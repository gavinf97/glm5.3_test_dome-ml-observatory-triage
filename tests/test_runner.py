import json
import threading

import pandas as pd
import pytest

import run_enrichment
from dome_triage.llm_classify.deepseek_client import DeepSeekResponse

ANSWER = {"domain_tier1": ["Biology"], "domain_tier2": [], "domain_tier3": [],
          "learning_paradigm": ["supervised classical machine learning"], "model_family": ["linear regression"],
          "model_type": [], "rationale": "test"}


class FakeClient:
    base_url = "https://example.invalid"

    def __init__(self, **kwargs):
        self.messages, self.extra_bodies = [], []
        self._lock = threading.Lock()

    def chat_completion(self, messages, tier, max_tokens=6000, extra_body=None, **kwargs):
        with self._lock:
            self.messages.append(messages)
            self.extra_bodies.append(extra_body)
        assert tier == "glm-5.3-flash" and max_tokens == 16000
        return DeepSeekResponse(content=json.dumps(ANSWER), reasoning_content=None, prompt_tokens=3000,
                                completion_tokens=800, total_tokens=3800, finish_reason="stop",
                                raw={"usage": {"prompt_cache_hit_tokens": 2500,
                                               "completion_tokens_details": {"reasoning_tokens": 700}}})

    def close(self):
        pass


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(run_enrichment, "REPO", tmp_path)
    monkeypatch.setattr(run_enrichment, "SPEND_LOG", tmp_path / "runs" / "spend_log.csv")
    path = tmp_path / "input.csv"
    pd.DataFrame([
        {"record_id": "a", "title": "Deep learning for X", "abstract": "We train a CNN.", "journal": "J1", "year": "2024"},
        {"record_id": "b", "title": "No journal", "abstract": "A random forest.", "journal": "", "year": "2023"},
        {"record_id": "c", "title": "Third", "abstract": "SVMs.", "journal": "J2", "year": ""},
    ]).to_csv(path, index=False)
    return tmp_path, path


def test_dry_run_spends_nothing(sandbox):
    tmp, path = sandbox
    calls = []
    assert run_enrichment.main(["--input", str(path), "--events-out", str(tmp / "ev.csv")],
                               client_factory=lambda **kw: calls.append(1)) == 0
    assert not calls and not (tmp / "ev.csv").exists()


def test_budget_gate_refuses(sandbox):
    tmp, path = sandbox
    assert run_enrichment.main(["--input", str(path), "--events-out", str(tmp / "ev.csv"), "--confirm",
                                "--max-usd", "0.0000001"], client_factory=FakeClient) == 1
    assert not (tmp / "ev.csv").exists()


def test_run_streams_events_resumes_and_keeps_production_quirks(sandbox):
    tmp, path = sandbox
    events = tmp / "ev.csv"
    client = FakeClient()
    assert run_enrichment.main(["--input", str(path), "--events-out", str(events), "--confirm"],
                               client_factory=lambda **kw: client) == 0
    df = pd.read_csv(events, dtype=str)
    assert sorted(df["record_id"]) == ["a", "b", "c"]
    assert set(df["model_tier"]) == {"glm-5.3-flash"} and set(df["prompt_version"]) == {"e1"}
    assert set(df["parse_status"]) == {"ok"} and set(df["cache_hit_tokens"]) == {"2500"}
    assert set(df["reasoning_tokens"]) == {"700"}
    # pd.read_csv(dtype=str) turns an empty journal into NaN, which the prompt prints as "nan" -- as in production
    users = {m[1]["content"].split("\n")[0]: m[1]["content"] for m in client.messages}
    assert "Journal: nan" in users["Title: No journal"]
    assert "Year: nan" in users["Title: Third"]
    assert all(b is None for b in client.extra_bodies)
    assert (tmp / "runs" / "spend_log.csv").exists()
    assert len(list((tmp / "runs").glob("*.manifest.json"))) == 1

    again = FakeClient()
    assert run_enrichment.main(["--input", str(path), "--events-out", str(events), "--confirm"],
                               client_factory=lambda **kw: again) == 0
    assert again.messages == []


def test_limit_takes_the_next_n(sandbox):
    tmp, path = sandbox
    events = tmp / "ev.csv"
    run_enrichment.main(["--input", str(path), "--events-out", str(events), "--confirm", "--limit", "2"],
                        client_factory=FakeClient)
    assert len(pd.read_csv(events)) == 2
    run_enrichment.main(["--input", str(path), "--events-out", str(events), "--confirm", "--limit", "2"],
                        client_factory=FakeClient)
    assert sorted(pd.read_csv(events, dtype=str)["record_id"]) == ["a", "b", "c"]
