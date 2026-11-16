#!/usr/bin/env python3
"""Draws the held-out cohort `heldout250`: 250 confirmed AI/ML positives that are in none of the
earlier cohorts (wave1, wave2, enriched100), so the e2 prompt -- tuned on enriched100's failures --
is judged on papers it has never been shaped by.

Read-only and offline: the source is the sibling triage repository's local landscape exports
(mongo_landscape_export/output/incoming_*_documents.jsonl), not moros. Selection is the same as
wave1/wave2 (glm_enrich.cohorts.select_unenriched: year band x preprint/article, floor per stratum,
at most 2 per journal) with a new seed.

    python3 scripts/export_heldout.py

Writes data/input_heldout_250.csv (titles and abstracts: gitignored), data/heldout_250_metadata.csv
(MeSH headings and author keywords, for the correctness review: gitignored), and the committed
cohorts/heldout_manifest.csv and cohorts/heldout_summary.json.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glm_enrich import REPO, triage_repo  # noqa: E402
from glm_enrich.cohorts import select_unenriched  # noqa: E402

SEED = 20261105
N, FLOOR, VENUE_CAP = 250, 10, 2
SOURCES = ("mongo_landscape_export/output/incoming_new_documents.jsonl",
           "mongo_landscape_export/output/incoming_catchup_documents.jsonl")
INPUT = REPO / "data" / "input_heldout_250.csv"
METADATA = REPO / "data" / "heldout_250_metadata.csv"
MANIFEST = REPO / "cohorts" / "heldout_manifest.csv"
SUMMARY = REPO / "cohorts" / "heldout_summary.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    triage = triage_repo()
    seen_ids, seen_dois, seen_pmids = set(), set(), set()
    with (REPO / "cohorts" / "manifest.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seen_ids.add(row["record_id"])
            seen_dois.add((row.get("doi") or "").strip().lower())
            seen_pmids.add((row.get("pmid") or "").strip())
    seen_dois.discard("")
    seen_pmids.discard("")

    pool, counts, sources = {}, {"positive": 0, "excluded_seen": 0, "excluded_no_text": 0}, {}
    for rel in SOURCES:
        path = triage / rel
        sources[rel] = sha256_file(path)
        with path.open(encoding="utf-8") as f:
            for line in f:
                doc = json.loads(line)
                if (doc.get("llm_classification") or {}).get("classification") != "positive":
                    continue
                counts["positive"] += 1
                ids, pub = doc.get("identifiers") or {}, doc.get("publication_metadata") or {}
                doi, pmid = (ids.get("doi") or "").strip().lower(), (ids.get("pmid") or "").strip()
                if doc["_id"] in seen_ids or (doi and doi in seen_dois) or (pmid and pmid in seen_pmids):
                    counts["excluded_seen"] += 1
                    continue
                title, abstract = (pub.get("title") or "").strip(), (pub.get("abstract") or "").strip()
                if not title or not abstract:
                    counts["excluded_no_text"] += 1
                    continue
                cf, src = doc.get("content_filters") or {}, doc.get("source") or {}
                pool[doc["_id"]] = {
                    "record_id": doc["_id"], "title": title, "abstract": abstract,
                    "journal": pub.get("journal") or "", "year": pub.get("year") or "",
                    "preprint_server": pub.get("preprint_server") or "", "epmc_source": src.get("epmc_source") or "",
                    "doi": ids.get("doi") or "", "pmid": pmid, "pmcid": ids.get("pmcid") or "",
                    "mesh_headings": json.dumps(cf.get("mesh_headings") or []),
                    "keywords_author": json.dumps(cf.get("keywords_author") or []),
                    "source_file": Path(rel).name,
                }
    chosen = select_unenriched(list(pool.values()), N, FLOOR, VENUE_CAP, SEED)

    INPUT.parent.mkdir(parents=True, exist_ok=True)
    def write(path: Path, columns: list[str]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            w.writeheader()
            w.writerows(chosen)
    write(INPUT, ["record_id", "title", "abstract", "journal", "year"])
    write(METADATA, ["record_id", "pmid", "doi", "mesh_headings", "keywords_author"])
    for row in chosen:
        row["cohort"] = "heldout250"
    write(MANIFEST, ["record_id", "cohort", "stratum", "year", "journal", "preprint_server", "epmc_source",
                     "doi", "pmid", "pmcid", "source_file"])

    strata: dict[str, int] = {}
    for row in chosen:
        strata[row["stratum"]] = strata.get(row["stratum"], 0) + 1
    summary = {
        "exported_utc": datetime.now(timezone.utc).isoformat(), "cohort": "heldout250", "seed": SEED,
        "purpose": "held-out evaluation of the EXPERIMENTAL e2 prompt; no overlap with wave1, wave2 or enriched100",
        "source": "triage repository local landscape exports (offline, read-only)", "source_sha256": sources,
        "counts": {**counts, "eligible": len(pool), "selected": len(chosen)},
        "floor_per_stratum": FLOOR, "venue_cap": VENUE_CAP, "strata": dict(sorted(strata.items())),
        "with_mesh": sum(1 for r in chosen if r["mesh_headings"] != "[]"),
        "distinct_venues": len({(r["journal"] or "").casefold() for r in chosen if r["epmc_source"] != "PPR"}),
        "overlap_with_earlier_cohorts": sum(1 for r in chosen if r["record_id"] in seen_ids),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
