import json

import pytest
import requests

from glm_enrich import EXPECTED_VOCAB_SHA256, RENDERED_PROMPT, triage_repo
from glm_enrich.fidelity import problems, render
from glm_enrich.zai_client import ZaiClient, normalise_usage
from dome_triage.llm_classify import enrichment

FAKE_KEY = "0" * 32 + "." + "A" * 16


def test_vendored_files_and_render_are_e1():
    assert problems(None) == []
    text, _, _ = render()
    assert enrichment.vocab_sha256(text) == EXPECTED_VOCAB_SHA256
    assert text.encode("utf-8") == RENDERED_PROMPT.read_bytes()


def test_vendored_files_match_triage_repo():
    triage = triage_repo()
    if not triage.exists():
        pytest.skip("triage repository not checked out beside this one")
    assert problems(triage) == []


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text
        self.ok = 200 <= status < 300

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response, self.calls = response, []

    def post(self, url, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.response

    def close(self):
        pass


def ok_payload():
    return {"model": "glm-5.3-flash",
            "choices": [{"message": {"content": "{}", "reasoning_content": "thinking"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3000, "completion_tokens": 900, "total_tokens": 3900,
                      "prompt_tokens_details": {"cached_tokens": 2500}}}


def test_request_body_matches_validated_configuration():
    session = FakeSession(FakeResponse(payload=ok_payload()))
    client = ZaiClient(FAKE_KEY, session=session)
    text, _, _ = render()
    messages = enrichment.build_enrichment_prompt({"title": "T", "abstract": "A", "journal": "J", "year": "2024"}, text)
    response = client.chat_completion(messages, tier="glm-5.3-flash", max_tokens=enrichment.ENRICHMENT_MAX_TOKENS)
    call = session.calls[0]
    body = call["json"]
    assert call["url"] == "https://api.z.ai/api/paas/v4/chat/completions"
    assert body["model"] == "glm-5.3-flash"
    assert body["messages"] == messages and body["messages"][0]["content"] == text
    assert body["max_tokens"] == 16000 and body["temperature"] == 0.0
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "enabled"} and body["reasoning_effort"] == "high"
    assert "tools" not in body
    assert call["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    # normalised so enrich_records records the cache share
    assert response.raw["usage"]["prompt_cache_hit_tokens"] == 2500
    assert response.prompt_tokens == 3000 and response.finish_reason == "stop"


def test_client_refuses_anything_outside_the_validated_shape():
    client = ZaiClient(FAKE_KEY, session=FakeSession(FakeResponse(payload=ok_payload())))
    with pytest.raises(ValueError):
        client.chat_completion([], tier="glm-5.3-flash", enable_search=True)
    with pytest.raises(ValueError):
        client.chat_completion([], tier="glm-5.3-flash", extra_body={"thinking": {"type": "disabled"}})
    with pytest.raises(ValueError):
        client.chat_completion([], tier="flash")
    with pytest.raises(ValueError):
        ZaiClient("")
    assert FAKE_KEY not in repr(client)


def test_http_error_does_not_echo_the_key():
    client = ZaiClient(FAKE_KEY, session=FakeSession(FakeResponse(status=400, text='{"error":"bad"}')))
    with pytest.raises(requests.HTTPError) as exc:
        client.chat_completion([], tier="glm-5.3-flash")
    assert FAKE_KEY not in str(exc.value)


def test_normalise_usage_without_cache_details():
    data = normalise_usage({"usage": {"prompt_tokens": 10}})
    assert data["usage"]["prompt_cache_hit_tokens"] == 0
    assert json.dumps(data)
