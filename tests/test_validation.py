"""Tests for validation/: the agreement statistics, the sample draw, the ratings log, the judge's answer
parsing (with canned CLI output, no network) and an end-to-end analysis on synthetic ratings."""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

VALIDATION = Path(__file__).resolve().parents[1] / "validation"
sys.path.insert(0, str(VALIDATION))

import agreement_stats as st  # noqa: E402
import common  # noqa: E402
import judge_opus  # noqa: E402
import make_sample  # noqa: E402


# --- statistics ---------------------------------------------------------------------------------

def test_kappas_match_sklearn():
    sk = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(0)
    for _ in range(100):
        n = int(rng.integers(5, 60))
        a, b = list(rng.integers(0, 3, n)), list(rng.integers(0, 3, n))
        ref = sk.cohen_kappa_score(a, b)
        got = st.cohen_kappa(a, b)
        assert (math.isnan(ref) and math.isnan(got)) or got == pytest.approx(ref)
        for w in ("linear", "quadratic"):
            assert st.weighted_kappa(a, b, [0, 1, 2], w) == pytest.approx(
                sk.cohen_kappa_score(a, b, weights=w, labels=[0, 1, 2]))


def test_ac1_pabak_specific_agreement_hand_example():
    # 100 papers: both acceptable 80, A only 10, B only 5, both not 5.
    a = [1] * 80 + [1] * 10 + [0] * 5 + [0] * 5
    b = [1] * 80 + [0] * 10 + [1] * 5 + [0] * 5
    pi = (0.90 + 0.85) / 2
    pe = 2 * pi * (1 - pi)
    assert st.gwet_ac1(a, b, [1, 0]) == pytest.approx((0.85 - pe) / (1 - pe))
    assert st.pabak(a, b) == pytest.approx(0.70)
    pa, na = st.specific_agreement(a, b, 1)
    assert pa == pytest.approx(160 / 175) and na == pytest.approx(10 / 25)
    assert st.cohen_kappa(a, b) < st.gwet_ac1(a, b, [1, 0])  # the prevalence paradox


def test_perfect_and_degenerate_agreement():
    a = [True, False, True, True]
    assert st.cohen_kappa(a, a) == pytest.approx(1.0)
    assert st.gwet_ac1(a, a, [True, False]) == pytest.approx(1.0)
    same = [True] * 5
    assert math.isnan(st.cohen_kappa(same, same))  # undefined, but no crash
    assert st.gwet_ac1(same, same, [True, False]) == pytest.approx(1.0)
    assert math.isnan(st.cohen_kappa([], []))
    assert st.mcnemar_exact(same, same) == 1.0


def test_wilson_and_binomial():
    lo, hi = st.wilson(135, 150)
    assert 0.84 < lo < 0.85 and 0.93 < hi < 0.94
    assert st.binom_p_greater(135, 150, 0.8) < 0.01
    assert st.binom_p_greater(120, 150, 0.8) > 0.4


# --- sample and ratings --------------------------------------------------------------------------

def test_draw_is_deterministic_and_proportional():
    ids = [f"r{i:03d}" for i in range(250)]
    strata = {rid: ("A" if i < 200 else "B") for i, rid in enumerate(ids)}
    one = make_sample.draw(ids, strata, 150, 7)
    two = make_sample.draw(ids, strata, 150, 7)
    assert one == two
    human = [r for r in one if r["human"] == "1"]
    assert len(human) == 150 and len(one) == 250
    assert sum(r["stratum"] == "A" for r in human) == 120
    assert sorted(r["order"] for r in one) == list(range(1, 251))
    assert make_sample.draw(ids, strata, 150, 8) != one


def test_append_rating_validates_and_latest_wins(tmp_path):
    common.append_rating("gf", "human", "p1", "model_type", "major", ["missing"], "x", ratings_dir=tmp_path)
    common.append_rating("gf", "human", "p1", "model_type", "minor", [], "", ratings_dir=tmp_path)
    assert common.latest_ratings("gf", tmp_path)[("p1", "model_type")]["verdict"] == "minor"
    for bad in (dict(unit="bogus", verdict="minor"), dict(unit="model_type", verdict="great"),
                dict(unit="model_type", verdict="minor", error_codes=["nope"])):
        with pytest.raises(ValueError):
            common.append_rating("gf", "human", "p1", bad["unit"], bad["verdict"], bad.get("error_codes"),
                                 ratings_dir=tmp_path)
    with pytest.raises(ValueError):
        common.ratings_path("../evil", tmp_path)


def test_needs_adjudication():
    assert not common.needs_adjudication("correct", "minor")
    assert common.needs_adjudication("correct", "major")
    assert common.needs_adjudication("unsure", "correct")
    assert not common.needs_adjudication("", "major")


def test_rubric_section_loads():
    text = common.rater_instructions()
    assert "## Verdicts" in text and "RATER INSTRUCTIONS" not in text


