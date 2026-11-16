# GLM-5.3-Flash vs DeepSeek V4.1-Flash: how often they give the same tags

Both models tagged the same 100 papers. DeepSeek used prompt e1; GLM-5.3-Flash used the same prompt (e1) and vocabulary. A field counts as agreeing when both models chose exactly the same terms.

GLM run: 100 of 100 papers tagged, 0 unreadable answers, 0 cut off at the length limit.

| Field | GLM-5.3-Flash and DeepSeek agree | For comparison: DeepSeek agrees with its own previous version |
|---|---:|---:|
| Domain, top level (EDAM tier 1) | 74% | 95% |
| Domain, tier 2 | 39% | 43% |
| Domain, tier 3 | 29% | 28% |
| Learning paradigm | 89% | 87% |
| Model family | 58% | 77% |
| Model type | 38% | 45% |
| **All six fields at once** | **4%** | **4%** |

**How to read this.** The right-hand column is DeepSeek V4.1 against DeepSeek V4 on the same kind of
papers (2026-09-15). Where GLM's figure is close to it, GLM differs from DeepSeek about as much as
DeepSeek differs from itself. Where it is well below, GLM tags that field differently.

Agreeing is not the same as being right: two models can agree on a wrong tag, or disagree where both
tags are defensible. For which model is correct, see `tag_correctness_review_enriched100.md`.

## Run profile

| | GLM-5.3-Flash | DeepSeek V4.1-Flash |
|---|---:|---:|
| Papers with a tag outside the vocabulary | 4% | 0% |
| Input tokens per paper | 3,144 | 3,119 |
| Share of input served from the prompt cache | 74% | 82% |
| Output tokens per paper | 375 | 1,829 |
| of which reasoning | 228 | not stored |

## Examples of disagreement

Up to 5 per field. Record IDs are shortened to their first 8 characters.

| Field | Record | GLM-5.3-Flash | DeepSeek |
|---|---|---|---|
| Domain, top level (EDAM tier 1) | 0ee90f22 | physics | chemistry |
| Domain, top level (EDAM tier 1) | 0a190435 | medicine | biomedical science |
| Domain, top level (EDAM tier 1) | 1d3c7859 | omics | medicine |
| Domain, top level (EDAM tier 1) | 089d314c | literature and language | computer science |
| Domain, top level (EDAM tier 1) | 0cece43f | computer science | experimental design and studies |
| Domain, tier 2 | 0a891883 | medical informatics, oncology | imaging, medical informatics |
| Domain, tier 2 | 0ee90f22 | biophysics | biotechnology, machine learning |
| Domain, tier 2 | 1223e044 | environmental science | environmental science, public health and epidemiology |
| Domain, tier 2 | 09a1fe63 | bioinformatics, machine learning | bioinformatics, genomics |
| Domain, tier 2 | 0a51c163 | applied mathematics, machine learning | environmental science, machine learning |
| Domain, tier 3 | 0a891883 | medical imaging | medical imaging, preclinical and clinical studies, tomography |
| Domain, tier 3 | 01413cdf | metagenomic sequencing, metagenomics | metagenomics, microbial ecology |
| Domain, tier 3 | 0ee90f22 | biomaterials | bioengineering, biomaterials |
| Domain, tier 3 | 1223e044 | (none) | safety sciences |
| Domain, tier 3 | 1d3c7859 | copy number variation, molecular medicine, transcriptomics | gene expression, molecular medicine, transcriptomics |
| Learning paradigm | 01d876f8 | supervised | supervised, unsupervised |
| Learning paradigm | 0befe16e | supervised | supervised, unsupervised |
| Learning paradigm | 17032311 | supervised | supervised, unsupervised |
| Learning paradigm | 0891e384 | unsupervised | supervised, unsupervised |
| Learning paradigm | 0e4e2c11 | supervised | unsupervised |
| Model family | 0f3e9738 | deep learning | classic neural network |
| Model family | 06e5d53a | large language model | ai agent, generative ai, large language model |
| Model family | 089d314c | deep learning, natural language processing | deep learning, natural language processing, transfer learning |
| Model family | 0cece43f | classical machine learning | classical machine learning, ensemble learning |
| Model family | 0a8cd982 | classical machine learning | classical machine learning, ensemble learning |
| Model type | 0a891883 | convolutional neural network | qer eu 2.0 |
| Model type | 01413cdf | random forest | lefse, random forest, redundancy analysis |
| Model type | 0a190435 | lasso | lasso, weighted gene co-expression network analysis (wgcna) |
| Model type | 0f3e9738 | neural network classifier | neural network |
| Model type | 089d314c | multilingual machine learning model | linear regression, multilingual machine learning model |
