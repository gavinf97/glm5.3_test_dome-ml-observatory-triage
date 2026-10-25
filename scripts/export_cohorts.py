#!/usr/bin/env python3
"""Export the three test cohorts from moros. READ-ONLY: only count_documents, aggregate
($sample/$match/$project) and find are issued, and nothing in this repository can write.

The connection is the triage repository's `moros_client.Moros`, configured by that repository's
gitignored `moros_pipeline/.env`, so the moros address never enters this one. Needs the VPN.

    python3 scripts/export_cohorts.py            # refuses if the cohorts already exist
    python3 scripts/export_cohorts.py --force    # re-draws them (orphans any events already paid for)

Writes:
  data/input_wave1_250.csv, data/input_wave2_250.csv   un-enriched positives, the e1 input columns
  data/input_enriched_100.csv                          DeepSeek V4.1-enriched positives, same columns
  data/reference_deepseek_100.csv                      their stored enrichment, as JSON list cells
  cohorts/manifest.csv                                 committed: ids, strata, venue, identifiers
  cohorts/export_summary.json                          committed: queries, pool sizes, strata counts
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glm_enrich import COHORTS, FIELDS, REPO, triage_repo  # noqa: E402
from glm_enrich.cohorts import select_enriched, select_unenriched, stratum, venue  # noqa: E402

SEED = 20261025
N_UNENRICHED, N_ENRICHED = 500, 100
FLOOR, CAP_UNENRICHED, CAP_ENRICHED = 10, 2, 3
# $sample as the FIRST stage, under 5% of the collection, uses a random cursor rather than a sort of
# the whole collection: no server-side memory pressure and no temporary files on moros.
SAMPLE_SIZE = 40_000
# DeepSeek began answering the pipeline's model id with V4.1-Flash at this instant (triage repo,
# pricing/pricing.yaml). Stored timestamps are ISO strings, so this compares as text.
V41_FROM = "2026-09-10T04:00"
MAX_TIME_MS = 120_000

INPUT_COLUMNS = ["record_id", "title", "abstract", "journal", "year"]
MANIFEST_COLUMNS = ["record_id", "cohort", "wave", "stratum", "year", "journal", "preprint_server",
                    "epmc_source", "doi", "pmid", "pmcid", "reference_model_id", "reference_batch_id",
                    "reference_timestamp"]
REFERENCE_COLUMNS = ["record_id", *FIELDS, "rationale", "vocab_violations", "parse_status", "model_id",
                     "batch_id", "timestamp", "prompt_version", "ruleset_sha256", "input_tokens", "output_tokens",
                     "cache_hit_tokens"]

HAS_TEXT = {"publication_metadata.title": {"$nin": [None, ""]},
            "publication_metadata.abstract": {"$nin": [None, ""]}}
UNENRICHED = {"llm_classification.classification": "positive", "llm_enrichment.provider": None, **HAS_TEXT}
ENRICHED_V41 = {"llm_classification.classification": "positive", "llm_enrichment.provider": {"$ne": None},
                "llm_enrichment.parse_status": {"$ne": "parse_error"},
                "llm_enrichment.timestamp": {"$gte": V41_FROM}, **HAS_TEXT}
META = {"_id": 1, "publication_metadata.journal": 1, "publication_metadata.year": 1,
        "publication_metadata.preprint_server": 1, "source.epmc_source": 1,
        "identifiers.doi": 1, "identifiers.pmid": 1, "identifiers.pmcid": 1}
ENRICH_META = {**META, **{f"content_filters.{f}": 1 for f in FIELDS},
               **{f"llm_enrichment.{k}": 1 for k in ("rationale", "vocab_violations", "parse_status", "model_id",
                                                    "batch_id", "timestamp", "prompt_version", "ruleset_sha256",
                                                    "input_tokens", "output_tokens", "cache_hit_tokens")}}


def flatten(doc: dict) -> dict:
    pub = doc.get("publication_metadata") or {}
    ids = doc.get("identifiers") or {}
    return {"record_id": doc["_id"], "journal": pub.get("journal") or "", "year": pub.get("year"),
            "preprint_server": pub.get("preprint_server") or "",
            "epmc_source": (doc.get("source") or {}).get("epmc_source") or "",
            "doi": ids.get("doi") or "", "pmid": ids.get("pmid") or "", "pmcid": ids.get("pmcid") or ""}


def as_list(value) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def fetch_text(collection, ids: list[str]) -> dict[str, dict]:
    out = {}
    for doc in collection.find({"_id": {"$in": ids}},
                               {"_id": 1, "publication_metadata.title": 1, "publication_metadata.abstract": 1},
                               max_time_ms=MAX_TIME_MS):
        out[doc["_id"]] = doc.get("publication_metadata") or {}
    missing = [i for i in ids if not ((out.get(i) or {}).get("title") and (out.get(i) or {}).get("abstract"))]
    if missing:
        raise SystemExit(f"{len(missing)} selected record(s) came back without a title or abstract, e.g. {missing[:3]}")
    return out


def input_row(row: dict, text: dict) -> dict:
    # The same row shape as the triage repo's export_journal_for_enrichment.py.
    return {"record_id": row["record_id"], "title": text.get("title") or "", "abstract": text["abstract"],
            "journal": row["journal"], "year": row["year"] if row["year"] is not None else ""}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="Overwrite existing cohort files.")
    args = parser.parse_args()

    outputs = [REPO / c["input"] for c in COHORTS.values()] + [REPO / COHORTS["enriched100"]["reference"],
                                                              REPO / "cohorts" / "manifest.csv"]
    existing = [p for p in outputs if p.exists()]
    if existing and not args.force:
        print("REFUSING: cohort files already exist (" + ", ".join(str(p.relative_to(REPO)) for p in existing)
              + "). Re-drawing would orphan events already paid for; pass --force to do it anyway.")
        return 1

    scripts_dir = triage_repo() / "moros_pipeline" / "scripts"
    if not (scripts_dir / "moros_client.py").exists():
        print(f"moros_client.py not found under TRIAGE_REPO ({scripts_dir}) -- set TRIAGE_REPO in .env")
        return 1
    sys.path.insert(0, str(scripts_dir))
    from moros_client import Moros  # noqa: E402 -- the triage repo's read-only client

    with Moros.from_env(compressors="zlib") as moros:
        c = moros.collection
        print(f"connected: {moros.db_name}.{moros.collection_name} (read-only queries only)")
        pool_unenriched = c.count_documents(UNENRICHED, maxTimeMS=MAX_TIME_MS)
        print(f"un-enriched positives with title+abstract: {pool_unenriched:,}")

        sampled = {}
        for doc in c.aggregate([{"$sample": {"size": SAMPLE_SIZE}}, {"$match": UNENRICHED}, {"$project": META}],
                               maxTimeMS=MAX_TIME_MS):
            sampled[doc["_id"]] = flatten(doc)
        print(f"random-cursor sample of {SAMPLE_SIZE:,} documents -> {len(sampled):,} eligible")
        unenriched = select_unenriched(list(sampled.values()), N_UNENRICHED, FLOOR, CAP_UNENRICHED, SEED)
        if len(unenriched) < N_UNENRICHED:
            raise SystemExit(f"only {len(unenriched)} un-enriched records selectable; raise SAMPLE_SIZE")

        pool_enriched = []
        for doc in c.find(ENRICHED_V41, ENRICH_META, max_time_ms=MAX_TIME_MS):
            row = flatten(doc)
            filters = doc.get("content_filters") or {}
            le = doc.get("llm_enrichment") or {}
            row.update({f: json.dumps(as_list(filters.get(f))) for f in FIELDS})
            row["domain_tier1_value"] = filters.get("domain_tier1")
            row.update({k: le.get(k) for k in ("rationale", "parse_status", "model_id", "batch_id", "timestamp",
                                                "prompt_version", "ruleset_sha256", "input_tokens",
                                                "output_tokens", "cache_hit_tokens")})
            row["vocab_violations"] = json.dumps(as_list(le.get("vocab_violations")))
            pool_enriched.append(row)
        print(f"DeepSeek V4.1-enriched positives (timestamp >= {V41_FROM}): {len(pool_enriched):,}")
        enriched = select_enriched(pool_enriched, N_ENRICHED, CAP_ENRICHED, SEED, key="domain_tier1_value")

        text = fetch_text(c, [r["record_id"] for r in unenriched + enriched])

    overlap = {r["record_id"] for r in unenriched} & {r["record_id"] for r in enriched}
    assert not overlap, overlap

    wave_rows = {1: [], 2: []}
    for r in unenriched:
        wave_rows[r["wave"]].append(input_row(r, text[r["record_id"]]))
    write_csv(REPO / COHORTS["wave1"]["input"], INPUT_COLUMNS, wave_rows[1])
    write_csv(REPO / COHORTS["wave2"]["input"], INPUT_COLUMNS, wave_rows[2])
    write_csv(REPO / COHORTS["enriched100"]["input"], INPUT_COLUMNS, [input_row(r, text[r["record_id"]]) for r in enriched])
    write_csv(REPO / COHORTS["enriched100"]["reference"], REFERENCE_COLUMNS, enriched)

    manifest = [{**r, "cohort": f"wave{r['wave']}"} for r in unenriched]
    manifest += [{**r, "cohort": "enriched100", "wave": "", "reference_model_id": r["model_id"],
                  "reference_batch_id": r["batch_id"], "reference_timestamp": r["timestamp"]} for r in enriched]
    write_csv(REPO / "cohorts" / "manifest.csv", MANIFEST_COLUMNS, manifest)

    summary = {
        "exported_utc": datetime.now(timezone.utc).isoformat(), "seed": SEED,
        "unenriched": {"query": UNENRICHED, "pool": pool_unenriched, "sample_size": SAMPLE_SIZE,
                       "eligible_in_sample": len(sampled), "selected": len(unenriched), "floor_per_stratum": FLOOR,
                       "venue_cap": CAP_UNENRICHED,
                       "eligible_strata": dict(sorted(Counter(stratum(r) for r in sampled.values()).items())),
                       "strata": dict(sorted(Counter(r["stratum"] for r in unenriched).items())),
                       "waves": dict(Counter(f"wave{r['wave']}" for r in unenriched)),
                       "distinct_venues": len({venue(r) for r in unenriched if venue(r)})},
        "enriched100": {"query": ENRICHED_V41, "pool": len(pool_enriched), "selected": len(enriched),
                        "venue_cap": CAP_ENRICHED,
                        "domain_tier1": dict(sorted(Counter(r["stratum"] for r in enriched).items())),
                        "reference_batches": dict(Counter(r["batch_id"] for r in enriched)),
                        "reference_ruleset_sha256": dict(Counter(r["ruleset_sha256"] for r in enriched)),
                        "distinct_venues": len({venue(r) for r in enriched if venue(r)})},
    }
    (REPO / "cohorts" / "export_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"\nwave1 {len(wave_rows[1])}, wave2 {len(wave_rows[2])}, enriched100 {len(enriched)}")
    print("eligible sample strata: " + ", ".join(f"{k} {v}" for k, v in summary["unenriched"]["eligible_strata"].items()))
    print("strata (un-enriched): " + ", ".join(f"{k} {v}" for k, v in summary["unenriched"]["strata"].items()))
    print("domain_tier1 (enriched100): " + ", ".join(f"{k} {v}" for k, v in summary["enriched100"]["domain_tier1"].items()))
    print(f"distinct venues: {summary['unenriched']['distinct_venues']} (un-enriched), {summary['enriched100']['distinct_venues']} (enriched100)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
