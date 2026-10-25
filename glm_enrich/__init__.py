"""GLM enrichment test bed: the validated e1 enrichment, unchanged, called through Z.ai instead of DeepSeek.

Importing this package puts `vendor/` on `sys.path`, so `dome_triage.llm_classify.*` resolves to the
byte-identical copies there and nowhere else.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "vendor"
CRITERIA_DIR = VENDOR / "curation_criteria"
RENDERED_PROMPT = VENDOR / "prompts" / "enrichment_system_message.e1.txt"
VENDOR_MANIFEST = VENDOR / "MANIFEST.sha256"

if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

# Recorded in the triage repository's prompts/PROMPT_HASHES.json for prompt e1. A render that does
# not come out at exactly this is not the validated prompt, and nothing is sent.
EXPECTED_VOCAB_SHA256 = "41db952f15118176fa27dac724eff9dff59714b62854859d9606ef440ee473c7"

FIELDS = ("domain_tier1", "domain_tier2", "domain_tier3", "learning_paradigm", "model_family", "model_type")

# One input and one events file per cohort -- never two cohorts in one log.
COHORTS = {
    "wave1": {"input": "data/input_wave1_250.csv", "events": "runs/events_wave1.csv"},
    "wave2": {"input": "data/input_wave2_250.csv", "events": "runs/events_wave2.csv"},
    "enriched100": {"input": "data/input_enriched_100.csv", "events": "runs/events_enriched100.csv",
                    "reference": "data/reference_deepseek_100.csv"},
}


def load_env(path: Path = REPO / ".env") -> dict[str, str]:
    """KEY=VALUE reader, the same shape as the triage repo's moros_client.load_env. Real environment
    variables win. Values are never printed by anything in this repository."""
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("ZAI_API_KEY", "TRIAGE_REPO"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def triage_repo() -> Path:
    """The sibling dome-ml-observatory-triage checkout: source of the vendored files and of the
    read-only moros client. Relative paths resolve against this repository."""
    value = load_env().get("TRIAGE_REPO") or "../dome-ml-observatory-triage"
    path = Path(value)
    return (path if path.is_absolute() else (REPO / path)).resolve()
