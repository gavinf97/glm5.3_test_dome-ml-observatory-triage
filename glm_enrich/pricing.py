"""Z.ai list prices, USD per 1,000,000 tokens, read from https://docs.z.ai/guides/overview/pricing.

List price is a projection. What a run cost is the delta on the Z.ai billing page, recorded by hand
in runs/spend_log.csv (`billed_usd`).
"""

from __future__ import annotations

AS_OF = "2026-10-25"
SOURCE = "https://docs.z.ai/guides/overview/pricing"

PRICES = {
    "glm-5.3-flash": {"input_cache_hit": 0.03, "input_cache_miss": 0.15, "output": 0.50},
    "glm-5.3": {"input_cache_hit": 0.26, "input_cache_miss": 1.40, "output": 4.40},
}

# The e1 token profile measured on DeepSeek-V4.1-Flash, 200 records, 2026-09-15 (triage repo,
# pricing/token_profiles.yaml): cache hit / cache miss / output tokens per record. GLM's own profile
# replaces it after the smoke run.
E1_PROFILE = {"input_cache_hit": 2560, "input_cache_miss": 588, "output": 1481}

# GLM may think longer than DeepSeek did; the budget gate projects at this multiple of the profile.
HEADROOM = 3.0


def usd(model: str, cache_hit: float, cache_miss: float, output: float) -> float:
    p = PRICES[model]
    return (cache_hit * p["input_cache_hit"] + cache_miss * p["input_cache_miss"] + output * p["output"]) / 1e6


def projected_usd(model: str, n_records: int, headroom: float = HEADROOM) -> float:
    per_record = usd(model, E1_PROFILE["input_cache_hit"], E1_PROFILE["input_cache_miss"], E1_PROFILE["output"])
    return n_records * per_record * headroom
