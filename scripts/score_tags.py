#!/usr/bin/env python3
"""Rule-based scorecard for the modelling tags, the automatic half of the correctness review: does
each model type get its family, does model_type hold things that are not models, and so on. Scores
every events file that exists (DeepSeek reference, GLM e1, GLM e2) side by side, in plain language.

    python3 scripts/score_tags.py            # prints and writes reports/e2_improvement/tag_scorecard.md

For e2, "model only" removes what post-processing backfilled (the family_backfilled column), so the
prompt's own effect and the post-processing's are visible separately.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glm_enrich import COHORTS, E2_REPORTS, REPO  # noqa: E402
from glm_enrich.e2 import EXCLUDED_KINDS  # noqa: E402

ENSEMBLE = re.compile(r"random forest|xgboost|gradient boost|lightgbm|catboost|adaboost|bagging|stacking|extra trees|causal forest", re.I)
DIM_RED = re.compile(r"principal component|t-sne|\bumap\b|non-negative matrix|independent component|factor analysis|multidimensional scaling", re.I)
PLAIN_NN = re.compile(r"^(neural network|multilayer perceptron)$", re.I)
NOT_A_MODEL = re.compile("|".join(f"(?:{p})" for k, p in EXCLUDED_KINDS.items() if k != "optimiser_check"), re.I)


def tags(cell) -> list[str]:
    try:
        value = json.loads(cell) if isinstance(cell, str) and cell.strip() else []
    except json.JSONDecodeError:
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def sets() -> list[tuple[str, pd.DataFrame]]:
    out = []
    ref = REPO / COHORTS["enriched100"]["reference"]
    if ref.exists():
        out.append(("DeepSeek V4.1 (e1), enriched100", pd.read_csv(ref, dtype=str)))
    for cohort in ("enriched100", "wave1", "wave2", "heldout250"):
        e1_path = REPO / COHORTS[cohort]["events"]
        e2_path = e1_path.parent / "e2" / e1_path.name
        variants = [(f"GLM e1, {cohort}", e1_path), (f"GLM e2, {cohort}", e2_path)]
        variants += [(f"GLM e2, {cohort}, {p.stem.split(cohort + '_', 1)[1].replace('_', ' ')}", p)
                     for p in sorted(e2_path.parent.glob(f"events_{cohort}_*.csv"))]
        for label, path in variants:
            if not path.exists():
                continue
            df = pd.read_csv(path, dtype=str)
            df = df[df["parse_status"] == "ok"].drop_duplicates("record_id", keep="last")
            if "family_backfilled" in df.columns:
                raw = df.copy()
                raw["model_family"] = [json.dumps([f for f in tags(fam) if not any(b.startswith(f + "<-") for b in tags(bf))])
                                       for fam, bf in zip(df["model_family"], df["family_backfilled"])]
                out.append((label + " (model only)", raw))
                out.append((label + " (with backfill)", df))
            else:
                out.append((label, df))
    return out


def score(df: pd.DataFrame) -> dict:
    rows = [{f: tags(r[f]) for f in ("learning_paradigm", "model_family", "model_type", "vocab_violations")}
            for _, r in df.iterrows()]
    def share(cond_has, cond_ok):
        has = [r for r in rows if cond_has(r)]
        return sum(1 for r in has if cond_ok(r)), len(has)
    fam = lambda r: {f.lower() for f in r["model_family"]}  # noqa: E731
    any_type = lambda pattern: (lambda r: any(pattern.search(t) for t in r["model_type"]))  # noqa: E731
    unknown = lambda r: [v for v in r["vocab_violations"] if ":unknown:" in v or ":cap_exceeded:" in v]  # noqa: E731
    return {
        "n": len(rows),
        "Tree ensembles that also get 'ensemble learning'": share(any_type(ENSEMBLE), lambda r: "ensemble learning" in fam(r)),
        "PCA/UMAP/t-SNE that also get 'dimensionality reduction'": share(any_type(DIM_RED), lambda r: "dimensionality reduction" in fam(r)),
        "Plain neural network/MLP that gets a neural family": share(any_type(PLAIN_NN), lambda r: bool({"classic neural network", "deep learning"} & fam(r))),
        "Model types listed but family left empty": sum(1 for r in rows if r["model_type"] and not r["model_family"]),
        "Records with a non-model item in model_type": sum(1 for r in rows if any(NOT_A_MODEL.search(t) for t in r["model_type"])),
        "Records with two paradigms": sum(1 for r in rows if len(r["learning_paradigm"]) == 2),
        "Records with a tag outside the vocabulary or over a cap": sum(1 for r in rows if unknown(r)),
    }


def fmt(v) -> str:
    if isinstance(v, tuple):
        ok, n = v
        return f"{ok}/{n} ({ok / n * 100:.0f}%)" if n else "-"
    return str(v)


def main() -> int:
    scored = [(label, score(df)) for label, df in sets()]
    metrics = [k for k in scored[0][1] if k != "n"]
    lines = ["# Modelling-tag scorecard", "",
             "Automatic checks from the correctness review, per run. Higher is better for the first three rows, "
             "lower is better for the next two. Two paradigms and vocabulary misses are context, not scores.", "",
             "e2 is the EXPERIMENTAL local prompt (experimental/e2/PROVENANCE.md). \"Model only\" is what GLM itself "
             "returned; \"with backfill\" adds the logged family backfill.", ""]
    for label, s in scored:
        lines += [f"## {label} ({s['n']} records)", "", "| Check | Result |", "|---|---:|"]
        lines += [f"| {m} | {fmt(s[m])} |" for m in metrics] + [""]
    text = "\n".join(lines)
    print(text)
    out = E2_REPORTS / "tag_scorecard.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
