#!/usr/bin/env python3
"""Second rater: Claude Opus 5.5 rates every sampled paper with the same rubric as the human.

It runs through the Claude Code CLI (`claude -p`) on your normal subscription. It never uses the
Anthropic API: there is no SDK import, and ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN are removed from
the CLI's environment so nothing can fall back to API billing. Each paper is one fresh, tool-less,
single-turn call, run in an empty temporary directory so no project files, CLAUDE.md or memory load.

    python3 validation/judge_opus.py                     # shows what it would do; no calls
    python3 validation/judge_opus.py --limit 5 --confirm # rate 5 papers
    python3 validation/judge_opus.py --confirm           # rate the rest; re-run to resume

Ratings append to validation/ratings/opus-5-5.csv. If the plan's usage limit is reached it stops
cleanly; run it again later and it carries on where it stopped.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CONFIG_PATH, ERROR_CODES, UNIT_FIELDS, VERDICTS, append_rating, latest_ratings,  # noqa: E402
                    load_config, load_items, load_sample, rater_instructions, sha256_text, tagger_prompt)

UNITS = list(UNIT_FIELDS)
TIMEOUT_S = 300
LIMIT_MARKERS = ("usage limit", "rate limit", "limit reached", "rate_limit", "overloaded", "429", "quota")


class UsageLimit(Exception):
    pass


def find_cli(explicit: str | None) -> str:
    if explicit:
        return explicit
    found = shutil.which("claude")
    if found:
        return found
    # The VS Code extension ships the CLI; take the newest installed version.
    candidates = sorted(glob.glob(os.path.expanduser(
        "~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude")))
    if candidates:
        return candidates[-1]
    raise SystemExit("Claude Code CLI not found. Pass --cli /path/to/claude.")


def schema() -> dict:
    unit = {"type": "object", "additionalProperties": False, "required": ["verdict", "error_codes", "reason"],
            "properties": {"verdict": {"type": "string", "enum": list(VERDICTS)},
                           "error_codes": {"type": "array", "items": {"type": "string", "enum": list(ERROR_CODES)}},
                           "reason": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": UNITS,
            "properties": {u: unit for u in UNITS}}


def system_prompt() -> str:
    return ("You are an expert curator of machine-learning metadata for biomedical literature, acting as an "
            "independent rater. You have no tools. Judge only from the paper text you are given.\n\n"
            + rater_instructions()
            + "\n\n=== THE INSTRUCTIONS THE TAGGER WAS GIVEN (vocabularies, caps and tagging rules) ===\n\n"
            + tagger_prompt())


def user_prompt(item: dict) -> str:
    tags = {u: {f: item["tags"][f] for f in fields} if len(fields) > 1 else item["tags"][fields[0]]
            for u, fields in UNIT_FIELDS.items()}
    return ("Rate the tags below for this paper. Read the title and abstract first and decide what you would tag, "
            "then compare.\n\n"
            f"Title: {item['title']}\n\nAbstract: {item['abstract']}\n\nJournal: {item['journal']}\nYear: {item['year']}\n\n"
            f"Tags to rate (JSON):\n{json.dumps(tags, ensure_ascii=False, indent=2)}\n\n"
            "Give, for each of the five units (domain, learning_paradigm, model_family, model_type, model_use), "
            "a verdict (correct, minor, major or unsure), the error codes that apply (empty for correct), and one "
            "short sentence of reason.")


def validate(obj) -> dict:
    """Strict check of the judge's answer; raises ValueError if anything is off."""
    if not isinstance(obj, dict):
        raise ValueError("answer is not a JSON object")
    out = {}
    for unit in UNITS:
        v = obj.get(unit)
        if not isinstance(v, dict):
            raise ValueError(f"missing unit {unit}")
        verdict = v.get("verdict")
        codes = v.get("error_codes", [])
        if verdict not in VERDICTS:
            raise ValueError(f"{unit}: bad verdict {verdict!r}")
        if not isinstance(codes, list) or any(c not in ERROR_CODES for c in codes):
            raise ValueError(f"{unit}: bad error codes {codes!r}")
        out[unit] = {"verdict": verdict, "error_codes": codes if verdict in ("minor", "major") else [],
                     "reason": str(v.get("reason", ""))[:2000]}
    return out


def parse_envelope(stdout: str, want_model: str) -> tuple[dict, dict]:
    """Return (validated answer, run info) from the CLI's --output-format json envelope."""
    text = stdout.strip()
    try:
        env = json.loads(text)
    except json.JSONDecodeError:
        if any(m in text.lower() for m in LIMIT_MARKERS):
            raise UsageLimit(text[:300])
        raise ValueError(f"CLI output is not JSON: {text[:200]!r}")
    if env.get("is_error") or env.get("subtype") not in (None, "success"):
        msg = json.dumps({k: env.get(k) for k in ("subtype", "result", "api_error_status")})
        if any(m in msg.lower() for m in LIMIT_MARKERS):
            raise UsageLimit(msg[:300])
        raise ValueError(f"CLI reported an error: {msg[:300]}")
    models = list((env.get("modelUsage") or {}).keys())
    if want_model not in models:
        raise ValueError(f"answer did not come from {want_model} (models used: {models})")
    answer = env.get("structured_output")
    if answer is None:
        result = env.get("result") or ""
        start, end = result.find("{"), result.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no JSON object in the answer")
        answer = json.loads(result[start:end + 1])
    info = {"session_id": env.get("session_id"), "models": models, "duration_ms": env.get("duration_ms"),
            "num_turns": env.get("num_turns")}
    return validate(answer), info


