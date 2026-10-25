"""Proof that what is sent is the validated e1 enrichment: every vendored file is the recorded
byte-for-byte copy, and the system message renders to the recorded hash."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from glm_enrich import CRITERIA_DIR, EXPECTED_VOCAB_SHA256, RENDERED_PROMPT, VENDOR, VENDOR_MANIFEST
from dome_triage.llm_classify import enrichment

# Where each vendored file lives in the triage repository.
TRIAGE_LOCATIONS = {
    "dome_triage/": "src/dome_triage/",
    "curation_criteria/": "curation_criteria/",
    "prompts/": "prompts/",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest() -> dict[str, str]:
    entries = {}
    for line in VENDOR_MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, rel = line.split(maxsplit=1)
            entries[rel.strip()] = digest
    return entries


def manifest_sha256() -> str:
    return sha256_file(VENDOR_MANIFEST)


def triage_path(triage: Path, rel: str) -> Path:
    for prefix, target in TRIAGE_LOCATIONS.items():
        if rel.startswith(prefix):
            return triage / target / rel[len(prefix):]
    raise KeyError(rel)


def render() -> tuple[str, dict, dict]:
    vocabs = enrichment.load_vocabularies(CRITERIA_DIR)
    text = enrichment.build_static_system_text(vocabs, "flat")
    return text, vocabs, enrichment._build_lookup(vocabs)


def problems(triage: Optional[Path] = None) -> list[str]:
    """Empty when everything holds. `triage`, when given and present, is also compared, so a
    versioned change there (a new prompt or vocabulary) is noticed here rather than silently
    tested against the old one."""
    found = []
    manifest = read_manifest()
    on_disk = {str(p.relative_to(VENDOR)) for p in VENDOR.rglob("*")
               if p.is_file() and p != VENDOR_MANIFEST and "__pycache__" not in p.parts}
    for rel in sorted(on_disk - set(manifest)):
        found.append(f"vendor/{rel} is not in MANIFEST.sha256")
    for rel, digest in sorted(manifest.items()):
        path = VENDOR / rel
        if not path.exists():
            found.append(f"vendor/{rel} is missing")
            continue
        if sha256_file(path) != digest:
            found.append(f"vendor/{rel} differs from MANIFEST.sha256")
        if triage is not None and triage.exists():
            original = triage_path(triage, rel)
            if not original.exists():
                found.append(f"{rel}: not found in the triage repo at {original.relative_to(triage)}")
            elif sha256_file(original) != digest:
                found.append(f"{rel}: the triage repo's copy has changed since it was vendored")

    text, _, _ = render()
    rendered = enrichment.vocab_sha256(text)
    if rendered != EXPECTED_VOCAB_SHA256:
        found.append(f"rendered e1 system message is {rendered[:12]}..., expected {EXPECTED_VOCAB_SHA256[:12]}...")
    if text.encode("utf-8") != RENDERED_PROMPT.read_bytes():
        found.append("rendered e1 system message differs from vendor/prompts/enrichment_system_message.e1.txt")
    return found
