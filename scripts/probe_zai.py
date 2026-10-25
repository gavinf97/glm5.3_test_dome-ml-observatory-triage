#!/usr/bin/env python3
"""One tiny paid call (well under $0.001) to confirm, before any cohort run, that Z.ai accepts the exact
request shape the runner sends and to show which usage fields come back.

It checks that temperature 0.0, `thinking.type=enabled`, top-level `reasoning_effort`,
`response_format=json_object` and `max_tokens` are all accepted, prints the usage keys (cached and
reasoning token fields), and prints whether `reasoning_content` is returned. The prompt is a
trivial JSON echo, not e1.

    python3 scripts/probe_zai.py --confirm
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glm_enrich import load_env  # noqa: E402
from glm_enrich.zai_client import DEFAULT_REASONING_EFFORT, TIER_MODEL_IDS, ZaiClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tier", default="glm-5.3-flash", choices=sorted(TIER_MODEL_IDS))
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        print("one paid call (well under $0.001): pass --confirm")
        return 0
    key = load_env().get("ZAI_API_KEY", "")
    if not key:
        print("ZAI_API_KEY is not set in .env -- see SETUP_ZAI.local.md.")
        return 1

    client = ZaiClient(key, reasoning_effort=args.reasoning_effort, max_retries=2)
    messages = [
        {"role": "system", "content": 'Answer with a JSON object only: {"ok": true, "n": <the number given>}.'},
        {"role": "user", "content": "The number is 7."},
    ]
    try:
        response = client.chat_completion(messages, tier=args.tier, max_tokens=2000)
    finally:
        client.close()

    raw = response.raw
    usage = raw.get("usage", {})
    print(f"model echoed:        {raw.get('model')}")
    print(f"finish_reason:       {response.finish_reason}")
    print(f"content:             {response.content[:200]!r}")
    print(f"reasoning_content:   {'present, ' + str(len(response.reasoning_content)) + ' chars' if response.reasoning_content else 'absent'}")
    print(f"usage:               {json.dumps(usage, sort_keys=True)}")
    details = usage.get("completion_tokens_details") or {}
    print(f"reasoning_tokens:    {details.get('reasoning_tokens', 'NOT REPORTED -- events will record 0')}")
    print(f"cached tokens field: {'prompt_tokens_details.cached_tokens' if 'prompt_tokens_details' in usage else 'absent (cache share will read 0)'}")
    try:
        ok = json.loads(response.content).get("n") == 7
    except (json.JSONDecodeError, AttributeError):
        ok = False
    print("probe: OK" if ok else "probe: the answer was not the expected JSON -- look before running a cohort")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
