"""The EXPERIMENTAL e2 prompt: frozen, additive over e1, provenance on every change, and post-processing
that logs everything it does."""

import importlib.util
import json
import threading

import pandas as pd

import run_enrichment
from glm_enrich import CRITERIA_DIR, REPO, e2
from glm_enrich.fidelity import render as render_e1
from dome_triage.llm_classify import enrichment as e1
from dome_triage.llm_classify.deepseek_client import DeepSeekResponse

_spec = importlib.util.spec_from_file_location("build_vocab", REPO / "experimental" / "e2" / "build_vocab.py")
build_vocab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_vocab)


def lookup():
    return e2.render_e2()[2]


def test_e2_is_frozen_and_e1_untouched():
    assert e2.e2_problems() == []
    text, _, _ = render_e1()
    assert e1.vocab_sha256(text) == "41db952f15118176fa27dac724eff9dff59714b62854859d9606ef440ee473c7"


def test_vocab_files_match_a_fresh_build():
    e1_branch = json.loads((CRITERIA_DIR / "modelling_branch_vocab.json").read_text())
    e1_seed = json.loads((CRITERIA_DIR / "model_type_seed_vocab.json").read_text())
    assert e2.E2_BRANCH.read_text() == build_vocab.dumps(build_vocab.build_branch(e1_branch))
    assert e2.E2_SEED.read_text() == build_vocab.dumps(build_vocab.build_seed(e1_seed))


def test_e2_is_additive_and_every_change_has_provenance():
    e1_branch = json.loads((CRITERIA_DIR / "modelling_branch_vocab.json").read_text())["fields"]
    e1_seed = json.loads((CRITERIA_DIR / "model_type_seed_vocab.json").read_text())["terms"]
    branch = json.loads(e2.E2_BRANCH.read_text())["fields"]
    seed = json.loads(e2.E2_SEED.read_text())["terms"]
    for field in ("learning_paradigm", "model_family"):
        old = {t["label"] for t in e1_branch[field]["terms"]}
        new = {t["label"]: t for t in branch[field]["terms"]}
        assert old <= set(new) and branch[field]["max_tags"] == e1_branch[field]["max_tags"]
        for label in set(new) - old:
            assert new[label]["extension"] == "e2-experimental"
            assert new[label]["provenance"].startswith("experimental/e2/PROVENANCE.md#e2-v")
    assert all(t["extension"] == "e2-experimental" for t in branch["model_use"]["terms"])
    by = {t["canonical"]: t for t in seed}
    for t in e1_seed:
        assert set(t["aliases"]) <= set(by[t["canonical"]]["aliases"])
        assert by[t["canonical"]]["family_hint"] == t["family_hint"]
    for t in seed:
        if t["canonical"] not in {x["canonical"] for x in e1_seed}:
            assert t["provenance"].endswith("#e2-v9")
    provenance = e2.PROVENANCE.read_text()
    for change in [f"E2-V{i}" for i in range(1, 10)] + [f"E2-P{i}" for i in range(1, 7)] + ["E2-PP1", "E2-PP2", "E2-PP3"]:
        assert change in provenance


def test_user_message_is_e1s():
    record = {"record_id": "x", "title": "T", "abstract": "A", "journal": "J", "year": "2024", "label": "secret"}
    e1_text, _, _ = render_e1()
    e2_text, _, _ = e2.render_e2()
    assert e1.build_enrichment_prompt(record, e1_text)[1] == e1.build_enrichment_prompt(record, e2_text)[1]
    assert "secret" not in json.dumps(e1.build_enrichment_prompt(record, e2_text))


def answer(**fields):
    base = {"domain_tier1": [], "domain_tier2": [], "domain_tier3": [], "model_use": ["trained in this study"],
            "learning_paradigm": ["supervised"], "model_family": [], "model_type": [], "rationale": "r"}
    return json.dumps({**base, **fields})


def test_family_backfill_is_logged_and_respects_the_cap():
    out = e2.parse_e2(answer(model_family=["classical machine learning"], model_type=["RF", "PCA"]), lookup())
    assert out["model_type"] == ["random forest", "principal component analysis"]
    assert out["model_family"] == ["classical machine learning", "ensemble learning", "dimensionality reduction"]
    assert out["family_backfilled"] == ["ensemble learning<-random forest", "dimensionality reduction<-principal component analysis"]

    full = e2.parse_e2(answer(model_family=["deep learning", "transfer learning", "classical machine learning"],
                              model_type=["XGBoost"]), lookup())
    assert full["model_family"] == ["deep learning", "transfer learning", "classical machine learning"]
    assert full["family_backfilled"] == ["skipped_cap:ensemble learning<-XGBoost"]


