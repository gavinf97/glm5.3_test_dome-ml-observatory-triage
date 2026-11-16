#!/usr/bin/env python3
"""Analyse the validation ratings: accuracy, inter-rater agreement, consensus, the pre-registered
go/no-go, CSV tables, figures and a dashboard. Run it at any point; it reports progress and marks
results as provisional until rating and adjudication are complete.

    python3 validation/analyse.py                 # writes validation/results/
    python3 validation/analyse.py --human gf      # if more than one human rater file exists

Outputs (validation/results/):
  accuracy.csv  agreement.csv  confusion.csv  error_codes.csv  by_stratum.csv  ratings_long.csv
  to_adjudicate.csv  fig_*.png/.svg  report.html  report.md  summary.json
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agreement_stats as st  # noqa: E402
from common import (CONFIG_PATH, ERROR_CODES, UNIT_FIELDS, UNIT_LABELS, VERDICTS, is_acceptable,  # noqa: E402
                    latest_ratings, load_config, load_sample, needs_adjudication, read_csv)

UNITS = list(UNIT_FIELDS)
ORDERED = ["major", "minor", "correct"]  # low to high, for weighted kappa
CONSENSUS = "consensus"
VIEW_LABELS = {"human": "Human", "judge_150": "Opus judge (same 150)", "consensus": "Consensus",
               "judge_250": "Opus judge (all 250)"}
# Reference palette (dataviz skill), light mode, first slots in fixed order.
SERIES = {"human": "#2a78d6", "judge_150": "#eb6834", "consensus": "#1baf7a", "judge_250": "#eda100"}
CODE_COLOURS = dict(zip(ERROR_CODES, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SEQ = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------

def find_human(rdir: Path, judge: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    humans = set()
    for path in sorted(Path(rdir).glob("*.csv")):
        rows = read_csv(path)
        if rows and rows[-1].get("rater_type") == "human":
            humans.add(path.stem)
    humans -= {judge, CONSENSUS}
    if len(humans) > 1:
        raise SystemExit(f"Several human raters found {sorted(humans)}: pass --human <id>.")
    return next(iter(humans), None)


def verdict_map(rater: str | None, rdir: Path) -> dict[tuple[str, str], dict]:
    return latest_ratings(rater, rdir) if rater else {}


def build_consensus(ids: list[str], human: dict, judge: dict, adjudicated: dict) -> tuple[dict, list[dict]]:
    """Consensus verdict per (paper, unit): the human's when the raters agree on acceptable/not;
    otherwise the adjudicated verdict. Pairs still awaiting either rater or adjudication are pending."""
    out, pending = {}, []
    for rid in ids:
        for unit in UNITS:
            h = human.get((rid, unit), {}).get("verdict", "")
            j = judge.get((rid, unit), {}).get("verdict", "")
            if not h or not j:
                pending.append({"record_id": rid, "unit": unit, "human": h, "judge": j, "reason": "not yet rated by both"})
            elif not needs_adjudication(h, j):
                out[(rid, unit)] = human[(rid, unit)]
            elif (rid, unit) in adjudicated:
                out[(rid, unit)] = adjudicated[(rid, unit)]
            else:
                pending.append({"record_id": rid, "unit": unit, "human": h, "judge": j, "reason": "needs adjudication"})
    return out, pending


# ---------------------------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------------------------

def accuracy_table(views: dict[str, tuple[list[str], dict]], config: dict) -> pd.DataFrame:
    rows = []
    primary = config["primary_units"]
    for view, (ids, ratings) in views.items():
        block = []
        for unit in UNITS:
            vs = [ratings[(rid, unit)]["verdict"] for rid in ids if (rid, unit) in ratings]
            c = Counter(vs)
            judged = c["correct"] + c["minor"] + c["major"]
            ok = c["correct"] + c["minor"]
            lo, hi = st.wilson(ok, judged)
            block.append({"view": view, "unit": unit, "primary": unit in primary, "n_papers": len(ids),
                          "n_rated": len(vs), "n_unsure": c["unsure"], "n_judged": judged, "n_correct": c["correct"],
                          "n_minor": c["minor"], "n_major": c["major"],
                          "pct_correct": c["correct"] / judged if judged else math.nan,
                          "pct_acceptable": ok / judged if judged else math.nan, "ci_low": lo, "ci_high": hi,
                          "p_vs_h0": st.binom_p_greater(ok, judged, config["h0_acceptable_rate"])})
        prim = [r for r in block if r["primary"] and not math.isnan(r["p_vs_h0"])]
        if prim:
            adj = multipletests([r["p_vs_h0"] for r in prim], alpha=config["alpha"], method=config["multiplicity"])[1]
            for r, p in zip(prim, adj):
                r["p_holm"] = float(p)
        for r in block:
            r.setdefault("p_holm", math.nan)
            r["passes_h0"] = bool(r["primary"] and not math.isnan(r["p_holm"]) and r["p_holm"] < config["alpha"])
        # Paper-level: all primary units acceptable (descriptive, not tested).
        complete = [rid for rid in ids if all(is_acceptable(ratings.get((rid, u), {}).get("verdict", "")) is not None
                                              for u in primary)]
        all_ok = sum(all(is_acceptable(ratings[(rid, u)]["verdict"]) for u in primary) for rid in complete)
        lo, hi = st.wilson(all_ok, len(complete))
        block.append({"view": view, "unit": "ALL_PRIMARY", "primary": False, "n_papers": len(ids),
                      "n_rated": len(complete), "n_unsure": math.nan, "n_judged": len(complete), "n_correct": math.nan,
                      "n_minor": math.nan, "n_major": len(complete) - all_ok, "pct_correct": math.nan,
                      "pct_acceptable": all_ok / len(complete) if complete else math.nan, "ci_low": lo, "ci_high": hi,
                      "p_vs_h0": math.nan, "p_holm": math.nan, "passes_h0": False})
        rows += block
    return pd.DataFrame(rows)


def agreement_table(ids: list[str], human: dict, judge: dict, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, conf = [], []
    reps, seed = config["bootstrap_reps"], config["seed"]
    for unit in UNITS:
        both = [(human[(r, unit)]["verdict"], judge[(r, unit)]["verdict"]) for r in ids
                if (r, unit) in human and (r, unit) in judge]
        for hv in VERDICTS:
            for jv in VERDICTS:
                conf.append({"unit": unit, "human": hv, "judge": jv, "count": sum(1 for p in both if p == (hv, jv))})
        pairs = [(h, j) for h, j in both if h != "unsure" and j != "unsure"]
        a = [is_acceptable(h) for h, _ in pairs]
        b = [is_acceptable(j) for _, j in pairs]
        a3 = [h for h, _ in pairs]
        b3 = [j for _, j in pairs]
        bin_cats = [True, False]
        k = st.cohen_kappa(a, b, bin_cats)
        ac1 = st.gwet_ac1(a, b, bin_cats)
        wk = st.weighted_kappa(a3, b3, ORDERED)
        pa, na = st.specific_agreement(a, b, True)
        k_ci = st.bootstrap_ci(lambda x, y: st.cohen_kappa(x, y, bin_cats), a, b, reps, seed)
        ac1_ci = st.bootstrap_ci(lambda x, y: st.gwet_ac1(x, y, bin_cats), a, b, reps, seed)
        wk_ci = st.bootstrap_ci(lambda x, y: st.weighted_kappa(x, y, ORDERED), a3, b3, reps, seed)
        rows.append({"unit": unit, "primary": unit in config["primary_units"], "n_both_rated": len(both),
                     "n_excluded_unsure": len(both) - len(pairs), "n_pairs": len(pairs),
                     "human_acceptable": float(np.mean(a)) if a else math.nan,
                     "judge_acceptable": float(np.mean(b)) if b else math.nan,
                     "pct_agreement": st.percent_agreement(a, b), "pct_agreement_3level": st.percent_agreement(a3, b3),
                     "gwet_ac1": ac1, "ac1_ci_low": ac1_ci[0], "ac1_ci_high": ac1_ci[1],
                     "cohen_kappa": k, "kappa_ci_low": k_ci[0], "kappa_ci_high": k_ci[1],
                     "weighted_kappa_3level": wk, "wkappa_ci_low": wk_ci[0], "wkappa_ci_high": wk_ci[1],
                     "pabak": st.pabak(a, b), "positive_agreement": pa, "negative_agreement": na,
                     "mcnemar_p": st.mcnemar_exact(a, b, True),
                     "passes_reliability": bool(not math.isnan(ac1) and ac1 >= config["reliability_min"])})
    return pd.DataFrame(rows), pd.DataFrame(conf)


def error_code_table(views: dict[str, tuple[list[str], dict]]) -> pd.DataFrame:
    rows = []
    for view, (ids, ratings) in views.items():
        idset = set(ids)
        for unit in UNITS:
            counts = Counter()
            for (rid, u), r in ratings.items():
                if u == unit and rid in idset and r.get("verdict") in ("minor", "major"):
                    counts.update(c for c in (r.get("error_codes") or "").split(";") if c)
            for code in ERROR_CODES:
                rows.append({"view": view, "unit": unit, "code": code, "count": counts[code]})
    return pd.DataFrame(rows)


def stratum_table(views: dict[str, tuple[list[str], dict]], strata: dict[str, str]) -> pd.DataFrame:
    rows = []
    for view, (ids, ratings) in views.items():
        for unit in UNITS:
            groups: dict[str, list[bool]] = {}
            for rid in ids:
                ok = is_acceptable(ratings.get((rid, unit), {}).get("verdict", ""))
                if ok is not None:
                    groups.setdefault(strata.get(rid, ""), []).append(ok)
            for s, vals in sorted(groups.items()):
                lo, hi = st.wilson(sum(vals), len(vals))
                rows.append({"view": view, "unit": unit, "stratum": s, "n_judged": len(vals),
                             "pct_acceptable": sum(vals) / len(vals), "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows)


def ratings_long(raters: dict[str, dict], sample: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for rater, ratings in raters.items():
        for (rid, unit), r in ratings.items():
            s = sample.get(rid, {})
            rows.append({"record_id": rid, "unit": unit, "rater": rater, "rater_type": r.get("rater_type", ""),
                         "verdict": r.get("verdict", ""), "acceptable": is_acceptable(r.get("verdict", "")),
                         "error_codes": r.get("error_codes", ""), "note": r.get("note", ""),
                         "stratum": s.get("stratum", ""), "human_set": s.get("human") == "1",
                         "timestamp": r.get("timestamp", "")})
    cols = ["record_id", "unit", "rater", "rater_type", "verdict", "acceptable", "error_codes", "note", "stratum",
            "human_set", "timestamp"]
    return pd.DataFrame(rows, columns=cols).sort_values(["rater", "record_id", "unit"]) if rows else pd.DataFrame(columns=cols)


# ---------------------------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------------------------

def decide(acc: pd.DataFrame, agr: pd.DataFrame, progress: dict, config: dict) -> dict:
    primary = config["primary_units"]
    reasons = []
    if progress["human_done"] < progress["human_total"]:
        reasons.append(f"human rating {progress['human_done']}/{progress['human_total']} papers")
    if progress["judge_done_150"] < progress["human_total"]:
        reasons.append(f"judge rating on the human set {progress['judge_done_150']}/{progress['human_total']} papers")
    if progress["pending_adjudication"]:
        reasons.append(f"{progress['pending_adjudication']} pairs awaiting adjudication")
    cons = acc[(acc.view == "consensus") & acc.unit.isin(primary)].set_index("unit")
    rel = agr[agr.unit.isin(primary)].set_index("unit")
    checks = []
    for u in primary:
        a = cons.loc[u] if u in cons.index else None
        r = rel.loc[u] if u in rel.index else None
        checks.append({"unit": u,
                       "acceptable": None if a is None else _num(a.pct_acceptable),
                       "ci": None if a is None else [_num(a.ci_low), _num(a.ci_high)],
                       "p_holm": None if a is None else _num(a.p_holm),
                       "accuracy_pass": bool(a is not None and a.passes_h0),
                       "ac1": None if r is None else _num(r.gwet_ac1),
                       "reliability_pass": bool(r is not None and r.passes_reliability)})
    all_pass = all(c["accuracy_pass"] and c["reliability_pass"] for c in checks)
    if reasons:
        status = "NOT YET DECIDED"
    else:
        status = "GO" if all_pass else "NO-GO"
    return {"status": status, "provisional_because": reasons, "checks": checks,
            "rule": (f"GO when every primary unit ({', '.join(primary)}) has consensus acceptable rate significantly "
                     f"above {config['h0_acceptable_rate']:.0%} (one-sided exact binomial, Holm-adjusted, alpha "
                     f"{config['alpha']}) AND Gwet's AC1 between human and judge >= {config['reliability_min']}.")}


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else round(x, 4)


# ---------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------

def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig, out: Path, name: str) -> Path:
    fig.patch.set_facecolor(SURFACE)
    png = out / f"{name}.png"
    fig.savefig(png, dpi=180, bbox_inches="tight")
    fig.savefig(out / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)
    return png


def _empty(ax, msg="No ratings yet"):
    ax.text(0.5, 0.5, msg, ha="center", va="center", color=INK2, transform=ax.transAxes)


def fig_accuracy(acc: pd.DataFrame, config: dict, out: Path) -> Path:
    views = ["human", "judge_150", "consensus"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    _style(ax)
    units = UNITS[::-1]
    offsets = dict(zip(views, (0.22, 0.0, -0.22)))
    any_data = False
    for v in views:
        d = acc[(acc.view == v)].set_index("unit")
        labelled = False
        for i, u in enumerate(units):
            if u in d.index and not math.isnan(d.loc[u, "pct_acceptable"]):
                any_data = True
                y = i + offsets[v]
                ax.plot([d.loc[u, "ci_low"], d.loc[u, "ci_high"]], [y, y], color=SERIES[v], linewidth=2,
                        solid_capstyle="round")
                ax.plot(d.loc[u, "pct_acceptable"], y, "o", color=SERIES[v], markersize=7,
                        markeredgecolor=SURFACE, markeredgewidth=1.5, label=None if labelled else VIEW_LABELS[v])
                labelled = True
    ax.axvline(config["h0_acceptable_rate"], color=INK2, linestyle="--", linewidth=1)
    ax.axvline(config["target_acceptable_rate"], color=INK2, linestyle=":", linewidth=1)
    ax.text(config["h0_acceptable_rate"], len(units) - 0.35, f" H0 {config['h0_acceptable_rate']:.0%}", color=INK2, fontsize=8)
    ax.text(config["target_acceptable_rate"], len(units) - 0.35, f" target {config['target_acceptable_rate']:.0%}",
            color=INK2, fontsize=8)
    ax.set_yticks(range(len(units)), [UNIT_LABELS[u] + ("" if u in config["primary_units"] else "\n(secondary)")
                                      for u in units], color=INK)
    ax.set_xlim(0.5, 1.0)
    ax.set_ylim(-0.6, len(units) - 0.1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("Tags acceptable (correct or minor), with 95% Wilson CI", color=INK2, fontsize=9)
    ax.set_title("Acceptable rate per rating unit", loc="left", color=INK, fontsize=11)
    if any_data:
        ax.legend(loc="lower left", frameon=False, fontsize=8, ncol=3, bbox_to_anchor=(0, -0.32))
    else:
        _empty(ax)
    return _save(fig, out, "fig_accuracy")


def fig_reliability(agr: pd.DataFrame, config: dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    _style(ax)
    units = UNITS[::-1]
    stats = [("gwet_ac1", "ac1", "Gwet's AC1 (gate)", SERIES["human"], 0.15),
             ("cohen_kappa", "kappa", "Cohen's kappa", SERIES["judge_150"], -0.15)]
    d = agr.set_index("unit")
    any_data = False
    for col, pre, label, colour, off in stats:
        labelled = False
        for i, u in enumerate(units):
            if u in d.index and not math.isnan(d.loc[u, col]):
                any_data = True
                lo, hi = d.loc[u, f"{pre}_ci_low"], d.loc[u, f"{pre}_ci_high"]
                if not math.isnan(lo):
                    ax.plot([lo, hi], [i + off] * 2, color=colour, linewidth=2, solid_capstyle="round")
                ax.plot(d.loc[u, col], i + off, "o", color=colour, markersize=7, markeredgecolor=SURFACE,
                        markeredgewidth=1.5, label=None if labelled else label)
                labelled = True
    ax.axvline(config["reliability_min"], color=INK2, linestyle="--", linewidth=1)
    ax.text(config["reliability_min"], len(units) - 0.4, f" gate {config['reliability_min']}", color=INK2, fontsize=8)
    ax.set_yticks(range(len(units)), [UNIT_LABELS[u] for u in units], color=INK)
    ax.set_xlim(-0.2, 1.0)
    ax.set_ylim(-0.6, len(units) - 0.1)
    ax.set_xlabel("Human vs Opus judge agreement on acceptable / not (95% bootstrap CI)", color=INK2, fontsize=9)
    ax.set_title("Inter-rater reliability", loc="left", color=INK, fontsize=11)
    if any_data:
        ax.legend(loc="lower left", frameon=False, fontsize=8, ncol=2, bbox_to_anchor=(0, -0.3))
    else:
        _empty(ax)
    return _save(fig, out, "fig_reliability")


def fig_confusion(conf: pd.DataFrame, out: Path) -> Path:
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    fig, axes = plt.subplots(1, len(UNITS), figsize=(13, 3.2))
    for ax, unit in zip(axes, UNITS):
        d = conf[conf.unit == unit]
        m = np.array([[int(d[(d.human == h) & (d.judge == j)]["count"].sum()) for j in VERDICTS] for h in VERDICTS])
        ax.imshow(m, cmap=cmap, vmin=0, vmax=max(1, m.max()))
        for i in range(len(VERDICTS)):
            for j in range(len(VERDICTS)):
                ax.text(j, i, m[i, j], ha="center", va="center", fontsize=9,
                        color="#ffffff" if m[i, j] > 0.55 * max(1, m.max()) else INK)
        ax.set_xticks(range(len(VERDICTS)), VERDICTS, rotation=45, fontsize=8, color=INK2)
        ax.set_yticks(range(len(VERDICTS)), VERDICTS if unit == UNITS[0] else [], fontsize=8, color=INK2)
        ax.set_title(UNIT_LABELS[unit], fontsize=9, color=INK)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xlabel("Opus judge", fontsize=8, color=INK2)
    axes[0].set_ylabel("Human", fontsize=8, color=INK2)
    fig.suptitle("Human vs Opus judge verdicts (papers rated by both)", x=0.01, ha="left", fontsize=11, color=INK)
    return _save(fig, out, "fig_confusion")


def fig_errors(err: pd.DataFrame, out: Path) -> Path:
    views = ["human", "judge_150"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharex=True)
    units = UNITS[::-1]
    total_max = 1
    for ax, v in zip(axes, views):
        _style(ax)
        d = err[err.view == v]
        left = np.zeros(len(units))
        for code in ERROR_CODES:
            vals = np.array([d[(d.unit == u) & (d.code == code)]["count"].sum() for u in units], dtype=float)
            ax.barh(range(len(units)), vals, left=left, color=CODE_COLOURS[code], height=0.6, label=code,
                    edgecolor=SURFACE, linewidth=2)
            left += vals
        total_max = max(total_max, left.max())
        ax.set_yticks(range(len(units)), [UNIT_LABELS[u] for u in units] if v == views[0] else [], color=INK)
        ax.set_title(VIEW_LABELS[v], loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Error codes ticked on minor/major verdicts", color=INK2, fontsize=9)
    axes[0].set_xlim(0, total_max * 1.05)
    axes[0].legend(loc="lower left", frameon=False, fontsize=8, ncol=5, bbox_to_anchor=(0, -0.42))
    return _save(fig, out, "fig_errors")


# ---------------------------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------------------------

def _pct(x):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.0%}"


def _f(x, nd=2):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def _p(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return "<0.001" if x < 0.001 else f"{x:.3f}"


def accuracy_rows(acc: pd.DataFrame, view: str) -> list[list[str]]:
    rows = []
    for _, r in acc[acc.view == view].iterrows():
        label = "All 4 primary units on the same paper" if r.unit == "ALL_PRIMARY" else UNIT_LABELS[r.unit]
        rows.append([label, f"{int(r.n_judged)}", "–" if math.isnan(r.n_unsure) else f"{int(r.n_unsure)}",
                     _pct(r.pct_correct), f"{_pct(r.pct_acceptable)} ({_pct(r.ci_low)}–{_pct(r.ci_high)})",
                     _p(r.p_holm) if r.primary else "–",
                     ("pass" if r.passes_h0 else "fail") if r.primary and not math.isnan(r.p_holm) else "–"])
    return rows


ACC_HEAD = ["Unit", "Judged", "Unsure", "Correct", "Acceptable (95% CI)", "Holm p vs H0", "H0 test"]
AGR_HEAD = ["Unit", "Pairs", "Agreement", "AC1 (95% CI)", "Kappa (95% CI)", "Weighted kappa, 3 levels", "PABAK",
            "Pos / neg agreement", "McNemar p", "Gate"]


def agreement_rows(agr: pd.DataFrame) -> list[list[str]]:
    return [[UNIT_LABELS[r.unit], f"{int(r.n_pairs)} (+{int(r.n_excluded_unsure)} unsure)", _pct(r.pct_agreement),
             f"{_f(r.gwet_ac1)} ({_f(r.ac1_ci_low)}–{_f(r.ac1_ci_high)})",
             f"{_f(r.cohen_kappa)} ({_f(r.kappa_ci_low)}–{_f(r.kappa_ci_high)})", _f(r.weighted_kappa_3level),
             _f(r.pabak), f"{_f(r.positive_agreement)} / {_f(r.negative_agreement)}", _p(r.mcnemar_p),
             ("pass" if r.passes_reliability else "fail") if not math.isnan(r.gwet_ac1) else "–"]
            for _, r in agr.iterrows()]


def md_table(head, rows) -> str:
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows])


def html_table(head, rows) -> str:
    th = "".join(f"<th>{html.escape(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f'<td class="{_cls(c)}">{html.escape(c)}</td>' for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _cls(cell: str) -> str:
    return {"pass": "ok", "fail": "bad"}.get(cell, "")


LIMITATIONS = [
    "One human rater, who also adjudicates the disagreements.",
    "Judgements use the title and abstract only, which is all the tagger sees.",
    "The judge (Claude Opus 5.5) is a different model family from the tagger (GLM-5.3-Flash), but an earlier "
    "Claude review shaped prompt e2; the human ratings are the anchor and the judge never sees them.",
    "Results apply to un-enriched confirmed AI/ML positives like wave2.",
    "The reliability gate uses the AC1 point estimate; its 95% CI is reported beside it.",
]


def write_reports(out: Path, config: dict, acc, agr, decision, progress, figs: dict, human_id, judge_id) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status = decision["status"]
    prov = decision["provisional_because"]
    md = [f"# GLM-5.3-Flash tag validation (prompt {config['prompt_version']})", "",
          f"Generated {now}. Cohort `{config['cohort']}`, human rater `{human_id or '-'}`, judge `{judge_id}` "
          f"({config['judge_model']} via Claude Code).", "",
          f"## Decision: **{status}**", ""]
    if prov:
        md += ["Provisional, because: " + "; ".join(prov) + ".", ""]
    md += [decision["rule"], "",
           "## Progress", "",
           md_table(["", "Done", "Total"], [["Human (papers, all 5 units)", str(progress["human_done"]), str(progress["human_total"])],
                                           ["Judge on human set", str(progress["judge_done_150"]), str(progress["human_total"])],
                                           ["Judge on all papers", str(progress["judge_done_all"]), str(progress["all_total"])],
                                           ["Pairs needing adjudication, still open", str(progress["pending_adjudication"]), "–"]]), ""]
    for view in ("consensus", "human", "judge_150", "judge_250"):
        md += [f"## Accuracy: {VIEW_LABELS[view]}", "", md_table(ACC_HEAD, accuracy_rows(acc, view)), ""]
    md += ["## Agreement: human vs Opus judge (acceptable / not)", "", md_table(AGR_HEAD, agreement_rows(agr)), "",
           "AC1 is the pre-registered reliability statistic. Kappa is shown beside it; when most tags are acceptable, "
           "kappa can be low even when the raters agree on nearly every paper (the prevalence paradox).", "",
           "## Figures", ""] + [f"![{k}]({v.name})" for k, v in figs.items()] + ["", "## Limitations", ""] + \
          [f"- {x}" for x in LIMITATIONS]
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    imgs = "".join(f'<figure><img alt="{html.escape(k)}" src="data:image/png;base64,'
                   f'{base64.b64encode(v.read_bytes()).decode()}"></figure>' for k, v in figs.items())
    badge = {"GO": "go", "NO-GO": "nogo"}.get(status, "wait")
    checks = "".join(
        f"<tr><td>{html.escape(UNIT_LABELS[c['unit']])}</td><td>{_pct(c['acceptable'])}"
        f"{'' if not c['ci'] else ' (' + _pct(c['ci'][0]) + '–' + _pct(c['ci'][1]) + ')'}</td>"
        f"<td class='{'ok' if c['accuracy_pass'] else 'bad'}'>{'pass' if c['accuracy_pass'] else 'not yet' if prov else 'fail'}</td>"
        f"<td>{_f(c['ac1'])}</td><td class='{'ok' if c['reliability_pass'] else 'bad'}'>"
        f"{'pass' if c['reliability_pass'] else 'not yet' if prov else 'fail'}</td></tr>" for c in decision["checks"])
    prog_rows = [("Human", progress["human_done"], progress["human_total"]),
                 ("Judge, human set", progress["judge_done_150"], progress["human_total"]),
                 ("Judge, all papers", progress["judge_done_all"], progress["all_total"])]
    prog = "".join(f"<div class='pr'><span>{n}</span><span class='bar'><i style='width:{(100 * d / t) if t else 0:.0f}%'></i></span>"
                   f"<span class='num'>{d} / {t}</span></div>" for n, d, t in prog_rows)
    sections = "".join(f"<h2>Accuracy: {VIEW_LABELS[v]}</h2>{html_table(ACC_HEAD, accuracy_rows(acc, v))}"
                       for v in ("consensus", "human", "judge_150", "judge_250"))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Tag Validation</title><style>
:root {{ --bg:#f7f7f5; --surface:#fff; --s2:#f0efeb; --text:#1d1d1b; --muted:#6b6a65; --border:#dddcd6;
  --ok:#1e7a46; --oks:#dff1e6; --bad:#b3261e; --bads:#f9e0de; --wait:#8a6a00; --waits:#f8f0d2; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#161615; --surface:#1f1f1d; --s2:#2a2a27;
  --text:#ecebe6; --muted:#a09f98; --border:#3a3a36; --ok:#6fd39a; --oks:#1c3a28; --bad:#ff8a80; --bads:#472321;
  --wait:#e6c65a; --waits:#3d3418; }} }}
:root[data-theme="dark"] {{ --bg:#161615; --surface:#1f1f1d; --s2:#2a2a27; --text:#ecebe6; --muted:#a09f98; --border:#3a3a36;
  --ok:#6fd39a; --oks:#1c3a28; --bad:#ff8a80; --bads:#472321; --wait:#e6c65a; --waits:#3d3418; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:16px; }} h1 {{ font-size:22px; margin:8px 0 4px; }}
h2 {{ font-size:17px; margin:28px 0 8px; }} .meta,.note {{ color:var(--muted); font-size:13px; }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:16px; margin:12px 0; }}
.badge {{ display:inline-block; font-weight:700; font-size:20px; padding:4px 14px; border-radius:8px; }}
.go {{ background:var(--oks); color:var(--ok); }} .nogo {{ background:var(--bads); color:var(--bad); }}
.wait {{ background:var(--waits); color:var(--wait); }}
.tw {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums; }}
th,td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--border); white-space:nowrap; }}
th {{ color:var(--muted); font-size:12px; }} td.ok {{ color:var(--ok); font-weight:600; }} td.bad {{ color:var(--bad); font-weight:600; }}
.pr {{ display:grid; grid-template-columns:150px 1fr 90px; gap:10px; align-items:center; margin:4px 0; }}
.bar {{ height:8px; background:var(--s2); border-radius:4px; overflow:hidden; }} .bar i {{ display:block; height:100%; background:var(--ok); }}
.num {{ font-variant-numeric:tabular-nums; color:var(--muted); font-size:13px; }}
figure {{ margin:12px 0; background:#fcfcfb; border:1px solid var(--border); border-radius:10px; padding:10px; }}
figure img {{ max-width:100%; height:auto; display:block; }}
@media (max-width:640px) {{ .pr {{ grid-template-columns:1fr; }} }}
</style></head><body><main>
<h1>GLM-5.3-Flash tag validation</h1>
<div class="meta">Prompt {html.escape(config['prompt_version'])} · cohort {html.escape(config['cohort'])} · human rater
{html.escape(human_id or '–')} · judge {html.escape(config['judge_model'])} via Claude Code · generated {now}</div>
<div class="card"><span class="badge {badge}">{status}</span>
{'<p class="note">Provisional, because: ' + html.escape('; '.join(prov)) + '.</p>' if prov else ''}
<p class="note">{html.escape(decision['rule'])}</p>
<div class="tw"><table><thead><tr><th>Primary unit</th><th>Consensus acceptable (95% CI)</th><th>Above H0</th>
<th>AC1</th><th>Reliability</th></tr></thead><tbody>{checks}</tbody></table></div></div>
<div class="card"><h2 style="margin-top:0">Progress</h2>{prog}
<p class="note">{progress['pending_adjudication']} human/judge disagreements still open for adjudication.</p></div>
{sections}
<h2>Agreement: human vs Opus judge (acceptable / not)</h2>{html_table(AGR_HEAD, agreement_rows(agr))}
<p class="note">AC1 is the pre-registered reliability statistic. Kappa is shown beside it: when most tags are acceptable,
kappa can be low even when the raters agree on nearly every paper (the prevalence paradox).</p>
<h2>Figures</h2>{imgs}
<h2>Limitations</h2><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in LIMITATIONS)}</ul>
<p class="note">Tables as CSV: accuracy.csv, agreement.csv, confusion.csv, error_codes.csv, by_stratum.csv,
ratings_long.csv, to_adjudicate.csv (same folder).</p>
</main></body></html>"""
    (out / "report.html").write_text(page, encoding="utf-8")


