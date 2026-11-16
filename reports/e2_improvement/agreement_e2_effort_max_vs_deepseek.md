# GLM-5.3-Flash (e2, max effort) vs DeepSeek V4.1-Flash: how often they give the same tags

Both models tagged the same 99 papers. DeepSeek used prompt e1; GLM-5.3-Flash (e2, max effort) used the EXPERIMENTAL local prompt e2 (experimental/e2/PROVENANCE.md). A field counts as agreeing when both models chose exactly the same terms.

GLM run: 100 of 100 papers tagged, 1 unreadable answers, 1 cut off at the length limit.

| Field | GLM-5.3-Flash (e2, max effort) and DeepSeek agree | For comparison: DeepSeek agrees with its own previous version |
|---|---:|---:|
| Domain, top level (EDAM tier 1) | 72% | 95% |
| Domain, tier 2 | 48% | 43% |
| Domain, tier 3 | 39% | 28% |
| Learning paradigm | 85% | 87% |
| Model family | 56% | 77% |
| Model type | 48% | 45% |
| **All six fields at once** | **8%** | **4%** |

**How to read this.** The right-hand column is DeepSeek V4.1 against DeepSeek V4 on the same kind of
papers (2026-09-15). Where GLM's figure is close to it, GLM differs from DeepSeek about as much as
DeepSeek differs from itself. Where it is well below, GLM tags that field differently.

Agreeing is not the same as being right: two models can agree on a wrong tag, or disagree where both
tags are defensible. For which model is correct, see `tag_correctness_review_enriched100.md`.

## Run profile

| | GLM-5.3-Flash (e2, max effort) | DeepSeek V4.1-Flash |
|---|---:|---:|
| Papers with a tag outside the vocabulary | 2% | 0% |
| Input tokens per paper | 5,628 | 3,120 |
| Share of input served from the prompt cache | 23% | 82% |
| Output tokens per paper | 2,981 | 1,789 |
| of which reasoning | 2,805 | not stored |