# --- judge parsing (canned CLI output, no network) ------------------------------------------------

def _answer(verdict="correct"):
    return {u: {"verdict": verdict, "error_codes": [] if verdict == "correct" else ["missing"], "reason": "r"}
            for u in common.UNIT_FIELDS}


def _envelope(answer, model="claude-opus-5-5", **extra):
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(answer),
                       "structured_output": answer, "modelUsage": {model: {}, "claude-haiku-5-5": {}},
                       "session_id": "s", **extra})


def test_judge_parses_valid_answer():
    ans, info = judge_opus.parse_envelope(_envelope(_answer("minor")), "claude-opus-5-5")
    assert ans["model_type"]["verdict"] == "minor" and ans["model_type"]["error_codes"] == ["missing"]
    assert "claude-opus-5-5" in info["models"]


def test_judge_falls_back_to_result_text():
    env = json.loads(_envelope(_answer()))
    env.pop("structured_output")
    env["result"] = "Here you go:\n" + json.dumps(_answer()) + "\n"
    ans, _ = judge_opus.parse_envelope(json.dumps(env), "claude-opus-5-5")
    assert ans["domain"]["verdict"] == "correct"


def test_judge_rejects_wrong_model_and_bad_answers():
    with pytest.raises(ValueError, match="did not come from"):
        judge_opus.parse_envelope(_envelope(_answer(), model="claude-sonnet-5-5"), "claude-opus-5-5")
    bad = _answer()
    bad["model_use"]["verdict"] = "fine"
    with pytest.raises(ValueError):
        judge_opus.parse_envelope(_envelope(bad), "claude-opus-5-5")
    missing = _answer()
    missing.pop("domain")
    with pytest.raises(ValueError):
        judge_opus.parse_envelope(_envelope(missing), "claude-opus-5-5")
    with pytest.raises(ValueError):
        judge_opus.parse_envelope("not json at all", "claude-opus-5-5")


def test_judge_detects_usage_limit():
    env = json.dumps({"type": "result", "subtype": "error", "is_error": True,
                      "result": "Claude usage limit reached. Your limit will reset at 5pm."})
    with pytest.raises(judge_opus.UsageLimit):
        judge_opus.parse_envelope(env, "claude-opus-5-5")


def test_judge_never_uses_the_api():
    src = (VALIDATION / "judge_opus.py").read_text(encoding="utf-8")
    assert "import anthropic" not in src and "from anthropic" not in src
    assert '("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")' in src  # stripped from the CLI's environment


# --- end to end ------------------------------------------------------------------------------------

def test_analyse_end_to_end(tmp_path):
    import analyse

    ids = [f"p{i:03d}" for i in range(60)]
    sample = tmp_path / "sample.csv"
    rows = ["order,record_id,stratum,human"] + [f"{i + 1},{rid},S{i % 2},{1 if i < 40 else 0}" for i, rid in enumerate(ids)]
    sample.write_text("\n".join(rows) + "\n")
    config = json.loads((VALIDATION / "config.json").read_text())
    config.update(sample_path=str(sample), ratings_dir=str(tmp_path / "ratings"), results_dir=str(tmp_path / "results"),
                  bootstrap_reps=200)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config))
    cfg = common.load_config(cfg_path)
    rng = random.Random(0)
    for i, rid in enumerate(ids):
        for unit in common.UNIT_FIELDS:
            j = rng.choice(["correct"] * 8 + ["minor", "major"])
            common.append_rating("opus-5-5", "llm", rid, unit, j, [], "", ratings_dir=cfg["_ratings_dir"])
            if i < 40:
                h = j if rng.random() < 0.9 else rng.choice(["correct", "major", "unsure"])
                common.append_rating("gf", "human", rid, unit, h, [], "", ratings_dir=cfg["_ratings_dir"])
    summary = analyse.run(cfg)
    out = cfg["_results_dir"]
    for name in ("accuracy.csv", "agreement.csv", "confusion.csv", "error_codes.csv", "by_stratum.csv",
                 "ratings_long.csv", "to_adjudicate.csv", "report.html", "report.md", "summary.json",
                 "fig_accuracy.png", "fig_reliability.svg", "fig_confusion.png", "fig_errors.png"):
        assert (out / name).exists(), name
    assert summary["progress"]["human_done"] == 40
    pending = summary["progress"]["pending_adjudication"]
    assert summary["decision"]["status"] == ("NOT YET DECIDED" if pending else summary["decision"]["status"])
    # Adjudicate everything, then the decision is final.
    import pandas as pd
    for _, r in pd.read_csv(out / "to_adjudicate.csv").iterrows():
        common.append_rating("consensus", "consensus", r.record_id, r.unit, "correct", [], "",
                             ratings_dir=cfg["_ratings_dir"])
    final = analyse.run(cfg)
    assert final["progress"]["pending_adjudication"] == 0
    assert final["decision"]["status"] in ("GO", "NO-GO")
