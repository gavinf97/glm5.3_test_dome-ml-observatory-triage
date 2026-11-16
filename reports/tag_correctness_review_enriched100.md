# Correctness review: GLM-5.3-Flash vs DeepSeek V4.1-Flash modelling tags (enriched100)

Reviewed 2026-11-05. One reviewer (Claude) read each of the 100 abstracts and judged `learning_paradigm`, `model_family` and `model_type` against what the title and abstract support, which is the only input either model sees. MeSH headings and author keywords were pulled from PubMed for the 72 records with a PMID and used as an independent check where present. The EDAM domain fields were looked at only briefly.

## Result

Per field, which model's tags were more correct (ties = both acceptable, or the same):

| Field | Tie | DeepSeek better | GLM better | Both wrong |
|---|---:|---:|---:|---:|
| learning_paradigm | 91 | 6 | 2 | 1 |
| model_family | 66 | 24 | 8 | 2 |
| model_type | 57 | 28 | 14 | 1 |

Approximate share of records with acceptable tags (ties plus own wins, minus shared errors):

| Field | DeepSeek | GLM |
|---|---:|---:|
| learning_paradigm | ~97% | ~93% |
| model_family | ~87% | ~71% |
| model_type | ~85% | ~71% |

## GLM's errors are systematic, so they are fixable

1. **Missing `ensemble learning`.** When `model_type` includes random forest, XGBoost, gradient boosting, CatBoost or causal forest, GLM adds `ensemble learning` 2/20 times on enriched100 and 15/51 on wave1. DeepSeek does it 17/22 times. This alone accounts for 13 of GLM's 24 family losses. GLM misses `dimensionality reduction` for PCA the same way (1/2 and 4/9). The seed vocabulary already holds the answer: every tree ensemble's `family_hint` is "classical machine learning + ensemble learning". But the e1 prompt shows only canonical names and aliases, not the hints.
2. **Non-model items in `model_type`.** 26/100 GLM records against 9/100 DeepSeek records. Examples: explainability (SHAP), tasks (semantic segmentation, NER), simulations (molecular docking, MD, path-integral Monte Carlo), optimisers and constraints, components (attention mechanism, Mish activation) and family names (deep learning).
3. **Types from outside the abstract.** Examples: CNN for the qER tool, k-means where the abstract says only "clustering", YOLO/MobileNet for CFRDet, transformer for ProteinTalks. There were about 6 of these, against about 3 for DeepSeek (e.g. UMAP for a SCENIC paper).
4. **Second paradigm dropped.** GLM gives two paradigms on 5/100 records, DeepSeek on 12/100. DeepSeek is usually right when it adds `unsupervised` for a real clustering or embedding step (e.g. the VGAE embeddings in DeepSMCA, the clustered CNN filters, the MLIP plus clustering paper).

## DeepSeek's errors

- **Guesses `classical machine learning` when the abstract names no algorithm** (6 records, e.g. the piezo sensor, RAxML-NG, REAP, the hybrid COTS model). In these cases GLM's empty family is the honest answer.
- **Counts statistics and pharmacology tools as model types.** Examples: LEfSe, RDA, Limma, LISA, Bliss independence, IUPred3.
- **Uses the wrong canonical name in two records.** It wrote "multilayer perceptron" for "ANN"/"BP-ANN", where the prompt's alias maps those to "neural network".

## MeSH cross-check

MeSH coverage of ML methods is thin. Only 12/100 enriched100 and 45/250 wave1 records have an ML-specific heading, beyond the generic "Machine Learning" or "Artificial Intelligence". Where one is present, DeepSeek's tags agree 13/13 and GLM's 11/13. GLM's two misses are the ensemble and PCA family gaps above. For wave1, GLM agrees 46/51. Three of the misses are records MeSH files as "Supervised Machine Learning" that GLM calls semi-supervised; MeSH has no semi-supervised heading, so these may not be GLM errors.

## Top-level EDAM domain

Most of the 26 domain_tier1 disagreements are boundary calls between overlapping EDAM terms: Biology, Biomedical science, Medicine, Omics and Computational biology. GLM leans towards Omics and Biomedical science; DeepSeek leans towards Biology and Computational biology. About 2–3 of the 26 look clearly wrong, e.g. DeepSeek's "Experimental design and studies" for an urban heat-island paper. The 74% agreement figure overstates the quality gap.

## Vocabulary: what is too rigid

`reinforcement` already sits at the same level as supervised, unsupervised and semi-supervised (MeSH D000098408), which is the textbook three-paradigm split plus semi-supervised. GLM's one "reinforcement learning" violation was correct in substance (temporal-difference learning, Bellman equations); only the label was off.

Gaps seen in this sample (MeSH has none of these; the AIO IDs below were checked on OLS4 on 2026-11-05):

