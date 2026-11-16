# GLM-5.3-Flash (e2) vs DeepSeek V4.1-Flash: how often they give the same tags

Both models tagged the same 100 papers. DeepSeek used prompt e1; GLM-5.3-Flash (e2) used the EXPERIMENTAL local prompt e2 (experimental/e2/PROVENANCE.md). A field counts as agreeing when both models chose exactly the same terms.

GLM run: 100 of 100 papers tagged, 0 unreadable answers, 0 cut off at the length limit.

| Field | GLM-5.3-Flash (e2) and DeepSeek agree | For comparison: DeepSeek agrees with its own previous version |
|---|---:|---:|
| Domain, top level (EDAM tier 1) | 68% | 95% |
| Domain, tier 2 | 35% | 43% |
| Domain, tier 3 | 33% | 28% |
| Learning paradigm | 85% | 87% |
| Model family | 56% | 77% |
| Model type | 52% | 45% |
| **All six fields at once** | **4%** | **4%** |

**How to read this.** The right-hand column is DeepSeek V4.1 against DeepSeek V4 on the same kind of
papers (2026-09-15). Where GLM's figure is close to it, GLM differs from DeepSeek about as much as
DeepSeek differs from itself. Where it is well below, GLM tags that field differently.

Agreeing is not the same as being right: two models can agree on a wrong tag, or disagree where both
tags are defensible. For which model is correct, see `tag_correctness_review_enriched100.md`.

## Run profile

| | GLM-5.3-Flash (e2) | DeepSeek V4.1-Flash |
|---|---:|---:|
| Papers with a tag outside the vocabulary | 2% | 0% |
| Input tokens per paper | 5,627 | 3,119 |
| Share of input served from the prompt cache | 24% | 82% |
| Output tokens per paper | 501 | 1,829 |
| of which reasoning | 341 | not stored |

## Examples of disagreement

Up to 5 per field. Record IDs are shortened to their first 8 characters.

| Field | Record | GLM-5.3-Flash (e2) | DeepSeek |
|---|---|---|---|
| Domain, top level (EDAM tier 1) | 0cda17de | computer science | physics |
| Domain, top level (EDAM tier 1) | 0e4e2c11 | biology | computational biology |
| Domain, top level (EDAM tier 1) | 1d3c7859 | omics | medicine |
| Domain, top level (EDAM tier 1) | 0a190435 | omics | biomedical science |
| Domain, top level (EDAM tier 1) | 099d073f | omics | biomedical science |
| Domain, tier 2 | 1d6ff883 | computational chemistry, simulation experiment | computational chemistry, machine learning |
| Domain, tier 2 | 0cda17de | machine learning | imaging, machine learning |
| Domain, tier 2 | 1952c67a | environmental science | environmental science, machine learning |
| Domain, tier 2 | 1223e044 | environmental science, machine learning | environmental science, public health and epidemiology |
| Domain, tier 2 | 0772cfc8 | computational chemistry | computational chemistry, machine learning |
| Domain, tier 3 | 0a891883 | medical imaging | medical imaging, preclinical and clinical studies, tomography |
| Domain, tier 3 | 0e30576b | (none) | preclinical and clinical studies |
| Domain, tier 3 | 0a51c163 | (none) | data acquisition |
| Domain, tier 3 | 0cda17de | (none) | tomography |
| Domain, tier 3 | 1952c67a | (none) | data acquisition, data architecture, analysis and design, data integration and warehousing |
| Learning paradigm | 0a891883 | (none) | supervised |
| Learning paradigm | 0e4e2c11 | (none) | unsupervised |
| Learning paradigm | 089d314c | (none) | supervised |
| Learning paradigm | 013bdf07 | (none) | supervised |
| Learning paradigm | 0891e384 | (none) | supervised, unsupervised |
| Model family | 01413cdf | classical machine learning, ensemble learning | classical machine learning |
| Model family | 0a891883 | (none) | deep learning |
| Model family | 1d6ff883 | classical machine learning | (none) |
| Model family | 0a51c163 | deep learning, physics-informed machine learning | deep learning |
| Model family | 1223e044 | classical machine learning, ensemble learning | classical machine learning |
| Model type | 01413cdf | random forest | lefse, random forest, redundancy analysis |
| Model type | 1d6ff883 | machine-learning interatomic potential | (none) |
| Model type | 0a51c163 | physics-informed neural network | neural network, physics-informed neural network |
| Model type | 11c8cad1 | long short-term memory | long short-term memory, recurrent neural network |
| Model type | 0e4e2c11 | chatgpt, claude, gemini, large language model | claude, gemini, gpt, large language model |
