"""Z.ai chat-completions client with the same `chat_completion()` signature as the vendored
`DeepSeekClient`, so the validated `enrich_records` loop runs on it unchanged.

What differs from DeepSeek, and why (https://docs.z.ai/api-reference/llm/chat-completion):

- Base URL `https://api.z.ai/api/paas/v4` -- the pay-as-you-go API. The GLM Coding Plan's endpoint
  is a different product and is never used here.
- GLM-5.3 and GLM-5.3-Flash think unconditionally (`thinking.type` can only be "enabled"); depth is
  a TOP-LEVEL `reasoning_effort`, defaulting to "max". DeepSeek's validated runs used its provider
  default, effort "high", so "high" is the default here: the same thinking budget, not Z.ai's.
- Usage reports cached prompt tokens as `prompt_tokens_details.cached_tokens`. `enrich_records`
  reads DeepSeek's `prompt_cache_hit_tokens`, so the response is normalised to carry that name too;
  otherwise every event would silently record a cache share of 0.
- Thinking at 16,000 output tokens can outlast DeepSeek's 60 s timeout, and a timed-out request
  may still be billed, so the default timeout is 300 s.

No tools are ever sent: `enable_search=True` raises rather than adding a key the validated
configuration never had.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

import glm_enrich  # noqa: F401 -- puts vendor/ on sys.path
from dome_triage.llm_classify.deepseek_client import (
    _RETRYABLE_NETWORK_EXCEPTIONS,
    DeepSeekResponse,
    create_session,
)

DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"

TIER_MODEL_IDS = {
    "glm-5.3-flash": "glm-5.3-flash",
    "glm-5.3": "glm-5.3",
}

DEFAULT_REASONING_EFFORT = "high"
REASONING_EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")


class ZaiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        max_retries: int = 8,
        backoff_factor: float = 1.0,
        timeout: float = 300.0,
        pool_maxsize: int = 50,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise ValueError("ZAI_API_KEY is empty -- see SETUP_ZAI.local.md")
        if reasoning_effort not in REASONING_EFFORT_LEVELS:
            raise ValueError(f"reasoning_effort must be one of {list(REASONING_EFFORT_LEVELS)}, got {reasoning_effort!r}")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout
        self.session = session if session is not None else create_session(max_retries, backoff_factor, pool_maxsize)

    def __repr__(self) -> str:  # never show the key
        return f"ZaiClient(base_url={self.base_url!r}, reasoning_effort={self.reasoning_effort!r})"

    def build_body(self, messages: list[dict], tier: str, max_tokens: int, temperature: float,
                   request_json_mode: bool) -> dict:
        if tier not in TIER_MODEL_IDS:
            raise ValueError(f"Unknown tier {tier!r} -- expected one of {list(TIER_MODEL_IDS)}")
        body: dict = {
            "model": TIER_MODEL_IDS[tier],
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "thinking": {"type": "enabled"},
            "reasoning_effort": self.reasoning_effort,
        }
        if request_json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def chat_completion(
        self,
        messages: list[dict],
        tier: str,
        max_tokens: int = 6000,
        temperature: float = 0.0,
        request_json_mode: bool = True,
        enable_search: bool = False,
        max_network_retries: int = 3,
        extra_body: Optional[dict] = None,
    ) -> DeepSeekResponse:
        if enable_search:
            raise ValueError("enable_search is never used for enrichment; no tools are sent")
        if extra_body:
            # The only extra_body enrich_records produces is DeepSeek's thinking shape for a
            # non-default effort. Z.ai's effort is set on the client, in Z.ai's own shape.
            raise ValueError("pass reasoning_effort to ZaiClient, not to enrich_records")
        body = self.build_body(messages, tier, max_tokens, temperature, request_json_mode)

        resp = None
        for attempt in range(max_network_retries + 1):
            try:
                resp = self.session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                    json=body,
                    timeout=self.timeout,
                )
                break
            except _RETRYABLE_NETWORK_EXCEPTIONS:
                if attempt >= max_network_retries:
                    raise
                time.sleep(2**attempt)

        if not resp.ok:
            raise requests.HTTPError(
                f"Z.ai API error {resp.status_code} for model={body['model']}: {resp.text[:2000]}",
                response=resp,
            )
        data = normalise_usage(resp.json())
        choice_wrapper = data["choices"][0]
        choice = choice_wrapper["message"]
        usage = data["usage"]
        return DeepSeekResponse(
            content=choice.get("content") or "",
            reasoning_content=choice.get("reasoning_content"),
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
            finish_reason=choice_wrapper.get("finish_reason"),
            raw=data,
        )

    def close(self) -> None:
        self.session.close()


def normalise_usage(data: dict) -> dict:
    """Adds DeepSeek's `prompt_cache_hit_tokens` from Z.ai's `prompt_tokens_details.cached_tokens`.
    `completion_tokens_details.reasoning_tokens` is passed through if Z.ai sends it; the spec does
    not document it, and if it is absent the events record 0 and the reports say so."""
    usage = dict(data.get("usage") or {})
    if "prompt_cache_hit_tokens" not in usage:
        usage["prompt_cache_hit_tokens"] = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    data["usage"] = usage
    return data
