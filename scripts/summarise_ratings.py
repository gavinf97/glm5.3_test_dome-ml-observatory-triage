#!/usr/bin/env python3
"""Summarise the rubric ratings: verdict counts per field and cohort, the acceptable share
(correct + partly, of those judged), and on enriched100 the GLM / equal / DeepSeek preference on
fields where the two models disagree.

    python3 scripts/summarise_ratings.py     # prints, and writes reports/ratings_summary.md
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glm_enrich import COHORTS, FIELDS, REPO  # noqa: E402
from glm_enrich.review import latest_ratings, records  # noqa: E402

OUT = REPO / "reports" / "ratings_summary.md"


def main() -> int:
    rated = latest_ratings()
    lines = ["# Rubric ratings", "",
             "Correct / partly (right direction, missing or extra) / wrong / can't judge. "
             "Acceptable = (correct + partly) / (correct + partly + wrong).", ""]
    for cohort in COHORTS:
        if not (REPO / COHORTS[cohort]["input"]).exists():
            continue
        recs = records(cohort)
        verdicts: dict[str, Counter] = defaultdict(Counter)
        prefs: dict[str, Counter] = defaultdict(Counter)
        by_agreement: dict[str, Counter] = defaultdict(Counter)
        n_rated_records = 0
        for rec in recs:
            any_rated = False
            for f in rec["fields"]:
                v = rated.get((rec["record_id"], f["field"]), {}).get("verdict", "")
                if v:
                    any_rated = True
                    verdicts[f["field"]][v] += 1
                    if f["same"] is not None:
                        by_agreement["agree" if f["same"] else "diverge"][v] += 1
                p = rated.get((rec["record_id"], f["field"]), {}).get("preference", "")
                if p and f["same"] is False:
                    prefs[f["field"]][p] += 1
            n_rated_records += any_rated
        if not n_rated_records:
            continue
        lines += [f"## {cohort} ({n_rated_records} of {len(recs)} records rated)", "",
                  "| Field | correct | partly | wrong | can't judge | acceptable |", "|---|---:|---:|---:|---:|---:|"]
        for field in FIELDS:
            c = verdicts[field]
            judged = c["correct"] + c["partly"] + c["wrong"]
            acc = f"{(c['correct'] + c['partly']) / judged * 100:.0f}%" if judged else "n/a"
            lines.append(f"| {field} | {c['correct']} | {c['partly']} | {c['wrong']} | {c['unsure']} | {acc} |")
        lines.append("")
        if by_agreement:
            lines += ["| GLM vs DeepSeek | correct | partly | wrong | can't judge |", "|---|---:|---:|---:|---:|"]
            for key in ("agree", "diverge"):
                c = by_agreement[key]
                lines.append(f"| fields where they {key} | {c['correct']} | {c['partly']} | {c['wrong']} | {c['unsure']} |")
            lines.append("")
        if prefs:
            lines += ["| Diverging field | GLM better | equal | DeepSeek better |", "|---|---:|---:|---:|"]
            for field in FIELDS:
                c = prefs[field]
                lines.append(f"| {field} | {c['glm']} | {c['equal']} | {c['deepseek']} |")
            lines.append("")
    text = "\n".join(lines)
    print(text)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
