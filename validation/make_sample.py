#!/usr/bin/env python3
"""Draw the validation sample, once, before any rating.

Every record of the cohort that has a parsed event for the frozen prompt goes into the sample and is
put in a seeded random order. The first `n_human` of a stratified draw (proportional over the cohort's
year band x preprint/article strata) are marked human=1: those are rated by the human AND the LLM
judge. The rest are rated by the judge only.

    python3 validation/make_sample.py            # writes validation/sample.csv; refuses to overwrite
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG_PATH, REPO, SAMPLE_COLUMNS, load_config, read_csv  # noqa: E402


def draw(record_ids: list[str], strata: dict[str, str], n_human: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for rid in sorted(record_ids):
        by_stratum[strata.get(rid, "")].append(rid)
    n_human = min(n_human, len(record_ids))
    # Proportional allocation, largest remainders, so the human subset mirrors the cohort.
    quotas = {s: n_human * len(ids) / len(record_ids) for s, ids in by_stratum.items()}
    take = {s: int(q) for s, q in quotas.items()}
    for s in sorted(quotas, key=lambda s: (quotas[s] - take[s], s), reverse=True)[: n_human - sum(take.values())]:
        take[s] += 1
    human = set()
    for s in sorted(by_stratum):
        human.update(rng.sample(by_stratum[s], take[s]))
    order = sorted(record_ids)
    rng.shuffle(order)
    return [{"order": i + 1, "record_id": rid, "stratum": strata.get(rid, ""), "human": "1" if rid in human else "0"}
            for i, rid in enumerate(order)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    config = load_config(args.config)
    args.out = config["_sample_path"]
    if args.out.exists():
        print(f"REFUSING: {args.out.name} already exists. The sample is drawn once; delete it only if no rating has started.")
        return 1
    events = [r for r in read_csv(REPO / config["events"])
              if r.get("parse_status") == "ok" and r.get("prompt_version") == config["prompt_version"]]
    if not events:
        print(f"No '{config['prompt_version']}' events in {config['events']}. Run the enrichment first:\n"
              f"  python3 scripts/run_enrichment.py --cohort {config['cohort']} --prompt e2 --confirm")
        return 1
    wrong = {r["vocab_sha256"] for r in events} - {config["prompt_sha256"]}
    if wrong:
        print(f"REFUSING: events were made with a different prompt hash than config.json: {sorted(wrong)}")
        return 1
    inputs = {r["record_id"] for r in read_csv(REPO / config["input"])}
    ids = sorted({r["record_id"] for r in events} & inputs)
    manifest = read_csv(REPO / "cohorts" / "manifest.csv") + read_csv(REPO / "cohorts" / "heldout_manifest.csv")
    strata = {r["record_id"]: r.get("stratum", "") for r in manifest}
    rows = draw(ids, strata, config["n_human"], config["seed"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SAMPLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    n_h = sum(r["human"] == "1" for r in rows)
    print(f"wrote {args.out}: {len(rows)} records, {n_h} for human + judge, {len(rows) - n_h} judge only "
          f"(seed {config['seed']})")
    if len(ids) < len(inputs):
        print(f"NOTE: {len(inputs) - len(ids)} input records have no parsed event and are not in the sample.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