| Gap | Records here | What the models did | Possible term |
|---|---|---|---|
| Pretrained model applied or prompted, nothing trained in the paper (AlphaFold, qER, LLM prompting, agent pipelines) | ~11 | Inconsistent: `supervised` for AlphaFold and qER, `[]` for most LLM papers, and once `unsupervised` (DeepSeek) and `supervised` (GLM) for the same prompting paper | A separate `model_use` axis: trained here / fine-tuned / applied as-is / prompted (zero- or few-shot; AIO:ZeroshotLearning) |
| Self-supervised or contrastive pretraining (ProteinTalks, stPainter, protein LM embeddings, contrastive NER) | 4–5 | Filed under `unsupervised` or left out | `self-supervised` paradigm (AIO:SelfsupervisedLearning) |
| Active learning, closed-loop design | 2 | Written into `model_type` | `active learning` family or strategy (AIO:ActiveLearning) |
| Weak supervision (MIL) | 1 | `semi-supervised` (DeepSeek) or `supervised` (GLM) | Extend the semi-supervised definition |
| Multimodal fusion | 2 | Not captured | `multimodal learning` family (AIO:MultimodalLearning) |
| Physics-informed ML | 3 | Not captured | Family extension |

There are also policy gaps in `model_type` that both models resolve inconsistently:
- Is WGCNA a model? Each model includes it in some records and not others.
- Are hyperparameter optimisers such as PSO and genetic algorithms model types?
- Should explainability methods, statistical tests and tools be excluded?

Each of these needs an explicit rule.

## Suggested fixes (for a future e2 prompt; e1 stays frozen in this test)

1. Backfill `model_family` from the seed vocabulary's `family_hint` after parsing. This is deterministic and needs no model change. It would close most of GLM's family gap.
2. Add a `model_type` exclusion rule to the prompt: no explainability methods, statistical tests or packages, tasks, simulations, docking, optimisers, model components or family names.
3. Normalise "<term> learning" to "<term>" for paradigm labels.
4. Add `self-supervised` and a separate model-use axis before scaling up, because LLM and foundation-model papers are a growing share of the corpus.

## Appendix: per-record judgements

`=` tie, `DS`/`GLM` that model's tags are better, `X` both wrong.