def test_ambiguous_and_non_family_hints_are_never_backfilled():
    out = e2.parse_e2(answer(model_type=["ANN", "PPO"]), lookup())
    assert out["model_type"] == ["neural network", "policy gradient"]
    assert out["model_family"] == [] and out["family_backfilled"] == []


def test_paradigm_repair_and_model_use_are_logged():
    out = e2.parse_e2(answer(learning_paradigm=["reinforcement learning"], model_use=["trained here"]), lookup())
    assert out["learning_paradigm"] == ["reinforcement"]
    assert "learning_paradigm:repaired:reinforcement learning->reinforcement" in out["vocab_violations"]
    assert not any(v.startswith("learning_paradigm:unknown") for v in out["vocab_violations"])
    assert out["model_use"] == ["trained here"] and "model_use:unknown:trained here" in out["vocab_violations"]
    ok = e2.parse_e2(answer(learning_paradigm=["self-supervised", "supervised"], model_use=["prompted (zero/few-shot)"]), lookup())
    assert ok["vocab_violations"] == [] and ok["model_use"] == ["prompted (zero/few-shot)"]


def test_excluded_kinds_are_flagged_not_dropped():
    out = e2.parse_e2(answer(model_type=["SHAP", "WGCNA", "molecular docking", "deep learning", "random forest",
                                         "particle swarm optimization"]), lookup())
    assert out["model_type"][0] == "SHAP" and len(out["model_type"]) == 6
    kinds = sorted(v.split(":")[2] for v in out["vocab_violations"] if v.startswith("model_type:excluded_kind"))
    assert kinds == ["explainability", "family_name", "optimiser_check", "pipeline", "simulation"]


class FakeClient:
    base_url = "https://example.invalid"

    def __init__(self, **kwargs):
        self.messages = []
        self._lock = threading.Lock()

    def chat_completion(self, messages, tier, max_tokens=6000, extra_body=None, **kwargs):
        with self._lock:
            self.messages.append(messages)
        return DeepSeekResponse(content=answer(model_type=["XGBoost"]), reasoning_content=None, prompt_tokens=6000,
                                completion_tokens=500, total_tokens=6500, finish_reason="stop",
                                raw={"usage": {"prompt_cache_hit_tokens": 5000, "completion_tokens_details": {"reasoning_tokens": 300}}})

    def close(self):
        pass


def test_runner_e2_writes_its_own_log_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(run_enrichment, "REPO", tmp_path)
    monkeypatch.setattr(run_enrichment, "SPEND_LOG", tmp_path / "runs" / "spend_log.csv")
    path = tmp_path / "input.csv"
    pd.DataFrame([{"record_id": "a", "title": "T", "abstract": "XGBoost.", "journal": "J", "year": "2024"}]).to_csv(path, index=False)
    events = tmp_path / "runs" / "e2" / "ev.csv"
    client = FakeClient()
    assert run_enrichment.main(["--input", str(path), "--events-out", str(events), "--confirm", "--prompt", "e2"],
                               client_factory=lambda **kw: client) == 0
    df = pd.read_csv(events, dtype=str)
    assert list(df.columns) == e2.E2_EVENT_COLUMNS
    assert df.loc[0, "prompt_version"] == "e2-exp" and df.loc[0, "vocab_sha256"] == e2.EXPECTED_E2_SHA256
    assert json.loads(df.loc[0, "model_family"]) == ["classical machine learning", "ensemble learning"]
    assert json.loads(df.loc[0, "model_use"]) == ["trained in this study"]
    assert client.messages[0][0]["content"] == e2.E2_RENDERED.read_text()
    manifest = json.loads(next((tmp_path / "runs").glob("*.manifest.json")).read_text())
    assert manifest["prompt_version"] == "e2-exp" and "experimental" in manifest
    again = FakeClient()
    assert run_enrichment.main(["--input", str(path), "--events-out", str(events), "--confirm", "--prompt", "e2"],
                               client_factory=lambda **kw: again) == 0
    assert again.messages == []
