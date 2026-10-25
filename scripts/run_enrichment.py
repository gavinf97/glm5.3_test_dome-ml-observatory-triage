#!/usr/bin/env python3
"""Run the validated e1 enrichment over one cohort on Z.ai GLM. Costs money.

Mirrors the triage repo's `step_llm_classify_enrich`: the input is read with
`pd.read_csv(dtype=str)` (so an empty journal reaches the prompt as `Journal: nan`, exactly as in
production), the vendored `enrich_records` builds every prompt and parses every answer, each event
streams to disk the moment it completes, and re-running the same command resumes for free.

Without --confirm this prints what it would do and spends nothing.

    python3 scripts/run_enrichment.py --cohort wave1 --limit 25            # dry run
    python3 scripts/run_enrichment.py --cohort wave1 --limit 25 --confirm  # smoke run
    python3 scripts/run_enrichment.py --cohort wave1 --confirm             # the rest of the cohort
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import fcntl
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from glm_enrich import COHORTS, EXPECTED_VOCAB_SHA256, REPO, load_env, triage_repo  # noqa: E402
from glm_enrich import pricing  # noqa: E402
from glm_enrich.fidelity import manifest_sha256, problems, render  # noqa: E402
from glm_enrich.zai_client import DEFAULT_BASE_URL, DEFAULT_REASONING_EFFORT, TIER_MODEL_IDS, ZaiClient  # noqa: E402
from dome_triage.llm_classify import enrichment as llm_enrichment  # noqa: E402

SPEND_LOG = REPO / "runs" / "spend_log.csv"
SPEND_COLUMNS = ["batch_id", "started_utc", "cohort", "model", "reasoning_effort", "records",
                 "input_tokens", "cache_hit_tokens", "output_tokens", "reasoning_tokens",
                 "list_usd", "billed_usd", "wall_seconds", "records_per_min", "concurrency"]


@contextlib.contextmanager
def events_file_lock(events_path: Path, ignore_lock: bool = False):
    """One writer per event log, held for the run (the triage repo's `_events_file_lock`): a second
    process cannot take it and exits before spending anything."""
    lock_path = events_path.with_suffix(events_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.seek(0)
            holder = handle.read().strip() or "(holder wrote no details)"
            if not ignore_lock:
                raise SystemExit(f"{events_path.name} is already being written by another run: {holder}. "
                                 f"Refusing to start -- two processes on one log pay twice.")
            print(f"--ignore-lock: proceeding despite the lock held by {holder}.")
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()} host={socket.gethostname()} started={datetime.now(timezone.utc).isoformat()}\n")
        handle.flush()
        yield
    finally:
        handle.close()


def stream_events_to_disk(events_path: Path, event_iterator, columns: list[str]) -> int:
    """Each event is on disk before the next is awaited (the triage repo's
    `_stream_classify_events_to_disk`), so a crash loses only the in-flight calls."""
    events_path.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    for event in event_iterator:
        pd.DataFrame([event], columns=columns).to_csv(events_path, mode="a", header=not events_path.exists(), index=False)
        n_written += 1
    return n_written


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return path.name


def append_spend(row: dict) -> None:
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not SPEND_LOG.exists()
    with SPEND_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SPEND_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def main(argv: Optional[list[str]] = None, client_factory: Optional[Callable[..., object]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cohort", choices=sorted(COHORTS), help="Sets --input and --events-out from glm_enrich.COHORTS.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--events-out", type=Path)
    parser.add_argument("--tier", default="glm-5.3-flash", choices=sorted(TIER_MODEL_IDS))
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-usd", type=float, default=3.0,
                        help=f"Refuse when the projection (list price x {pricing.HEADROOM:g} headroom) exceeds this.")
    parser.add_argument("--confirm", action="store_true", help="Actually call the API. Without it, nothing is spent.")
    parser.add_argument("--retry-truncated", action="store_true")
    parser.add_argument("--ignore-lock", action="store_true")
    args = parser.parse_args(argv)

    if args.cohort:
        args.input = args.input or REPO / COHORTS[args.cohort]["input"]
        args.events_out = args.events_out or REPO / COHORTS[args.cohort]["events"]
    if not args.input or not args.events_out:
        parser.error("--input and --events-out are both required (or --cohort)")

    found = problems(triage_repo())
    if found:
        print("REFUSING: the vendored e1 enrichment is not intact:\n  " + "\n  ".join(found))
        return 1

    if not args.input.exists():
        print(f"{rel(args.input)} does not exist -- run scripts/export_cohorts.py first.")
        return 1
    records = pd.read_csv(args.input, dtype=str)
    static_system_text, _, lookup = render()
    vocab_hash = llm_enrichment.vocab_sha256(static_system_text)
    assert vocab_hash == EXPECTED_VOCAB_SHA256

    events_path = args.events_out
    existing_events = (pd.read_csv(events_path, dtype=str) if events_path.exists()
                       else pd.DataFrame(columns=llm_enrichment.EVENT_COLUMNS))
    if not existing_events.empty:
        existing_events["parse_status"] = existing_events["parse_status"].fillna("")

    if args.limit is not None:
        done = llm_enrichment._already_enriched_ids(existing_events, args.tier, vocab_hash)
        remaining = records[~records["record_id"].isin(done)]
        records = pd.concat([records[records["record_id"].isin(done)], remaining.head(args.limit)])

    done = llm_enrichment._already_enriched_ids(existing_events, args.tier, vocab_hash, args.retry_truncated)
    n_todo = int((~records["record_id"].isin(done)).sum())
    projection = pricing.projected_usd(args.tier, n_todo)
    print(f"{n_todo:,} record(s) to enrich from {rel(args.input)} -> {rel(events_path)}\n"
          f"  model {TIER_MODEL_IDS[args.tier]}, reasoning_effort {args.reasoning_effort}, concurrency {args.concurrency}\n"
          f"  projected ${projection:.2f} (list price x {pricing.HEADROOM:g} headroom on the e1 token profile; "
          f"prices as of {pricing.AS_OF}), cap ${args.max_usd:.2f}")
    if n_todo == 0:
        print("nothing to do")
        return 0
    if projection > args.max_usd:
        print(f"REFUSING: projection ${projection:.2f} exceeds --max-usd ${args.max_usd:.2f}.")
        return 1
    if not args.confirm:
        print("dry run: pass --confirm to call the API.")
        return 0

    api_key = load_env().get("ZAI_API_KEY", "")
    if client_factory is None:
        if not api_key:
            print("ZAI_API_KEY is not set in .env -- see SETUP_ZAI.local.md.")
            return 1
        client = ZaiClient(api_key, reasoning_effort=args.reasoning_effort, pool_maxsize=max(50, args.concurrency))
    else:
        client = client_factory(reasoning_effort=args.reasoning_effort)

    started = datetime.now(timezone.utc)
    batch_id = f"enrich_{args.tier}_{started.strftime('%Y%m%dT%H%M%S')}"
    manifest_path = REPO / "runs" / f"{batch_id}.manifest.json"
    manifest = {
        "batch_id": batch_id, "cohort": args.cohort, "started_utc": started.isoformat(),
        "model": TIER_MODEL_IDS[args.tier], "base_url": getattr(client, "base_url", DEFAULT_BASE_URL),
        "reasoning_effort": args.reasoning_effort, "temperature": 0.0,
        "max_tokens": llm_enrichment.ENRICHMENT_MAX_TOKENS, "response_format": "json_object",
        "prompt_version": llm_enrichment.ENRICHMENT_PROMPT_VERSION, "vocab_sha256": vocab_hash,
        "vendor_manifest_sha256": manifest_sha256(), "git_commit": git_commit(),
        "input": rel(args.input), "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "events": rel(events_path), "concurrency": args.concurrency, "limit": args.limit,
        "records_to_do": n_todo, "projected_usd": round(projection, 4),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    t0 = time.monotonic()
    n_written = 0
    try:
        with events_file_lock(events_path, ignore_lock=args.ignore_lock):
            n_written = stream_events_to_disk(
                events_path,
                llm_enrichment.enrich_records(
                    records, args.tier, client, static_system_text, lookup, batch_id,
                    existing_events=existing_events, max_workers=args.concurrency,
                    reasoning_effort=None, retry_truncated=args.retry_truncated,
                ),
                columns=llm_enrichment.EVENT_COLUMNS,
            )
    except BaseException:
        print(f"CRASHED after {n_written} record(s) safely written to {rel(events_path)}. "
              "Re-run the same command to resume; finished records are skipped.")
        raise
    finally:
        client.close()
        wall = time.monotonic() - t0
        summarise(events_path, batch_id, manifest, manifest_path, n_written, wall, args)
    return 0


def summarise(events_path: Path, batch_id: str, manifest: dict, manifest_path: Path, n_written: int,
              wall: float, args) -> None:
    if not events_path.exists():
        return
    batch = pd.read_csv(events_path, dtype=str)
    batch = batch[batch["batch_id"] == batch_id]
    num = lambda col: int(pd.to_numeric(batch[col], errors="coerce").fillna(0).sum())  # noqa: E731
    tokens_in, cached, out, reasoning = num("input_tokens"), num("cache_hit_tokens"), num("output_tokens"), num("reasoning_tokens")
    list_usd = pricing.usd(args.tier, cached, tokens_in - cached, out)
    n_parse_error = int((batch["parse_status"] == llm_enrichment.PARSE_ERROR).sum())
    n_truncated = int((batch["finish_reason"] == "length").sum())
    n_violating = int((batch["vocab_violations"].fillna("[]") != "[]").sum())
    per_min = n_written / wall * 60 if wall else 0.0
    print(f"\n{n_written} record(s) enriched in {wall / 60:.1f} min ({per_min:.0f}/min at concurrency {args.concurrency}); "
          f"{n_parse_error} parse_error, {n_truncated} truncated at {llm_enrichment.ENRICHMENT_MAX_TOKENS:,}, "
          f"{n_violating} with a vocabulary violation")
    print(f"tokens: {tokens_in:,} in ({cached / tokens_in * 100 if tokens_in else 0:.0f}% cached) / {out:,} out"
          f"{f', {reasoning:,} reported as reasoning' if reasoning else ' (Z.ai reported no reasoning-token count)'}")
    print(f"list price: ${list_usd:.4f}. Read the billed figure off https://z.ai/manage-apikey/billing "
          f"and put it in runs/spend_log.csv (billed_usd).")
    manifest.update({"finished_utc": datetime.now(timezone.utc).isoformat(), "records_written": n_written,
                     "parse_errors": n_parse_error, "truncated": n_truncated, "vocab_violating_records": n_violating,
                     "input_tokens": tokens_in, "cache_hit_tokens": cached, "output_tokens": out,
                     "reasoning_tokens": reasoning, "list_usd": round(list_usd, 6), "wall_seconds": round(wall, 1)})
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if n_written:
        append_spend({"batch_id": batch_id, "started_utc": manifest["started_utc"], "cohort": args.cohort or "",
                      "model": manifest["model"], "reasoning_effort": args.reasoning_effort, "records": n_written,
                      "input_tokens": tokens_in, "cache_hit_tokens": cached, "output_tokens": out,
                      "reasoning_tokens": reasoning, "list_usd": f"{list_usd:.6f}", "billed_usd": "",
                      "wall_seconds": f"{wall:.1f}", "records_per_min": f"{per_min:.1f}",
                      "concurrency": args.concurrency})


if __name__ == "__main__":
    sys.exit(main())