```
0 0068c72a GMM MAP-EM: para= fam= type DS (GLM over-splits: "graph-Laplacian regularization", "split-merge clustering" are components not models)
1 00a9c984 GeoAI transfer: para= fam= type GLM (DS put "transfer learning" as a model type; arch unnamed -> [] right)
2 00ad5da0 MKRR: para= fam= type DS (GLM adds "SOAP descriptor-based kernel regression", "kernel learning": descriptor/dup)
3 00cd1e41 KNN ICU: = = = (RF via Boruta vs Boruta: both defensible; 7 algos unnamed)
4 00d52ca1 NN Salmonella: = = =
5 00f598e1 UCS soil: para= fam DS (RF/XGB/CatBoost -> ensemble learning; GLM missed) type GLM (BP-ANN -> canonical alias is "neural network"; DS "multilayer perceptron" wrong canonical; both list PSO, an optimiser)
6 00fb2eef stPainter latent diffusion: para= fam DS-ish (pretrained atlas applied w/o retraining -> transfer) type= (DS autoencoder inferred from "latent")
7 01008f73 piezo sensor, ML unnamed: para= fam GLM (DS guessed classical ML with no evidence) type=
8 013bdf07 LIR AlphaFold3: para= fam= type GLM (DS lists IUPred3, not ML)
9 01413cdf soil RF+LEfSe+RDA: = = type GLM (DS lists LEfSe and RDA: statistics, not ML)
10 01bfb6d2 biochar XGB/RF/SVM/LR: para= fam DS (ensemble) type=
11 01d876f8 SCZ coexpression + classifier: para DS (modules unsupervised + diag classifier) fam DS (GLM [] while tagging WGCNA type) type= (GLM WGCNA inferred, not named)
12 0208c801 MaxEnt: = = =
13 028e5948 Mamba SOD: para= fam GLM (DS "representation learning" unwarranted) type= (DS lists Mamba and SSM twice)
14 02e7c13c NSCLC WGCNA+XGB/RF/LASSO/SVM: para DS-ish (WGCNA unsup) fam= type GLM (adds WGCNA)
15 02f3e037 stocks DL: = = =
16 030aac5c furanocoumarin PCA: para= fam= type DS (GLM adds "molecular docking", "scaffold-aware machine learning")
17 033285f2 fluoride XAI: = = =
18 036c9364 causal forest: para= fam DS (causal forest = tree ensemble) type= (both list lin/log regression used as stats)
19 039cafeb MI RF: para= fam DS (ensemble) type=
20 03cf18e2 ViT+ClinicalBERT GMU: para= fam= (DS transfer, GLM NLP; ideal has both) type=
21 0401dd8d DeepSMCA VGAE+ResNetDNN: para DS (VGAE embeddings unsup + classifier) fam DS (representation learning) type GLM (DS adds Bliss independence, a pharmacology model)
22 04846937 active learning alloys: = = = (both put "active learning" as type; underlying learner unnamed) VOCAB GAP: active learning
23 059ff917 AlphaFold2: para= fam= type DS (GLM adds molecular docking)
24 06471288 nnU-Net: = = type DS (GLM adds "semantic segmentation", a task)
25 06e5d53a LLM tumour board: para= ([] both; VOCAB GAP no 'prompted/pretrained use') fam DS-ish (LLM pipeline w/ guidelines -> AI agent/genAI plausible) type=
26 073a0beb PPG LR+HGB: para= fam DS (ensemble) type= (GLM 'histogram gradient boosting' more exact, not canonical)
27 0772cfc8 perovskite: = = =
28 07bd6d78 snRNA clustering: para= fam= type DS (GLM adds DE analysis, motif enrichment, pseudotime: not ML)
29 081a8c78 oncoPredict+WGCNA: para GLM (WGCNA unsup) fam= type GLM (oncoPredict verbatim; DS 'ridge regression' inferred)
30 0891e384 scRNA SCENIC/CellChat/NicheNet: para= fam X (DS over-infers ensemble/DR; GLM []) type X (DS hallucinates UMAP + RF from SCENIC internals; GLM lists tools + "single-cell RNA-seq analysis")
31 089d314c multilingual model: para= fam= (both add unstated DL; DS adds transfer) type GLM (DS adds linear regression = hypothesis test)
32 099d073f SPIA SVM/LASSO/RF/XGB: para= fam DS (ensemble) type=
33 09a1fe63 COPZ1 4 unnamed algos: = = =
34 0a190435 LASSO (+WGCNA named): = = = (DS lists WGCNA here; GLM lists it elsewhere -> both inconsistent on WGCNA)
35 0a51c163 PINN: = = =
36 0a891883 qER CT head: para= fam= type DS (qER verbatim; GLM 'convolutional neural network' is from outside knowledge, not abstract)
37 0a8cd982 metabolomics RF + hier clust: para= fam DS (ensemble) type=
38 0b2baf39 RCA service graph: para= fam GLM (DS guessed classical ML) type=
39 0b4d99b1 Landsat SVM: = = =
40 0bdd7ec7 BDLO MLP-mixer: = = = (GLM adds BDLO, the proposed operator: fine)
41 0befe16e CNN filters clustered vs fMRI: para DS (filters clustered) fam DS type DS (clustering)
42 0c35feeb DL-assisted PIMC: para= fam= type DS (GLM: 'deep learning' family as type + PIMC simulation)
43 0c468b23 open-vocab food detection, weak sup MIL: para= (DS semi-sup closest to weak sup; VOCAB GAP weakly/self-supervised) fam= (DS transfer+rep; GLM NLP) type= (GLM vision-language model inferred, plausible)
44 0cda17de WAAM LR->RF cascade: para= fam DS (ensemble) type DS (GLM adds k-of-n filtering)
45 0cece43f Ikorodu RF + XGB SHAP: para= fam DS (ensemble) type DS (GLM lists SHAP)
46 0d1656ab COTS hybrid ML: para= fam GLM (DS ensemble unsupported) type GLM-ish ('hybrid machine learning' verbatim; vague)
47 0d4e123b LLM Angoff: = = =
48 0d5c57b9 GP classification: = = =
49 0d8849a4 REAP RankReg closed loop: para= fam GLM (DS classical ML unsupported) type GLM (active learning captured) VOCAB GAP active learning
50 0da4489b ASEAN XGB+PLS-SEM: para= fam DS (ensemble; MeSH 'Boosting ML Algorithms' agrees) type GLM (DS adds linear regression [not in abstract], SEM, SHAP)
51 0daf1929 FEDRA embeddings+clustering: para= fam DS (adds classical ML for clustering) type DS (GLM 'k-means' not named; both wrongly list LLM, which is only the benchmark)
52 0db0d71a trait impressions pretrained DNNs: para= fam GLM (DS classical ML unsupported) type DS (GLM adds 'multimodal fusion', 'temporal integration' = operations)
53 0dc3db1c flu ML unnamed: = = =
54 0dfa1417 semi-sup cross-lingual NER: para= fam= (DS misses NLP; GLM misses transfer/rep) type DS (GLM lists NER task, distillation, contrastive learning)
55 0e30576b readmission LR: = = =
56 0e4e2c11 LLMs design proteins (prompting): para X (DS unsupervised, GLM supervised; nothing trained -> [] ) fam= type DS (Claude/Gemini named; GLM drops them, adds 'transformer') VOCAB GAP prompting/zero-shot
57 0e60ef7e RAxML-NG ML branch support: para= fam GLM (DS classical ML unsupported) type=
58 0ede2643 FTIR PCA/HCA/PLS: para= fam DS (dimensionality reduction for PCA; MeSH 'Principal Component Analysis') type=
59 0ee90f22 1D-CNN sensor: = = =
60 0efe592d ProRB LM embeddings: = = = (DS rep learning plausible)
61 0f2d4fa9 endometriosis SHAP: para= fam X (model unnamed; DS guesses classical, GLM []) type DS (GLM lists SHAP as a model)
62 0f3e9738 ZIF NN classifiers: para= fam= (depth unknown; DS classic NN, GLM DL) type DS (canonical 'neural network')
63 0f6a5999 MCKG-SL RGCN+GAT: = = =
64 0f7b3fdf MLIP glasses: para= fam DS (arch unstated; GLM asserts DL) type DS (GLM adds 'neural network' unstated)
65 10339cc8 NN friction: = = =
66 1038453d MLIP + unsup clustering: para DS (MLIP supervised + clustering) fam= type=
67 10fbecb5 insulinoma LR: = = =
68 11c8cad1 LiSep LSTM: para= fam= type DS (GLM lists LSTM twice)
69 1223e044 gamma dose SVM/LR/RF/DT: = = = (BOTH miss ensemble for RF here)
70 12920b7e HS-MIND multi-agent LLM: = = = (both list RAG/CoT techniques as types)
71 13933e0a XGBoost condensates: = = = (BOTH miss ensemble)
72 14122ec7 wheat genomic prediction: para= fam= type DS (GLM 'parametric model','non-parametric model' are not types)
73 141418e7 PLS-DA: = = =
74 1455518b rivaroxaban LASSO/RF/XGB: para= fam DS (ensemble) type=
75 14a31795 NSDC corpus agent pipeline: para DS ([] - nothing trained; GLM 'supervised' wrong) fam= type= (both list tasks)
76 1530c987 TB proteomics Limma + 4 unnamed ML: para= fam= type GLM (DS lists Limma, a stats package)
77 155dfcd7 ProteinTalks: para= fam= type DS (GLM 'transformer' not in abstract)
78 155e52ba MLP scRNA AD: = = =
79 1628fb23 CFRDet jujube: para= fam= type DS (GLM adds YOLO, MobileNet not named; 'attention mechanism', 'Mish activation' are components)
80 16358ea8 wavelet eggshell: para= fam= type DS (GLM 'Wavelet transform' = feature eng, 'linear regression' not named)
81 17032311 PM2.5 XGB-SHAP + LISA: para GLM (DS counts LISA spatial stats as unsupervised ML) fam DS (ensemble) type= (DS LISA, GLM SHAP: one non-model each)
82 17905774 FAERS LASSO+BCPNN: = = =
83 194b17af PRS RF/XGB: para= fam DS (ensemble) type=
84 1952c67a GPR shoreline: = = =
85 199266e1 NLP expert system: = = =
86 1a1eda99 SPICE RL+pseudo-labels: = = = (identical, good: reinforcement + semi-supervised)
87 1a40f4a5 churn LR/RF/GB: = = = (BOTH miss ensemble)
88 1a46bb7e XGB conformal: para= fam DS (ensemble) type=
89 1a5849e3 motor ANN/HPSO-SVM/NB/SOGA-DT: para= fam DS (classic NN for ANN; GLM typed NN but no NN family) type GLM (ANN -> canonical 'neural network'; DS MLP)
90 1a7c2149 MetaboAnnotate LLM multiagent: para= fam= type DS (DS also lists the orchestrated ML tools SIRIUS/FLARE/JESTR)
91 1acc9fc6 multi-task elastic net: para= fam= type DS (GLM drops multi-task EN, adds MIC feature selection)
92 1b4a4da1 fairness credit: para= fam= type DS (GLM adds constraints, 'balanced accuracy optimization', 'Pareto-optimal analysis')
93 1bceb53b microbiome AI unnamed: = = =
94 1c39f3d0 Vib2Conf MoE: para= fam GLM (DS ensemble for MoE + representation learning dubious) type= (DS 'attentional resampler' component; GLM 'transformer' inferred)
95 1cf3209b TRPV1 virtual screening: para= fam= type DS (GLM adds shape similarity, MD simulation, generic 'ML-based classification models')
96 1d13afc3 battery CE physics-guided: para= fam= type DS (GLM 'physics-guided ML', 'explainable ML' not types)
97 1d1de6f4 Cell Painting sPLS-DA: = = =
98 1d3c7859 butyrate ensemble ML: = = =
99 1d6ff883 ML-MD Cu-Ag: para= fam DS (arch unstated) type GLM (MLIP is the evident method)
```