def call_cli(cli: str, model: str, effort: str, system: str, user: str) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    cmd = [cli, "-p", "--model", model, "--effort", effort, "--output-format", "json",
           "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
           "--system-prompt", system, "--json-schema", json.dumps(schema())]
    with tempfile.TemporaryDirectory(prefix="judge_") as empty:
        proc = subprocess.run(cmd, input=user, capture_output=True, text=True, cwd=empty, env=env, timeout=TIMEOUT_S)
    if proc.returncode != 0 and not proc.stdout.strip():
        err = (proc.stderr or "")[:300]
        if any(m in err.lower() for m in LIMIT_MARKERS):
            raise UsageLimit(err)
        raise ValueError(f"CLI exited {proc.returncode}: {err}")
    return proc.stdout


def judge_one(item: dict, cli: str, config: dict, system: str) -> tuple[dict, dict]:
    last = None
    for _ in range(2):  # one retry on an invalid answer
        try:
            out = call_cli(cli, config["judge_model"], config.get("judge_effort", "high"), system, user_prompt(item))
            return parse_envelope(out, config["judge_model"])
        except UsageLimit:
            raise
        except (ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            last = exc
    answer = {u: {"verdict": "unsure", "error_codes": [], "reason": f"JUDGE FAILED: {last}"} for u in UNITS}
    return answer, {"failed": str(last)}


def cli_version(cli: str) -> str:
    try:
        return subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--limit", type=int, help="Rate at most this many papers in this run.")
    parser.add_argument("--workers", type=int, default=1, choices=(1, 2))
    parser.add_argument("--cli", help="Path to the claude CLI (found automatically otherwise).")
    parser.add_argument("--confirm", action="store_true", help="Actually call the CLI.")
    args = parser.parse_args()

    config = load_config(args.config)
    rater = config["judge_rater_id"]
    rdir = config["_ratings_dir"]
    items = load_items(config, load_sample(config["_sample_path"]))
    done = latest_ratings(rater, rdir)
    todo = [it for it in items if not all((it["record_id"], u) in done for u in UNITS)]
    # Human-rated papers first, so the primary analysis set is complete as early as possible.
    todo.sort(key=lambda it: (not it["human"], it["order"]))
    n_remaining = len(todo)
    if args.limit:
        todo = todo[: args.limit]
    instructions_sha = sha256_text(rater_instructions())
    print(f"judge {config['judge_model']} (effort {config.get('judge_effort', 'high')}) via Claude Code CLI, "
          f"subscription only\n  {len(items)} papers in sample, {len(items) - n_remaining} already rated, "
          f"{n_remaining} remaining, {len(todo)} in this run\n  rubric sha256 {instructions_sha[:12]}…")
    if not todo:
        print("Nothing to do.")
        return 0
    if not args.confirm:
        print("Dry run: add --confirm to rate them.")
        return 0

    cli = find_cli(args.cli)
    system = system_prompt()
    started = datetime.now(timezone.utc)
    t0 = time.time()
    n_ok = n_failed = 0
    stopped = None

    def work(item):
        return item, *judge_one(item, cli, config, system)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        queue = iter(todo)
        for item in [next(queue, None) for _ in range(args.workers)]:
            if item:
                futures[pool.submit(work, item)] = item
        while futures:
            fut = next(concurrent.futures.as_completed(futures))
            futures.pop(fut)
            try:
                item, answer, info = fut.result()
            except UsageLimit as exc:
                stopped = str(exc)
                break
            for unit, a in answer.items():
                append_rating(rater, "llm", item["record_id"], unit, a["verdict"], a["error_codes"], a["reason"],
                              ratings_dir=rdir)
            n_failed += "failed" in info
            n_ok += "failed" not in info
            print(f"  [{n_ok + n_failed}/{len(todo)}] {item['record_id'][:8]} "
                  + " ".join(f"{u[:6]}={a['verdict']}" for u, a in answer.items()) + (" (FAILED)" if "failed" in info else ""))
            nxt = next(queue, None) if not stopped else None
            if nxt:
                futures[pool.submit(work, nxt)] = nxt
        for fut in futures:
            fut.cancel()

    manifest = {"started_utc": started.isoformat(), "wall_seconds": round(time.time() - t0, 1),
                "judge_model": config["judge_model"], "effort": config.get("judge_effort", "high"),
                "via": "claude-code-cli", "cli": cli_version(cli), "rubric_instructions_sha256": instructions_sha,
                "tagger_prompt_sha256": sha256_text(tagger_prompt()), "papers_rated": n_ok, "papers_failed": n_failed,
                "stopped_on_usage_limit": stopped}
    out = config["_results_dir"] / f"judge_run_{started.strftime('%Y%m%dT%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nrated {n_ok}, failed {n_failed} (recorded as unsure); manifest {out.name}")
    if stopped:
        print(f"STOPPED: the plan's usage limit was reached ({stopped[:120]}). Run the same command again later to resume.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
