#!/usr/bin/env python3
"""Builds the EXPERIMENTAL e2 modelling vocabularies from the vendored e1 files, so every change is
code with an ID rather than a hand edit. Each added or changed entry carries
`"extension": "e2-experimental"` and a `provenance` pointer into PROVENANCE.md.

    python3 experimental/e2/build_vocab.py           # writes the two *.e2.json files next to this script
    python3 experimental/e2/build_vocab.py --check   # exits 1 if the files on disk differ from a fresh build

e1 in vendor/ is read, never written. The domain vocabulary is not changed in e2 and is not copied.
Local only: nothing here is part of the production vocabulary in dome-ml-observatory-triage.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E1 = REPO / "vendor" / "curation_criteria"
OUT_BRANCH = HERE / "modelling_branch_vocab.e2.json"
OUT_SEED = HERE / "model_type_seed_vocab.e2.json"

APPROVED = "Gavin, 2026-11-05"
LOOKED_UP = "2026-11-05"
STATUS = "EXPERIMENTAL e2 -- local to glm5.3_test only, not production, not validated"


def prov(change_id: str) -> dict:
    return {"extension": "e2-experimental", "provenance": f"experimental/e2/PROVENANCE.md#{change_id.lower()}",
            "approved": APPROVED}


def aio(name: str, label: str) -> dict:
    return {"ontology": "aio", "id": f"AIO:{name}", "iri": f"https://w3id.org/aio/{name}", "label": label,
            "predicate": "skos:exactMatch", "source": "ols4 search (ontology=aio)", "checked": LOOKED_UP}


def build_branch(e1: dict) -> dict:
    v = copy.deepcopy(e1)
    v["e2"] = {"status": STATUS, "base": "vendor/curation_criteria/modelling_branch_vocab.json (prompt e1)",
               "changes": ["E2-V1", "E2-V2", "E2-V3", "E2-V4", "E2-V5", "E2-V6"]}
    f = v["fields"]

    # E2-V1: a separate axis for how the paper obtains its model, so learning_paradigm stops
    # describing the training of tools the paper only applies or prompts.
    f["model_use"] = {
        "max_tags": 2,
        "guidance": ("How the paper obtains the model(s) it reports. Usually exactly 1; use 2 when the paper "
                     "both trains its own model and applies or prompts another one."),
        **prov("E2-V1"),
        "terms": [
            {"label": "trained in this study", "definition": "The paper fits or trains the model on its own data (including training from scratch a published architecture).", **prov("E2-V1"), "ontology_mappings": []},
            {"label": "fine-tuned or adapted", "definition": "A pretrained model is further trained, fine-tuned, calibrated or transfer-learned on the paper's data.", **prov("E2-V1"), "ontology_mappings": []},
            {"label": "pretrained, applied as-is", "definition": "An existing trained model or tool (e.g. AlphaFold, a commercial AI product) is run without further training.", **prov("E2-V1"), "ontology_mappings": []},
            {"label": "prompted (zero/few-shot)", "definition": "A pretrained model, usually an LLM, is used through prompts or in-context examples, with no weight updates.", **prov("E2-V1"), "ontology_mappings": [aio("ZeroshotLearning", "Zero-shot Learning")]},
        ],
    }

    lp = f["learning_paradigm"]
    lp["guidance"] = ("How the model is trained IN THIS PAPER. Usually exactly 1; use 2 when the paper has a distinct "
                      "second learning step (e.g. unsupervised clustering or embedding feeding a supervised model). "
                      "Use [] when the paper trains nothing (model_use is only 'pretrained, applied as-is' or "
                      "'prompted (zero/few-shot)').")
    lp.update({"guidance_changed_by": "E2-V1"})
    for term in lp["terms"]:
        if term["label"] == "semi-supervised":  # E2-V3
            term["definition"] = ("Learning from a mix of labelled and unlabelled data, including weak supervision "
                                  "(noisy, partial or coarse labels such as image-level tags or multiple-instance "
                                  "learning) and pseudo-labelling. Standard textbook category; verified absent "
                                  "from MeSH (exact + contains lookups empty).")
            term.update({"definition_changed_by": "E2-V3", **prov("E2-V3")})
    # E2-V2
    lp["terms"].append({"label": "self-supervised", "mesh_id": None, **prov("E2-V2"),
                        "definition": ("Learning from labels generated from the data itself, e.g. masked or next-token "
                                       "prediction, contrastive pretraining, denoising. Used for pretraining "
                                       "foundation and language models. Verified absent from MeSH."),
                        "ontology_mappings": [aio("SelfsupervisedLearning", "Self-supervised Learning")]})

    mf = f["model_family"]
    mf["terms"] += [
        {"label": "active learning", "mesh_id": None, **prov("E2-V4"),
         "definition": "The model chooses which new samples or experiments to label or run next (closed-loop, query-driven design). Verified absent from MeSH.",
         "ontology_mappings": [aio("ActiveLearning", "Active Learning")]},
        {"label": "multimodal learning", "mesh_id": None, **prov("E2-V5"),
         "definition": "One model learns jointly from two or more data modalities (e.g. image + text, imaging + omics, several sensor types). Verified absent from MeSH.",
         "ontology_mappings": [aio("MultimodalLearning", "Multimodal Learning")]},
        {"label": "physics-informed machine learning", "mesh_id": None, **prov("E2-V6"),
         "definition": "Physical laws or constraints are built into the model or its loss (e.g. physics-informed neural networks, physics-constrained losses). Project extension: no MeSH descriptor and no AIO term found.",
         "ontology_mappings": []},
    ]
    return v


def build_seed(e1: dict) -> dict:
    v = copy.deepcopy(e1)
    v["e2"] = {"status": STATUS, "base": "vendor/curation_criteria/model_type_seed_vocab.json (prompt e1)",
               "changes": ["E2-V9"]}
    by = {t["canonical"]: t for t in v["terms"]}
    # E2-V9: aliases the review found models mis-mapping.
    for canonical, extra in (("neural network", ["BP-ANN", "backpropagation neural network", "BPNN"]),
                             ("gradient boosting", ["histogram gradient boosting", "HistGradientBoosting"])):
        by[canonical]["aliases"] = by[canonical]["aliases"] + extra
        by[canonical].update({"aliases_added_by": "E2-V9", **prov("E2-V9")})
    v["terms"] += [
        {"canonical": "causal forest", "aliases": ["generalized random forest", "causal random forest"],
         "family_hint": "classical machine learning + ensemble learning", "sklearn": [], "ontology_mappings": [], **prov("E2-V9")},
        {"canonical": "machine-learning interatomic potential",
         "aliases": ["MLIP", "machine learning potential", "ML potential", "machine-learned interatomic potential", "neural network potential"],
         "family_hint": "", "sklearn": [], "ontology_mappings": [], **prov("E2-V9")},
        {"canonical": "state space model", "aliases": ["Mamba", "SSM (state space model)", "S4"],
         "family_hint": "deep learning", "sklearn": [], "ontology_mappings": [], **prov("E2-V9")},
    ]
    v["n_seed_entries"] = len(v["terms"])
    return v


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    branch = dumps(build_branch(json.loads((E1 / "modelling_branch_vocab.json").read_text(encoding="utf-8"))))
    seed = dumps(build_seed(json.loads((E1 / "model_type_seed_vocab.json").read_text(encoding="utf-8"))))
    if args.check:
        stale = [p.name for p, text in ((OUT_BRANCH, branch), (OUT_SEED, seed))
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        print("ok: e2 vocab files match a fresh build" if not stale else f"STALE: {', '.join(stale)}")
        return 1 if stale else 0
    OUT_BRANCH.write_text(branch, encoding="utf-8")
    OUT_SEED.write_text(seed, encoding="utf-8")
    print(f"wrote {OUT_BRANCH.relative_to(REPO)} and {OUT_SEED.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
