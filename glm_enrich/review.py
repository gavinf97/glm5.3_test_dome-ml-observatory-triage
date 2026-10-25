"""What the viewer shows and what it records: each cohort record joined with its latest GLM event,
the stored DeepSeek enrichment where there is one, and the latest rating per field.

Ratings are an append-only CSV; the latest row per (record_id, field) wins, so changing a verdict
never rewrites history. Field `_record` carries the per-record note.
"""

from __future__ import annotations

import csv
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from glm_enrich import COHORTS, FIELDS, REPO

RATINGS = REPO / "ratings" / "ratings.csv"
RATING_COLUMNS = ["record_id", "cohort", "field", "verdict", "preference", "note", "rater", "timestamp"]
VERDICTS = ("correct", "partly", "wrong", "unsure", "")
PREFERENCES = ("glm", "equal", "deepseek", "")
RATABLE = set(FIELDS) | {"_record"}

_lock = threading.Lock()


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _list(cell) -> list:
    try:
        value = json.loads(cell) if isinstance(cell, str) and cell.strip() else []
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def latest_ratings(path: Path = RATINGS) -> dict[tuple[str, str], dict]:
    out = {}
    for row in _read(path):
        out[(row["record_id"], row["field"])] = row
    return out


def append_rating(payload: dict, path: Path = RATINGS) -> dict:
    field = payload.get("field", "")
    verdict = payload.get("verdict", "") or ""
    preference = payload.get("preference", "") or ""
    if field not in RATABLE:
        raise ValueError(f"unknown field {field!r}")
    if verdict not in VERDICTS or preference not in PREFERENCES:
        raise ValueError("bad verdict or preference")
    if not payload.get("record_id"):
        raise ValueError("record_id is required")
    row = {"record_id": payload["record_id"], "cohort": payload.get("cohort", ""), "field": field,
           "verdict": verdict, "preference": preference, "note": (payload.get("note") or "")[:4000],
           "rater": (payload.get("rater") or "rater1")[:40],
           "timestamp": datetime.now(timezone.utc).isoformat()}
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RATING_COLUMNS)
            if new:
                writer.writeheader()
            writer.writerow(row)
    return row


def _manifest() -> dict[str, dict]:
    return {r["record_id"]: r for r in _read(REPO / "cohorts" / "manifest.csv")}


def records(cohort: str, ratings_path: Path = RATINGS) -> list[dict]:
    spec = COHORTS[cohort]
    inputs = _read(REPO / spec["input"])
    latest_event: dict[str, dict] = {}
    for row in sorted(_read(REPO / spec["events"]), key=lambda r: r.get("timestamp") or ""):
        latest_event[row["record_id"]] = row
    reference = {r["record_id"]: r for r in _read(REPO / spec["reference"])} if "reference" in spec else {}
    meta = _manifest()
    rated = latest_ratings(ratings_path)

    out = []
    for rec in inputs:
        rid = rec["record_id"]
        event = latest_event.get(rid)
        ref = reference.get(rid)
        m = meta.get(rid, {})
        fields = []
        for field in FIELDS:
            glm = _list(event.get(field)) if event else None
            ds = _list(ref.get(field)) if ref else None
            r = rated.get((rid, field), {})
            same = None
            if glm is not None and ds is not None:
                a = {str(v).strip().casefold() for v in (glm[:1] if field == "domain_tier1" else glm)}
                b = {str(v).strip().casefold() for v in (ds[:1] if field == "domain_tier1" else ds)}
                same = a == b
            fields.append({"field": field, "glm": glm, "deepseek": ds, "same": same,
                           "verdict": r.get("verdict", ""), "preference": r.get("preference", "")})
        out.append({
            "record_id": rid, "cohort": cohort, "title": rec.get("title", ""), "abstract": rec.get("abstract", ""),
            "journal": rec.get("journal", ""), "year": rec.get("year", ""),
            "preprint_server": m.get("preprint_server", ""), "doi": m.get("doi", ""), "pmid": m.get("pmid", ""),
            "pmcid": m.get("pmcid", ""), "stratum": m.get("stratum", ""),
            "glm": None if not event else {
                "parse_status": event.get("parse_status"), "rationale": event.get("rationale", ""),
                "vocab_violations": _list(event.get("vocab_violations")), "finish_reason": event.get("finish_reason"),
                "output_tokens": event.get("output_tokens"), "batch_id": event.get("batch_id")},
            "deepseek": None if not ref else {
                "rationale": ref.get("rationale", ""), "vocab_violations": _list(ref.get("vocab_violations")),
                "model_id": ref.get("model_id"), "batch_id": ref.get("batch_id")},
            "fields": fields,
            "note": rated.get((rid, "_record"), {}).get("note", ""),
        })
    return out