# ---------------------------------------------------------------------------------------------

def run(config: dict, human_id: str | None = None) -> dict:
    out = config["_results_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rdir = config["_ratings_dir"]
    sample_rows = load_sample(config["_sample_path"])
    sample = {r["record_id"]: r for r in sample_rows}
    strata = {rid: r.get("stratum", "") for rid, r in sample.items()}
    ids_all = [r["record_id"] for r in sample_rows]
    ids_h = [r["record_id"] for r in sample_rows if r.get("human") == "1"]
    judge_id = config["judge_rater_id"]
    human_id = find_human(rdir, judge_id, human_id)
    human = verdict_map(human_id, rdir)
    judge = verdict_map(judge_id, rdir)
    adjudicated = verdict_map(CONSENSUS, rdir)
    consensus, pending = build_consensus(ids_h, human, judge, adjudicated)

    def done(ratings, ids):
        return sum(all((rid, u) in ratings for u in UNITS) for rid in ids)

    progress = {"human_total": len(ids_h), "all_total": len(ids_all), "human_done": done(human, ids_h),
                "judge_done_150": done(judge, ids_h), "judge_done_all": done(judge, ids_all),
                "pending_adjudication": sum(p["reason"] == "needs adjudication" for p in pending)}
    views = {"human": (ids_h, human), "judge_150": (ids_h, judge), "consensus": (ids_h, consensus),
             "judge_250": (ids_all, judge)}

    acc = accuracy_table(views, config)
    agr, conf = agreement_table(ids_h, human, judge, config)
    err = error_code_table({k: views[k] for k in ("human", "judge_150", "judge_250")})
    strat = stratum_table({k: views[k] for k in ("consensus", "judge_250")}, strata)
    long = ratings_long({k: v for k, v in {human_id: human, judge_id: judge, CONSENSUS: adjudicated}.items() if k}, sample)
    to_adj = pd.DataFrame([p for p in pending if p["reason"] == "needs adjudication"],
                          columns=["record_id", "unit", "human", "judge", "reason"])

    for name, df in [("accuracy", acc), ("agreement", agr), ("confusion", conf), ("error_codes", err),
                     ("by_stratum", strat), ("ratings_long", long), ("to_adjudicate", to_adj)]:
        df.to_csv(out / f"{name}.csv", index=False, float_format="%.4f")

    figs = {"Acceptable rate per unit": fig_accuracy(acc, config, out),
            "Inter-rater reliability": fig_reliability(agr, config, out),
            "Verdict confusion": fig_confusion(conf, out),
            "Error codes": fig_errors(err, out)}
    decision = decide(acc, agr, progress, config)
    write_reports(out, config, acc, agr, decision, progress, figs, human_id, judge_id)
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "human_rater": human_id, "judge_rater": judge_id,
               "progress": progress, "decision": decision}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--human", help="Human rater id (auto-detected when there is only one).")
    args = parser.parse_args()
    config = load_config(args.config)
    summary = run(config, args.human)
    p, d = summary["progress"], summary["decision"]
    print(f"human {p['human_done']}/{p['human_total']} · judge {p['judge_done_150']}/{p['human_total']} on the human set, "
          f"{p['judge_done_all']}/{p['all_total']} overall · {p['pending_adjudication']} pairs to adjudicate")
    print(f"decision: {d['status']}" + (f" (provisional: {'; '.join(d['provisional_because'])})" if d["provisional_because"] else ""))
    print(f"report: {config['_results_dir'] / 'report.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
