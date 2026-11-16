#!/usr/bin/env python3
"""Freezes the EXPERIMENTAL e2 prompt: renders it, writes enrichment_system_message.e2.txt, and
records the sha256 of the four files that define e2 in MANIFEST.sha256. Prints the prompt hash,
which must then be put in glm_enrich/e2.py (EXPECTED_E2_SHA256) on purpose -- a changed prompt
never starts a run silently.

    python3 experimental/e2/freeze.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from glm_enrich import e2  # noqa: E402


def main() -> int:
    text, _, _ = e2.render_e2()
    e2.E2_RENDERED.write_text(text, encoding="utf-8")
    entries = e2.e2_manifest_entries()
    e2.E2_MANIFEST.write_text("".join(f"{digest}  {name}\n" for name, digest in entries.items()), encoding="utf-8")
    digest = e2.e1.vocab_sha256(text)
    print(f"e2 prompt sha256 {digest}")
    if digest != e2.EXPECTED_E2_SHA256:
        print("set EXPECTED_E2_SHA256 in glm_enrich/e2.py to this value")
    return 0


if __name__ == "__main__":
    sys.exit(main())
