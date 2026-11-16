"""Shared pieces of the tag validation: the frozen config, the rubric vocabulary, the sample and the
append-only ratings files. Standard library only, so the rating app runs anywhere.

Ratings are one CSV per rater in validation/ratings/. Rows are only ever appended; the latest row per
(record_id, unit) wins, so changing a verdict never rewrites history.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG_PATH = HERE / "config.json"
SAMPLE_PATH = HERE / "sample.csv"
RATINGS_DIR = HERE / "ratings"
RESULTS_DIR = HERE / "results"
RUBRIC_PATH = HERE / "RUBRIC.md"

VERDICTS = ("correct", "minor", "major", "unsure")
VERDICT_SCORE = {"major": 0, "minor": 1, "correct": 2}
ERROR_CODES = {
    "missing": "A tag the abstract clearly supports is absent",
    "unsupported": "A tag is present that the title/abstract does not support (guessed or hallucinated)",
    "wrong_term": "The right idea, but the wrong vocabulary term or level (e.g. wrong family, wrong EDAM tier)",
    "not_a_model": "model_type holds something that is not an ML model (SHAP, a task, a statistic, a pipeline)",
    "vocab": "A term outside the closed vocabulary, or more terms than the cap allows",
}
# The tag fields each rating unit covers. `domain` is judged as one path through the three EDAM tiers.
UNIT_FIELDS = {
    "domain": ("domain_tier1", "domain_tier2", "domain_tier3"),
    "learning_paradigm": ("learning_paradigm",),
    "model_family": ("model_family",),
    "model_type": ("model_type",),
    "model_use": ("model_use",),
}
UNIT_LABELS = {
    "domain": "Domain (EDAM tiers 1-3)",
    "learning_paradigm": "Learning paradigm",
    "model_family": "Model family",
    "model_type": "Model type",
    "model_use": "Model use",
}
RATING_COLUMNS = ["record_id", "unit", "verdict", "error_codes", "note", "rater", "rater_type", "timestamp"]
SAMPLE_COLUMNS = ["order", "record_id", "stratum", "human"]

_lock = threading.Lock()


def load_config(path: Path = CONFIG_PATH) -> dict:
    """The frozen settings. Optional keys `sample_path`, `ratings_dir` and `results_dir` (relative to the
    repo, or absolute) redirect the outputs, e.g. for a dry run on another cohort."""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    config["_sample_path"] = _resolve(config.get("sample_path"), SAMPLE_PATH)
    config["_ratings_dir"] = _resolve(config.get("ratings_dir"), RATINGS_DIR)
    config["_results_dir"] = _resolve(config.get("results_dir"), RESULTS_DIR)
    return config


def _resolve(value, default: Path) -> Path:
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else (REPO / p)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rater_instructions(path: Path = RUBRIC_PATH) -> str:
    """The part of RUBRIC.md both raters read; the judge gets it verbatim."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"<!-- RATER INSTRUCTIONS START -->(.*?)<!-- RATER INSTRUCTIONS END -->", text, re.S)
    if not m:
        raise SystemExit("RUBRIC.md has no RATER INSTRUCTIONS section.")
    return m.group(1).strip()


def tagger_prompt() -> str:
    """The frozen e2 system message GLM was given: the vocabularies and rules the tags are judged against."""
    return (REPO / "experimental" / "e2" / "enrichment_system_message.e2.txt").read_text(encoding="utf-8")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_list(cell) -> list[str]:
    try:
        value = json.loads(cell) if isinstance(cell, str) and cell.strip() else []
    except json.JSONDecodeError:
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def load_sample(path: Path = SAMPLE_PATH) -> list[dict]:
    rows = read_csv(Path(path))
    if not rows:
        raise SystemExit(f"{path.name} not found or empty: run  python3 validation/make_sample.py  first.")
    return sorted(rows, key=lambda r: int(r["order"]))


def is_acceptable(verdict: str) -> bool | None:
    """True/False for correct-minor/major; None for unsure or missing."""
    if verdict in ("correct", "minor"):
        return True
    if verdict == "major":
        return False
    return None


def load_items(config: dict, sample: list[dict]) -> list[dict]:
    """The sampled records with title, abstract and the tags to judge. Never the tagger's rationale:
    raters judge the tags against the abstract, not against the model's own argument."""
    inputs = {r["record_id"]: r for r in read_csv(REPO / config["input"])}
    events: dict[str, dict] = {}
    for row in sorted(read_csv(REPO / config["events"]), key=lambda r: r.get("timestamp") or ""):
        if row.get("parse_status") == "ok" and row.get("prompt_version") == config["prompt_version"]:
            events[row["record_id"]] = row
    items = []
    for s in sample:
        rid = s["record_id"]
        rec, event = inputs.get(rid), events.get(rid)
        if rec is None or event is None:
            raise SystemExit(f"record {rid} is in the sample but has no input row or no '{config['prompt_version']}' event.")
        items.append({
            "order": int(s["order"]), "record_id": rid, "stratum": s.get("stratum", ""), "human": s.get("human") == "1",
            "title": rec.get("title", ""), "abstract": rec.get("abstract", ""),
            "journal": rec.get("journal", ""), "year": rec.get("year", ""),
            "tags": {field: as_list(event.get(field)) for fields in UNIT_FIELDS.values() for field in fields},
        })
    return items


def ratings_path(rater: str, ratings_dir: Path = RATINGS_DIR) -> Path:
    safe = "".join(c for c in rater if c.isalnum() or c in "-_.")
    if not safe or safe != rater:
        raise ValueError("rater id may contain only letters, digits, '-', '_' and '.'")
    return Path(ratings_dir) / f"{safe}.csv"


def latest_ratings(rater: str, ratings_dir: Path = RATINGS_DIR) -> dict[tuple[str, str], dict]:
    out = {}
    for row in read_csv(ratings_path(rater, ratings_dir)):
        out[(row["record_id"], row["unit"])] = row
    return out


def append_rating(rater: str, rater_type: str, record_id: str, unit: str, verdict: str,
                  error_codes: list[str] | None = None, note: str = "",
                  ratings_dir: Path = RATINGS_DIR) -> dict:
    if unit not in UNIT_FIELDS:
        raise ValueError(f"unknown unit {unit!r}")
    if verdict not in VERDICTS:
        raise ValueError(f"unknown verdict {verdict!r}")
    codes = [c for c in (error_codes or []) if c]
    bad = [c for c in codes if c not in ERROR_CODES]
    if bad:
        raise ValueError(f"unknown error code(s) {bad}")
    if not record_id:
        raise ValueError("record_id is required")
    row = {"record_id": record_id, "unit": unit, "verdict": verdict, "error_codes": ";".join(sorted(set(codes))),
           "note": (note or "")[:4000], "rater": rater, "rater_type": rater_type,
           "timestamp": datetime.now(timezone.utc).isoformat()}
    path = ratings_path(rater, ratings_dir)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RATING_COLUMNS)
            if new:
                writer.writeheader()
            writer.writerow(row)
    return row


def needs_adjudication(human_verdict: str, judge_verdict: str) -> bool:
    """A (paper, unit) pair goes to adjudication when both raters have rated it and they differ on
    acceptable vs not, or either said 'unsure'."""
    if not human_verdict or not judge_verdict:
        return False
    a, b = is_acceptable(human_verdict), is_acceptable(judge_verdict)
    return a is None or b is None or a != b
