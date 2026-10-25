#!/usr/bin/env python3
"""Check that the vendored enrichment code, vocabularies and rendered prompt are the validated e1
copies: the recorded sha256 of each, against the triage repository when it is present, and the
rendered system message against vocab_sha256 41db952f... Exits 1 on any difference.

    python3 scripts/check_vendor.py
    python3 scripts/check_vendor.py --no-triage    # vendored manifest and render only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glm_enrich import EXPECTED_VOCAB_SHA256, triage_repo  # noqa: E402
from glm_enrich.fidelity import problems  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-triage", action="store_true", help="Do not compare with the triage repository.")
    args = parser.parse_args()

    triage = None if args.no_triage else triage_repo()
    found = problems(triage)
    if found:
        print("FAIL")
        for line in found:
            print(f"  {line}")
        return 1
    compared = "and the triage repository" if triage is not None and triage.exists() else "(triage repository not found, not compared)"
    print(f"ok: vendored files match MANIFEST.sha256 {compared}; e1 renders to {EXPECTED_VOCAB_SHA256[:12]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
