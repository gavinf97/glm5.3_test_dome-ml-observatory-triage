# Rating rubric: GLM-5.3-Flash enrichment tags (prompt e2)

This rubric is used by both raters: the human (in `rate_app.py`) and the Opus 5.5 judge (`judge_opus.py`). The judge receives the section between the two `RATER INSTRUCTIONS` markers word for word, so edit only before rating starts. Its sha256 is recorded in each judge run.

**What you see:** the paper's title, abstract, journal and year, and the tags GLM gave it.
**What you do not see:** GLM's rationale, the other rater's verdicts, and anything outside the abstract.

<!-- RATER INSTRUCTIONS START -->
## Task

You are checking tags that a model gave a scientific paper, using only the paper's title, abstract, journal and year. The paper is already known to describe the use or development of an AI/ML method. For each of five rating units, decide whether the tags are right for this paper.

Judge the tags against what the title and abstract support, and against the tagging rules and vocabularies the tagger was given (they are provided). Do not use outside knowledge of the paper. You may use well-established knowledge of a named model (e.g. AlphaFold2 is deep learning, GPT-4 is a large language model), but not guesses about unnamed methods.

## The five units

| Unit | Tags it covers | Closed vocabulary? |
|---|---|---|
| domain | domain_tier1 (max 1), domain_tier2 (max 2), domain_tier3 (max 3): EDAM topics, judged together as one subject description | yes |
| learning_paradigm | supervised, unsupervised, semi-supervised, reinforcement, self-supervised (max 2) | yes |
| model_family | e.g. classical machine learning, deep learning, ensemble learning, dimensionality reduction, large language model (max 3) | yes |
| model_type | the specific ML models, algorithms or named trained tools | no (canonical spellings preferred) |
| model_use | trained in this study, fine-tuned or adapted, pretrained applied as-is, prompted (zero/few-shot) (max 2) | yes |

An empty list `[]` is a tag value like any other: it is correct when nothing applies (e.g. learning_paradigm `[]` when the paper trains nothing; model_type and model_family `[]` when the abstract names no algorithm and no family).

## Verdicts

Give each unit exactly one verdict.

- **correct**: the tags are what a careful curator would assign from this abstract. Nothing important missing, nothing wrong added.
- **minor**: usable as they stand. Someone searching the database would still find the paper correctly. There is one small problem: a secondary item missing, one harmless extra item, a near-miss spelling, or a defensible alternative choice.
- **major**: wrong or misleading. The main model, paradigm, family, use or subject is missing, a wrong tag would put the paper in the wrong search results, or most of the tags are unsupported.
- **unsure**: the abstract genuinely cannot settle it. Use sparingly; do not use it for hard but decidable cases.

"Acceptable" in the analysis means correct or minor.

Rate what is there, not how it was phrased. If two tag sets are equally defensible, the tagger's choice is correct.

## Error codes (tick all that apply to a minor or major verdict)

- **missing**: a tag the abstract clearly supports is absent.
- **unsupported**: a tag is present that the title and abstract do not support (guessed or hallucinated).
- **wrong_term**: the right idea, but the wrong vocabulary term or level (e.g. wrong family, wrong EDAM tier, 'neural network' where the abstract names a CNN).
- **not_a_model**: model_type contains something that is not an ML model (an explainability method, a task, a statistic, a pipeline, a simulation, a component).
- **vocab**: a term outside the closed vocabulary, or more terms than the cap allows.

## Rules and worked judgements per unit

### learning_paradigm
- Describes learning done IN THIS PAPER. If the paper only applies or prompts an existing model and trains nothing, `[]` is correct and `supervised` is major (`unsupported`).
- Two paradigms are expected when the paper has a distinct second learning step (e.g. clustering or dimensionality reduction plus a supervised classifier; self-supervised pretraining then supervised fine-tuning). Missing the secondary one is minor; missing the main one is major.
- `semi-supervised` covers weak supervision, multiple-instance learning and pseudo-labelling.
- Examples: a paper that fine-tunes a pretrained CNN on labelled images → `supervised` correct. A paper that clusters patients with k-means and then trains a random forest on the clusters → `unsupervised, supervised` correct; `supervised` alone is minor. A paper prompting GPT-4 → `[]` correct.

