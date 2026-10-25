#!/usr/bin/env python3
"""How far GLM's enrichment of the enriched100 cohort agrees with the DeepSeek V4.1 enrichment
stored for the same records, set beside how far DeepSeek V4.1 agreed with DeepSeek V4 on the
2026-09-15 model check. No database access: it reads the reference snapshot the export took.

    python3 scripts/compare_to_deepseek.py                  # prints, and writes the report
    python3 scripts/compare_to_deepseek.py --examples 5     # plus disagreements per field

The metrics are the triage repo's moros_pipeline/scripts/compare_enrichment_to_corpus.py, copied:
exact agreement (the same set of terms, case-folded), mean Jaccard overlap, both-empty share, and
the share of records agreeing on all six fields; domain_tier1 is compared as the first term only,
the way moros stores it.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glm_enrich import COHORTS, FIELDS, REPO  # noqa: E402

# DeepSeek V4.1 re-enrichment of 100 V4-enriched records against the stored V4 values, 2026-09-15
# (triage repo, logs/gate_enrich_compare_20260915.log): the same model family disagreeing with itself.
BASELINE_V4_VS_V41 = {"domain_tier1": 0.95, "domain_tier2": 0.43, "domain_tier3": 0.28,
                      "learning_paradigm": 0.87, "model_family": 0.77, "model_type": 0.45, "all_six": 0.04}
BASELINE_JACCARD = {"domain_tier1": 0.950, "domain_tier2": 0.605, "domain_tier3": 0.546,
                    "learning_paradigm": 0.893, "model_family": 0.868, "model_type": 0.598}


# --- copied from compare_enrichment_to_corpus.py -------------------------------------------------

def json_list(cell) -> list:
    if isinstance(cell, list):
        return cell
    if not isinstance(cell, str) or not cell.strip():
        return []
    try:
        value = json.loads(cell)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def latest_ok(rows: list[dict]) -> dict[str, dict]:
    """Last parsed event per record, the last-event-wins convention every log here uses."""
    out: dict[str, dict] = {}
    for row in sorted(rows, key=lambda r: r.get("timestamp") or ""):
        if (row.get("parse_status") or "").strip() == "ok":
            out[row["record_id"]] = row
    return out


def _norm(values) -> set[str]:
    return {str(v).strip().casefold() for v in values if v is not None and str(v).strip()}


def event_terms(row: dict, field: str) -> set[str]:
    values = json_list(row.get(field, ""))
    if field == "domain_tier1":
        values = values[:1]
    return _norm(values)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


# The reference snapshot stores every field as a JSON list cell, so both sides are read the same way.
stored_terms = event_terms


def compare(pairs: list[tuple[dict, dict]]) -> dict:
    """pairs: (event row, reference row) for the same record."""
    n = len(pairs)
    result: dict = {"n": n, "fields": {}, "all_six": 0}
    if n == 0:
        return result
    all_six = [True] * n
    for field in FIELDS:
        exact = both_empty = 0
        jac = 0.0
        for i, (row, doc) in enumerate(pairs):
            a, b = event_terms(row, field), stored_terms(doc, field)
            if a == b:
                exact += 1
                if not a:
                    both_empty += 1
            else:
                all_six[i] = False
            jac += jaccard(a, b)
        result["fields"][field] = {"exact": exact / n, "mean_jaccard": jac / n, "both_empty": both_empty / n}
    result["all_six"] = sum(all_six) / n
    return result


def disagreements(pairs: list[tuple[dict, dict]], field: str, limit: int) -> list[dict]:
    out = []
    for row, doc in pairs:
        a, b = event_terms(row, field), stored_terms(doc, field)
        if a != b:
            out.append({"record_id": row["record_id"], "glm": sorted(a), "deepseek": sorted(b)})
            if len(out) >= limit:
                break
    return out

# -------------------------------------------------------------------------------------------------


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def profile(rows: list[dict]) -> dict:
    def mean(col):
        values = [float(r[col]) for r in rows if (r.get(col) or "").strip() not in ("", "nan", "None")]
        return statistics.mean(values) if values else None
    n = len(rows)
    violating = sum(1 for r in rows if json_list(r.get("vocab_violations")))
    tokens_in = sum(float(r.get("input_tokens") or 0) for r in rows)
    cached = sum(float(r.get("cache_hit_tokens") or 0) for r in rows)
    return {"n": n, "violating_share": violating / n if n else None, "mean_input_tokens": mean("input_tokens"),
            "mean_output_tokens": mean("output_tokens"), "mean_reasoning_tokens": mean("reasoning_tokens"),
            "cache_share": cached / tokens_in if tokens_in else None}


def pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def num(x) -> str:
    return "n/a" if x is None else f"{x:,.0f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--examples", type=int, default=0)
    parser.add_argument("--out", type=Path, default=REPO / "reports" / "agreement_glm53flash_vs_deepseek.md")
    args = parser.parse_args()

    events_path = REPO / COHORTS["enriched100"]["events"]
    reference_path = REPO / COHORTS["enriched100"]["reference"]
    for p in (events_path, reference_path):
        if not p.exists():
            print(f"{p.relative_to(REPO)} does not exist yet")
            return 1
    all_events = read_csv(events_path)
    events = latest_ok(all_events)
    reference = {r["record_id"]: r for r in read_csv(reference_path)}
    pairs = [(events[r], reference[r]) for r in events if r in reference]
    result = compare(pairs)

    latest_any: dict[str, dict] = {}
    for row in sorted(all_events, key=lambda r: r.get("timestamp") or ""):
        latest_any[row["record_id"]] = row
    n_parse_error = sum(1 for r in latest_any.values() if r.get("parse_status") == "parse_error")
    n_truncated = sum(1 for r in latest_any.values() if r.get("finish_reason") == "length")
    glm_profile = profile(list(events.values()))
    ds_profile = profile([reference[r] for r in events if r in reference])

    lines = [
        "# GLM-5.3-Flash vs DeepSeek V4.1-Flash on the enriched100 cohort", "",
        f"{result['n']} records compared ({len(reference)} in the cohort, {len(latest_any)} with a GLM event, "
        f"{n_parse_error} GLM parse_error, {n_truncated} truncated). Prompt e1, vocab sha256 41db952f..., "
        "identical system message and parser on both sides.", "",
        "| Field | GLM vs DeepSeek V4.1: exact | Jaccard | both empty | Baseline, V4.1 vs V4: exact | Jaccard |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for field, s in result.get("fields", {}).items():
        lines.append(f"| {field} | {pct(s['exact'])} | {s['mean_jaccard']:.3f} | {pct(s['both_empty'])} | "
                     f"{pct(BASELINE_V4_VS_V41[field])} | {BASELINE_JACCARD[field]:.3f} |")
    lines += [f"| **all six** | **{pct(result.get('all_six'))}** | | | **{pct(BASELINE_V4_VS_V41['all_six'])}** | |", "",
              "The baseline is DeepSeek disagreeing with its own previous version (2026-09-15). A GLM figure near it",
              "means GLM diverges from DeepSeek about as much as DeepSeek diverges from itself.", "",
              "| | GLM-5.3-Flash | DeepSeek V4.1-Flash (stored) |", "|---|---:|---:|",
              f"| records with a vocabulary violation | {pct(glm_profile['violating_share'])} | {pct(ds_profile['violating_share'])} |",
              f"| mean input tokens | {num(glm_profile['mean_input_tokens'])} | {num(ds_profile['mean_input_tokens'])} |",
              f"| prompt-cache share | {pct(glm_profile['cache_share'])} | {pct(ds_profile['cache_share'])} |",
              f"| mean output tokens | {num(glm_profile['mean_output_tokens'])} | {num(ds_profile['mean_output_tokens'])} |",
              f"| mean reasoning tokens | {num(glm_profile['mean_reasoning_tokens']) if glm_profile['mean_reasoning_tokens'] else 'not reported'} | not stored |",
              ""]
    if args.examples:
        lines += ["## Disagreements", ""]
        for field in FIELDS:
            for row in disagreements(pairs, field, args.examples):
                lines.append(f"- `{field}` {row['record_id']}: GLM {row['glm']} / DeepSeek {row['deepseek']}")
        lines.append("")
    text = "\n".join(lines)
    print(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"\nwrote {args.out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