### model_family
- Every listed model type needs its family: tree ensembles (random forest, XGBoost, gradient boosting, CatBoost, bagging, stacking) need `ensemble learning` as well as `classical machine learning`; PCA, UMAP, t-SNE, NMF need `dimensionality reduction`. Missing `ensemble learning` or `dimensionality reduction` when the main family is present is **minor** (`missing`). Missing the main family is **major**.
- A plain 'neural network'/ANN/MLP is `classic neural network` unless the abstract says it is deep or names a deep architecture; using `deep learning` for a plain ANN is minor (`wrong_term`).
- When the abstract names no algorithm and no family, `[]` is correct; guessing `classical machine learning` there is minor (`unsupported`) if a model clearly exists, major if the guess points the wrong way (e.g. `deep learning` for an unnamed method).
- The cap is 3. When more families apply, choosing the 3 that describe the main models is correct; dropping the main one to fit the cap is major.

### model_type
- List every distinct ML model the paper uses, develops, applies or prompts, as named in the abstract. Canonical spellings (e.g. 'random forest', 'support vector machine', 'XGBoost') are preferred; a correct method in a different spelling is still correct.
- NOT model types: explainability methods (SHAP, LIME, Grad-CAM); statistical tests and packages (Limma, DESeq2, LEfSe, Mendelian randomization, survival curves, regression used only to test associations); pipelines and network analyses (WGCNA, SCENIC, CellChat, pseudotime); tasks (segmentation, classification, NER); simulations (docking, molecular dynamics, DFT); components and techniques (attention, dropout, data augmentation, RAG, chain-of-thought); family names or generic phrases ('machine learning', 'deep learning', 'neural network classifier'); optimisers that only tune another model.
- Stated clustering the authors run (k-means, hierarchical clustering, latent class/profile analysis) and baseline models the authors train and compare ARE model types. Dropping them is minor if the main model is still there, major if the main model is lost.
- An architecture the abstract does not name (e.g. 'convolutional neural network' added for a commercial tool whose architecture is not given) is `unsupported`: minor if it is one extra item beside correct ones, major if it replaces the real model.
- A non-model item alongside the right models is minor (`not_a_model`); non-model items as the only or main types are major.
- Missing the paper's main model is major. Missing one of several secondary baselines is minor.

### model_use
- `trained in this study`: the paper fits or trains the model on its own data (including training a published architecture from scratch).
- `fine-tuned or adapted`: a pretrained model is further trained, fine-tuned or transfer-learned on the paper's data.
- `pretrained, applied as-is`: an existing trained model or tool is run without further training.
- `prompted (zero/few-shot)`: a pretrained model (usually an LLM) is used through prompts, with no weight updates.
- Two values are expected when the paper both trains its own model and applies or prompts another. Missing the secondary one is minor; a wrong main value (e.g. `trained in this study` for a paper that only prompts ChatGPT) is major.

### domain
- Judge the three tiers together as one description of the paper's subject. The tiers are EDAM topics, and neighbouring terms overlap (Biology, Biomedical science, Medicine, Omics, Computational biology). A defensible choice among overlapping terms is correct.
- The tier-1 term sits on a different branch from the paper's main subject (e.g. 'Physics' for a clinical prediction paper): major. A tier-2/3 term that is off but does not mislead: minor. Over the caps: minor (`vocab`).
- Empty tiers are acceptable when nothing in the vocabulary fits at that depth.

## Process
1. Read the title and abstract first, before looking at the tags.
2. Decide what you would tag for model_use, learning_paradigm, model_type, model_family and domain.
3. Compare with the tagger's tags and give each unit a verdict, error codes and (for minor and major) one short sentence saying what is wrong.
<!-- RATER INSTRUCTIONS END -->

## Notes for the human rater

- Keyboard in the rating app: `1` correct, `2` minor, `3` major, `4` unsure for the selected unit; `↑`/`↓` move between units; `→` or `n` next paper; `←` previous.
- Ratings save as soon as you click. Changing a verdict appends a new row; the latest one counts.
- About 1–2 minutes per paper. Take breaks; there is no need to do the 150 in one sitting.
- For minor and major, a short note helps adjudication later.
