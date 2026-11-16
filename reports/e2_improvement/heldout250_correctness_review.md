# Held-out correctness review: GLM-5.3-Flash, prompt e1 vs EXPERIMENTAL prompt e2 (heldout250)

Reviewed 2026-11-05. The cohort is 250 confirmed AI/ML positives that appear in no earlier cohort, so e2 was never tuned on them. They were drawn by `scripts/export_heldout.py` from the triage repository's local landscape exports, with seed 20261105, a year band × preprint/article stratification and at most 2 papers per journal; the manifest is in `cohorts/heldout_manifest.csv`. Each paper was tagged twice by GLM-5.3-Flash at reasoning effort high, once with prompt e1 and once with prompt e2.

**Method.** One reviewer (Claude) read every title and abstract, with MeSH headings and author keywords where present (96 of 250 papers). For each paper the reviewer judged whether each prompt's learning_paradigm, model_family and model_type tags were acceptable. For e2 the reviewer also judged model_use. The standard was the same for both prompts:

- Model types must be ML models or named trained tools stated in the abstract.
- Families must cover the types listed.
- Paradigms describe learning done in the paper.

Each prompt was judged against its own vocabulary, so e1 was not marked down for lacking a term that only e2 has.

**Limitations.**
- There was one reviewer, and not a blind one: the same reviewer designed e2.
- The judgements are made against the abstract only.
- No DeepSeek tags exist for these papers (the local exports carry none), so DeepSeek is compared only on enriched100.
- The cohort leans towards 2025–2026 papers, because the local exports are mostly incoming records.

A spot check by a human curator is recommended before relying on these figures.

## Result

| Field | e1 acceptable | e2 acceptable | e2 fixed | e2 broke | Both wrong |
|---|---:|---:|---:|---:|---:|
| learning_paradigm | 239/250 (96%) | 244/250 (98%) | 10 | 5 | 1 |
| model_family | 201/250 (80%) | 239/250 (96%) | 49 | 11 | 0 |
| model_type | 156/250 (62%) | 224/250 (90%) | 83 | 15 | 11 |
| **All three right** | **119/250 (48%)** | **218/250 (87%)** | | | |
| model_use (e2 only) | | 248/250 (99%) | | | |

For comparison, the first review put DeepSeek V4.1 at about 87% acceptable for family and 85% for type on enriched100. That is a different set of papers, so treat the comparison as indicative only.

## What e2 fixed

- **Families now follow the model types.** e1 left out `ensemble learning` for tree ensembles in 21 of 29 such papers; e2 left it out in none. e2 also adds `dimensionality reduction` for PCA, NMF and factor analysis.
- **Non-model items removed from model_type.** These include SHAP, Boruta, nomograms, restricted cubic splines, WGCNA, GSVA and ssGSEA, SMOTE, docking and molecular dynamics, attention modules, LoRA and RAG, and task names such as segmentation and open-set recognition.
- **No guessing on unnamed methods.** When the abstract names no algorithm, e2 leaves family and type empty. e1 guessed `classical machine learning` in about 20 such papers.
- **Pretrained and prompted models handled consistently.** These are papers that apply AlphaFold, SpliceAI, commercial imaging tools or Stable Diffusion, or that prompt LLMs. e2 sets model_use correctly and leaves learning_paradigm `[]`. e1 tagged most of them `supervised`, and one `unsupervised`.
- **The new terms were used where they fit:**
  - `self-supervised` for masked-reconstruction pretraining, continued LLM pretraining and contrastive pretraining;
  - `multimodal learning` for image + clinical or multi-sensor fusion;
  - `physics-informed machine learning` for PINNs and physics-guided losses;
  - `fine-tuned or adapted` for transfer learning.

## Where e2 is worse (the 31 field regressions)

1. **It over-prunes and drops real models (about 10 papers).** It loses stated unsupervised clustering (176, 223, 247). It removes the trained baseline CNNs and the compared regression models (4, 186). It drops latent profile analysis (31) and protein-language-model embeddings (94). In one paper that benchmarks the clustering methods it runs, it empties every field (59). These come from applying the "benchmark-only tool" and "pipeline" exclusions too broadly.
2. **The family cap of 3 squeezes out `natural language processing`** in text papers (144, 234).
3. **Some non-model items remain.** These include tuning optimisers (35), majority voting (115), generic "tree-based models", "deep learning models" or "regression model" (128, 246, 249), "contrastive learning" as a type (240), and a physics method (97).
4. **A few paradigm slips:**
   - `self-supervised` for a pretrained model the paper did not pretrain (14);
   - `multimodal learning` placed in learning_paradigm (148);
   - `unsupervised` kept after WGCNA was excluded (123);
   - a logistic growth curve read as supervised logistic regression (211).
5. **Family over-reach.** It adds `deep learning` to a shallow reservoir network (5), and `physics-informed` where only the input features are physics-derived (195).

## Suggested next iteration (e3, not built)

- Say explicitly that stated clustering, latent class/profile analysis and baseline models the authors train **are** model types. The exclusions apply only to tools the paper does not itself run.
- Add a rule that any model trained on text gets `natural language processing`, and consider raising the model_family cap to 4.
- Say that `multimodal learning` is a family and never a paradigm, and that `self-supervised` applies only when the pretraining is done in the paper.
- Add generic phrases ("tree-based models", "regression model", "deep learning models") and "contrastive learning" to the exclusion examples.

## Appendix: per-record judgements

Each line gives: e1 paradigm, family and type; e2 model_use, paradigm, family and type (1 = acceptable, 0 = wrong); then a note. Record numbers are positions in the sorted cohort; IDs are the first 8 characters of record_id.

```
0 0199979d | E1 1 1 1 | E2 1 1 1 1 | LASSO+LR
1 019ce715 | E1 1 0 0 | E2 1 1 1 1 | E1 no ensemble for RF; Boruta (feature selection) as type
2 050230fc | E1 1 1 1 | E2 1 1 1 1 | NMF + Cox
3 053b74f9 | E1 1 1 0 | E2 1 1 1 1 | E1 generic 'regression model'
4 0578b126 | E1 1 1 1 | E2 1 1 1 0 | E2 DROPS the trained baseline CNNs (VGG16...) and transfer learning: over-applies comparator rule
5 06472e68 | E1 1 1 1 | E2 1 1 0 0 | E2 adds deep learning to a reservoir RNN; 'linear readout' component
6 079699dc | E1 1 0 1 | E2 1 1 1 1 | E1 no DR for PCA
7 07be7ccf | E1 1 1 1 | E2 1 1 1 1 |
8 0804b3dc | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
9 0865ac4a | E1 1 1 1 | E2 1 1 1 1 | E2 adds multimodal learning (good)
10 091298bd | E1 1 1 1 | E2 1 1 1 1 |
11 0ba84c92 | E1 1 0 0 | E2 1 1 1 1 | unnamed radiomics ML: E1 guesses classical + generic type; E2 [] []
12 0c66e27f | E1 1 0 0 | E2 1 1 1 1 | E1 no ensemble; Boruta, RCS as types
13 0eac774b | E1 1 1 1 | E2 1 1 1 1 | E2 self-supervised (good); E1 unsupervised = closest e1 term
14 0f1cfac6 | E1 0 1 0 | E2 1 0 1 1 | E1 semi-supervised wrong, 'transformer' unstated; E2 self-supervised although pretraining was not done in this paper
15 1082e4f2 | E1 1 1 0 | E2 1 1 1 0 | applied commercial DL-VMM: E1 generic 'neural network'; E2 drops the named tool
16 11ae9b7d | E1 1 1 1 | E2 1 1 1 1 | E2 physics-informed family (good)
17 14e48126 | E1 1 1 1 | E2 1 1 1 1 | Bayesian network
18 18602130 | E1 1 1 0 | E2 1 1 1 1 | E1 'domain adaptation', 'attention mechanism' as types
19 1984da77 | E1 1 1 1 | E2 1 1 1 0 | E2 'reinforcement learning framework' generic; E1 Q-learning (from Q-Score)
20 1c229942 | E1 1 1 0 | E2 1 1 1 1 | E1 WGCNA, GSVA as types
21 1dfaf922 | E1 1 0 1 | E2 1 1 1 1 | unnamed ML: E1 guesses classical
22 1e2c12f5 | E1 1 1 1 | E2 1 1 1 1 | GAM
23 1f32caf2 | E1 1 1 1 | E2 1 1 1 1 | DeepSurv
24 20ce8754 | E1 1 0 1 | E2 1 1 1 1 | E1 MLP->deep learning, no ensemble
25 2154e45c | E1 1 1 1 | E2 1 1 1 1 |
26 21a3738a | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
27 223cce16 | E1 1 1 1 | E2 1 1 1 1 |
28 22a33843 | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
29 23043264 | E1 1 0 1 | E2 1 1 1 1 | E1 'transfer learning' for a spectral transform
30 2353f56d | E1 1 1 1 | E2 1 1 1 1 | unnamed soft sensor
31 26852dc8 | E1 1 1 1 | E2 1 1 0 0 | E2 DROPS latent profile analysis (a canonical seed type)
32 26a08b68 | E1 1 1 0 | E2 1 1 1 1 | E1 'nomogram' as type; E2 multimodal + MIL as semi-supervised (per E2-V3)
33 29097064 | E1 1 1 1 | E2 1 1 1 1 |
34 2b2a68f6 | E1 1 1 0 | E2 1 1 1 1 | E1 SHAP as type
35 2b67729e | E1 1 1 0 | E2 1 1 1 0 | both list tuning optimisers + imputation as types (E2 breaks its own rule)
36 2d859d2b | E1 1 1 1 | E2 1 1 1 1 |
37 2e00cc3b | E1 1 1 1 | E2 1 1 1 1 |
38 305b6ac6 | E1 1 0 0 | E2 1 1 1 1 | commercial tools: E1 guesses DL, misses tool names; E2 applied-as-is, names tools
39 30707256 | E1 1 1 1 | E2 1 1 1 1 | stacked ensemble
40 30d8b078 | E1 1 1 1 | E2 1 1 1 1 |
41 3403c647 | E1 1 1 0 | E2 1 1 1 1 | E1 'instance segmentation' (task)
42 341256bb | E1 1 0 0 | E2 1 1 1 1 | E1 no ensemble, SHAP
43 3569cd58 | E1 1 0 1 | E2 1 1 1 1 | validation of existing text classifier: E1 guesses classical; E2 applied-as-is, NLP
44 35bfecd3 | E1 1 1 0 | E2 1 1 1 1 | E1 SMOTE as type
45 366200aa | E1 1 1 1 | E2 1 1 1 1 |
46 3731a4f4 | E1 1 1 0 | E2 1 1 1 1 | E1 types are techniques (attention, adversarial training, contrastive learning)
47 3744ef1a | E1 1 1 1 | E2 1 1 1 1 |
48 37a4ea04 | E1 1 1 0 | E2 1 1 1 1 | E1 'attention mechanism'; E2 multimodal (multi-source sensors)
49 3cb20992 | E1 0 1 1 | E2 1 1 1 1 | E1 paradigm [] for a newly trained model
50 3d126b17 | E1 1 1 1 | E2 1 1 1 1 |
51 3e12c129 | E1 1 1 0 | E2 1 1 1 1 | barely ML (GEE/ROC); E1 lists GEE, mediation, ROC analysis; E2 leaves all empty
52 3e36cca5 | E1 1 1 1 | E2 1 1 1 1 | applied AI-CO
53 3e3d3d3b | E1 1 1 1 | E2 1 1 1 1 | paper is about the preprocessing methods themselves
54 3eb4bb50 | E1 1 1 1 | E2 1 1 1 1 |
55 3f8e58e3 | E1 1 1 1 | E2 1 1 1 1 |
56 3fcb6952 | E1 1 1 0 | E2 1 1 1 1 | E1 'nomogram'
57 4042e8ef | E1 1 1 1 | E2 1 1 1 1 |
58 405b6de3 | E1 1 1 1 | E2 1 1 1 1 |
59 428b1603 | E1 1 1 1 | E2 0 0 0 0 | benchmarks clustering methods it runs: E2 calls it applied-as-is and empties everything
60 437a3c3b | E1 1 1 1 | E2 1 1 1 1 |
61 44dbbeba | E1 0 1 1 | E2 1 1 1 1 | prompted LLMs: E1 'supervised'; E2 prompted, []
62 46032b85 | E1 1 1 0 | E2 1 1 1 1 | E1 association regression as type
63 46d681cd | E1 1 0 0 | E2 1 1 1 1 | E1 no ensemble, TreeSHAP
64 478bdc3a | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
65 48d2c58f | E1 1 1 1 | E2 1 1 1 1 | deep RL
66 4903afba | E1 1 0 0 | E2 1 1 1 1 | unnamed: E1 generic + SHAP, guessed family
67 4a0d8cab | E1 1 1 0 | E2 1 1 1 1 | E1 finite element analysis as type
68 4ad3d4cc | E1 1 1 0 | E2 1 1 1 1 | E1 'open-set recognition' (task)
69 4ae1e67c | E1 1 1 0 | E2 1 1 1 1 | applied Theia3D/Pose2Sim: E1 generic task name
70 4aea47ae | E1 1 1 0 | E2 1 1 1 1 | applied SpliceAI: E1 adds CNN from outside knowledge
71 4aef64c3 | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
72 4bd209cf | E1 1 1 1 | E2 1 1 1 1 |
73 4c1870d3 | E1 1 1 1 | E2 1 1 1 1 |
74 4cf22248 | E1 1 0 0 | E2 1 1 1 1 | scRNA atlas: E1 invents UMAP/PCA/clustering not in abstract; E2 empty
75 4e3d0da8 | E1 1 1 1 | E2 1 1 1 1 | PhenoGraph + t-SNE
76 4e9525d3 | E1 0 1 0 | E2 1 1 1 0 | pretrained Mol2Vec: E1 'unsupervised' + Mahalanobis distance; E2 lists MSI (a similarity index)
77 4e96dc47 | E1 1 0 1 | E2 1 1 1 1 | E1 family empty
78 4f8f3a89 | E1 1 1 1 | E2 1 1 1 1 |
79 4fa55c03 | E1 1 0 0 | E2 1 1 1 1 | E1 no ensemble, WGCNA
80 512b9140 | E1 1 1 1 | E2 1 1 1 1 |
81 52220d19 | E1 1 1 1 | E2 1 1 1 1 |
82 53cc4d45 | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble for XGBoost
83 54336edc | E1 1 1 0 | E2 1 1 1 1 | E1 'vision language model', 'visual question answering'
84 5457f79b | E1 1 1 0 | E2 1 1 1 1 | E1 SHAP; E2 SAMNN + multimodal
85 54e95070 | E1 0 1 1 | E2 1 1 1 1 | applied Stable Diffusion: E1 'unsupervised'
86 55fc51e6 | E1 1 1 0 | E2 1 1 1 1 | WGCNA-only paper: E1 WGCNA as type; E2 empty
87 56c9d927 | E1 1 1 1 | E2 1 1 1 1 |
88 57551b1a | E1 1 1 0 | E2 1 1 1 1 | E1 techniques as types
89 57e5c1a1 | E1 1 0 1 | E2 1 1 1 1 | unnamed surrogate: E1 guessed classical
90 5d5f071e | E1 0 1 0 | E2 1 1 1 1 | E1 misses NetTCR retraining (supervised), lists silhouette score/TCRdist3
91 5db9569d | E1 1 1 0 | E2 1 1 1 1 | E1 LoRA, RAG as types; E2 continued pretraining = self-supervised (good)
92 5e3b4673 | E1 1 1 0 | E2 1 1 1 1 | E1 association regressions
93 5e60c3b5 | E1 1 1 0 | E2 1 1 1 1 | E1 Grad-CAM
94 5f3e8478 | E1 1 1 1 | E2 1 1 0 0 | E2 drops the protein language model embeddings (named family, deep) -> empty
95 5f93b8ca | E1 1 1 0 | E2 1 1 1 1 | E1 SHAP
96 61481e9b | E1 1 1 1 | E2 1 1 1 1 |
97 61d9908c | E1 1 1 1 | E2 1 1 1 0 | E2 adds 'multiscale CG force-matching' (physics method)
98 646ac343 | E1 1 1 1 | E2 1 1 1 1 |
99 65e7d8b1 | E1 1 1 0 | E2 1 1 1 1 | E1 'hidden Markov model' inferred from ichorCNA; E2 names ichorCNA
100 672c07d1 | E1 1 0 0 | E2 1 1 1 1 | E1 no ensemble; Boruta, SHAP
101 69212f4f | E1 1 1 0 | E2 1 1 1 1 | E1 'neural network' not stated
102 6a081fd5 | E1 1 1 1 | E2 1 1 1 1 | stacked ensemble
103 6a136b77 | E1 1 1 0 | E2 1 1 1 0 | both list phosphene stimulation encoders (not ML models) as types
104 6c1cf7f8 | E1 0 1 1 | E2 1 1 1 1 | LLM use: E1 'supervised'
105 6c2f4ef1 | E1 1 1 1 | E2 1 1 1 1 |
106 6d527b89 | E1 1 1 0 | E2 1 1 1 1 | E1 'persistent GLMY homology' (feature method)
107 6e0a68c8 | E1 1 0 0 | E2 1 1 1 1 | E1 no ensemble; Boruta, RFE, SMOTE, SHAP
108 6e48bed5 | E1 1 1 1 | E2 1 1 1 1 | EM algorithm
109 6f1d564d | E1 1 1 0 | E2 1 1 1 1 | E1 restricted cubic splines
110 7265ffd4 | E1 1 1 1 | E2 1 1 1 1 | Mask R-CNN transfer
111 759b871e | E1 1 1 0 | E2 1 1 1 1 | E1 nomogram
112 75cf0905 | E1 1 1 0 | E2 1 1 1 0 | E1 LoRA/contrastive loss as types; E2 generic 'foundation model'
113 7676e93c | E1 1 1 1 | E2 1 1 1 1 |
114 76baecdf | E1 1 1 1 | E2 1 1 1 1 | TabNet
115 783a353d | E1 1 1 1 | E2 1 1 1 0 | E2 'majority voting' as type
116 7934bc16 | E1 1 1 1 | E2 1 1 1 1 |
117 79be1008 | E1 1 1 0 | E2 1 1 1 1 | applied M2M DL: E1 generic 'neural network'
118 7aed16c0 | E1 1 1 1 | E2 1 1 1 1 | E2 masked-reconstruction pretraining = self-supervised (good)
119 7c163cb7 | E1 1 1 0 | E2 1 1 0 1 | E1 augmentation method as type; E2 leaves family empty although abstract says ML and DL models
120 7c9f14d7 | E1 0 1 1 | E2 1 1 1 1 | new ML model trained: E1 paradigm []
121 7e5c6e44 | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
122 7e8a428d | E1 1 1 0 | E2 1 1 1 1 | E1 linear regression not stated
123 7ea19a2b | E1 1 1 0 | E2 1 0 1 1 | E1 WGCNA; E2 keeps 'unsupervised' after excluding WGCNA (no unsupervised model left)
124 7fe48aea | E1 1 1 1 | E2 1 1 1 1 |
125 7fe5b248 | E1 1 1 1 | E2 1 1 1 1 |
126 80da5b95 | E1 1 0 0 | E2 1 1 1 1 | unnamed: E1 generic types + guessed family
127 824ecbee | E1 1 1 1 | E2 1 1 1 1 | NAS: evolutionary search is the method (E2-V8 correctly kept)
128 8280f81d | E1 1 1 1 | E2 1 1 1 0 | E2 'tree-based models', 'deep learning models' generic (breaks its rule)
129 8384f7cb | E1 1 1 1 | E2 1 1 1 1 |
130 83a2278f | E1 1 1 0 | E2 1 1 1 1 | E1 techniques/task as types; E2 ProViCNet, weak+contrastive
131 843d3715 | E1 1 1 0 | E2 1 1 1 0 | both list Boruta (feature selection)
132 84894e6d | E1 1 1 1 | E2 1 1 1 1 | applied UMA + ShiftML3
133 84a11c93 | E1 1 1 1 | E2 1 1 1 1 |
134 84d41870 | E1 1 1 1 | E2 1 1 1 1 | CNN/BiLSTM/transformer + WGAN-GP
135 854c4297 | E1 1 1 0 | E2 1 1 1 1 | E1 'fine-tuning' as type
136 8595059b | E1 1 1 0 | E2 1 1 1 1 | E1 BCH method, mediation model
137 8690c183 | E1 1 1 1 | E2 1 1 1 1 |
138 874b18fa | E1 1 1 0 | E2 1 1 1 1 | no ML: E1 lists molecular dynamics
139 876b74e2 | E1 1 1 1 | E2 1 1 1 1 |
140 87cc6bda | E1 1 1 1 | E2 1 1 1 1 | barely ML; both defensible
141 88077aa3 | E1 1 1 1 | E2 1 1 1 1 |
142 881e75dc | E1 1 1 0 | E2 1 1 1 1 | association study: E1 RCS; E2 empty
143 882fc714 | E1 0 1 1 | E2 1 1 1 1 | prompted ChatGPT-4: E1 'supervised'
144 8883995c | E1 1 1 0 | E2 1 1 0 0 | both list RegEx; E2 loses 'natural language processing' to the cap (LLM for BERT)
145 8a93eaec | E1 1 1 0 | E2 1 1 1 1 | E1 'multi-task learning' as type
146 8a94510d | E1 1 1 1 | E2 1 1 1 1 |
147 8b888bf3 | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
148 8bafc3bb | E1 1 1 1 | E2 1 0 1 1 | E2 puts 'multimodal learning' in learning_paradigm
149 8bfd445d | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
150 8f19dacf | E1 1 1 1 | E2 1 1 1 1 | logistic regression study; both defensible
151 8f2c5858 | E1 1 1 1 | E2 1 1 1 1 |
152 9126c7b0 | E1 1 1 1 | E2 1 1 1 1 |
153 91cc77ad | E1 1 0 0 | E2 1 1 1 1 | E1 generic type + guessed family; E2 multimodal, []
154 92dd72de | E1 1 1 1 | E2 1 1 1 1 |
155 9326bac0 | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
156 97899b42 | E1 0 1 1 | E2 1 1 1 1 | E1 misses unsupervised trajectory modelling
157 987147c6 | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
158 98bb3c6d | E1 1 1 1 | E2 1 1 1 1 |
159 9b92b5c3 | E1 1 1 1 | E2 1 1 1 1 |
160 9e9df008 | E1 1 1 1 | E2 1 1 1 1 |
161 9f387444 | E1 1 1 0 | E2 1 1 1 1 | E1 deformable convolution, attention mechanism
162 9f524473 | E1 1 0 0 | E2 1 1 1 1 | unnamed genomic prediction: E1 generic type + guessed family
163 9fb3a045 | E1 1 1 0 | E2 1 1 1 1 | E1 lists optimisation subroutines
164 a257f5e6 | E1 1 1 1 | E2 1 1 1 1 | applied vendor CNN reconstruction
165 a31d3b97 | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
166 a3fecb70 | E1 1 1 1 | E2 1 1 1 1 |
167 a4a24056 | E1 1 1 1 | E2 1 1 1 1 |
168 a5624154 | E1 1 1 1 | E2 1 1 1 1 | prompted LLMs
169 a71558b9 | E1 1 1 1 | E2 1 1 1 1 |
170 a7211c60 | E1 1 1 1 | E2 1 1 1 1 |
171 a99e8150 | E1 1 0 1 | E2 1 1 1 1 | fine-tuning, architecture unstated: E1 adds deep learning
172 aad377be | E1 1 1 0 | E2 1 1 1 1 | E1 HDOCK docking as type
173 addf5c2e | E1 1 1 1 | E2 1 1 1 1 |
174 b17a9271 | E1 1 0 0 | E2 1 1 1 1 | E1 LR (unstated) + WGCNA
175 b1ba20cc | E1 1 1 0 | E2 1 1 1 1 | E1 components as types
176 b1f3f9a9 | E1 1 1 1 | E2 1 1 0 0 | E2 drops the stated unsupervised clustering (family and type empty)
177 b21bff17 | E1 1 1 1 | E2 1 1 1 1 | Prophet
178 b54150b4 | E1 1 1 1 | E2 1 1 1 1 |
179 b54e06ef | E1 1 1 1 | E2 1 1 1 1 |
180 b58c33bc | E1 1 0 0 | E2 1 1 1 1 | E1 no ensemble, nomogram
181 b912adf8 | E1 1 0 0 | E2 1 1 1 1 | E1 Gaussian process from outside knowledge; E2 applied MLIP
182 ba7d4ad7 | E1 1 1 0 | E2 1 1 1 1 | E1 'radiomics' as type
183 bb60b5f8 | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
184 bbc276cb | E1 1 1 1 | E2 1 1 1 1 |
185 bbd7a91e | E1 1 1 0 | E2 1 1 1 1 | pretrained CNN/ViT compared with neurons: E1 'style transfer' as type
186 bc6519a7 | E1 1 0 1 | E2 1 1 1 0 | E2 keeps only XGBoost, drops the compared regression models; E1 no ensemble
187 bdff9866 | E1 1 1 1 | E2 1 1 1 1 |
188 bf0ab919 | E1 0 1 0 | E2 1 1 1 1 | E1 counts association logistic regression as supervised model
189 bf859805 | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
190 bfb9a496 | E1 1 1 1 | E2 1 1 1 1 |
191 c03b53bb | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
192 c0459914 | E1 1 0 1 | E2 1 1 1 1 | E1 no DR for factor analysis
193 c383bba2 | E1 1 1 1 | E2 1 1 1 1 |
194 c60f338e | E1 1 1 1 | E2 1 1 1 1 |
195 c71ac0e2 | E1 1 1 0 | E2 1 1 0 1 | E1 SHAP; E2 'physics-informed' for physics-derived input features only
196 c7233a56 | E1 1 1 1 | E2 1 1 1 1 | applied SpliceAI
197 c796d043 | E1 1 1 1 | E2 1 1 1 1 |
198 c8868a70 | E1 1 1 1 | E2 1 1 1 1 | MoE; E2 multimodal (good)
199 ca794c63 | E1 1 1 1 | E2 1 1 1 1 |
200 cba9fe3e | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
201 cc893d54 | E1 1 1 1 | E2 1 1 1 1 |
202 cd72be5c | E1 1 1 1 | E2 1 1 1 1 |
203 ceb894cf | E1 1 1 0 | E2 1 1 1 1 | E1 attention modules, Grad-CAM
204 d00d69b9 | E1 1 1 1 | E2 1 1 1 1 | SOM
205 d0f4b29d | E1 1 1 1 | E2 1 1 1 1 | applied CADe
206 d124258a | E1 1 1 0 | E2 1 1 1 0 | both list radiomics/nomogram as types
207 d37611bb | E1 1 1 1 | E2 1 1 1 1 |
208 d54aa10a | E1 1 1 1 | E2 1 1 1 0 | E2 'AlphaFold2' where abstract says only AlphaFold
209 d7415a2d | E1 1 1 1 | E2 1 1 1 1 |
210 d7cf024c | E1 1 1 0 | E2 1 1 1 1 | E1 association logistic regression
211 dabc0d60 | E1 1 1 0 | E2 1 0 1 0 | both read a logistic growth curve as logistic regression; E2 adds 'supervised'
212 db45e0ba | E1 1 1 1 | E2 1 1 1 1 | MaxEnt
213 dc6608e9 | E1 1 1 0 | E2 1 1 1 1 | unnamed architectures: E1 task + unstated CNN; E2 []
214 dce953d4 | E1 1 1 0 | E2 1 1 1 1 | E1 ODConv, CBAM, loss as types
215 dd23b32f | E1 1 1 0 | E2 1 1 1 1 | E1 'pseudo-labeling' as type
216 dd9e672d | E1 1 1 1 | E2 1 1 1 1 | PINN; E2 physics-informed family (good)
217 ddf5f17c | E1 1 0 0 | E2 1 1 1 1 | E1 conformal prediction as type, guessed family; E2 applied VEGA models
218 de4661ba | E1 1 1 0 | E2 1 1 1 1 | E1 radiomics, self-attention
219 de49823b | E1 1 1 1 | E2 1 1 1 1 |
220 dfb9e69a | E1 1 1 1 | E2 1 1 1 1 | RL agent
221 e0defec6 | E1 1 1 0 | E2 1 1 1 1 | E1 'neural network' not stated
222 e16a8123 | E1 1 1 1 | E2 1 1 1 1 |
223 e16eb2d7 | E1 1 1 1 | E2 0 0 0 0 | E2 empties a paper that clusters cancer cells into subtypes
224 e28df596 | E1 1 1 1 | E2 1 1 1 1 |
225 e2d15d70 | E1 1 1 0 | E2 1 1 1 1 | E1 ssGSEA as type
226 e39d3c8c | E1 1 1 0 | E2 1 1 1 1 | E1 WGCNA
227 e56776c0 | E1 1 1 0 | E2 1 1 1 1 | E1 nomogram
228 e577dd0a | E1 1 1 0 | E2 1 1 1 1 | E1 generic 'self-supervised machine learning' type; E2 self-supervised paradigm
229 e593b9f9 | E1 1 0 0 | E2 1 1 1 1 | unnamed AI search platforms: E1 assumes LLM
230 e5f568d0 | E1 1 1 0 | E2 1 1 1 1 | E1 FastMI, SHAP as types
231 e753bb28 | E1 1 1 1 | E2 1 1 1 1 |
232 e83369c6 | E1 1 1 1 | E2 1 1 1 1 | E2 self-supervised + physics-informed (good)
233 e8934d9d | E1 1 0 1 | E2 1 1 1 1 | E1 no ensemble
234 ea73be63 | E1 1 1 1 | E2 1 1 0 1 | E2 drops 'natural language processing' for LDA topic modelling of literature
235 eb1e7867 | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
236 eb25c464 | E1 1 1 1 | E2 1 1 1 1 |
237 ef7f5133 | E1 1 1 0 | E2 1 1 1 1 | E1 temperature scaling as type
238 f0b041e5 | E1 1 1 1 | E2 1 1 1 1 |
239 f2013dd7 | E1 1 1 1 | E2 1 1 1 1 |
240 f262f6e3 | E1 1 1 0 | E2 1 1 1 0 | E1 hard negative mining, attention; E2 'contrastive learning' (technique) as type
241 f4835625 | E1 1 1 0 | E2 1 1 1 1 | E1 WGCNA; E2 applied CIBERSORT
242 f652d04e | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
243 f72811ef | E1 1 1 1 | E2 1 1 1 1 | LLM agentic system
244 f91ae58c | E1 1 1 0 | E2 1 1 1 1 | E1 VMD, tuning optimisers, SHAP as types
245 f9e4ab4c | E1 1 0 1 | E2 1 1 1 1 | unnamed: E1 guessed classical
246 fa6a9a3f | E1 1 1 1 | E2 1 1 1 0 | E2 generic 'regression model'
247 fb43bfa5 | E1 1 1 1 | E2 1 1 0 0 | E2 drops stated unsupervised clustering (family and type empty)
248 fc31927b | E1 1 1 1 | E2 1 1 1 1 |
249 fdf2e20e | E1 1 1 0 | E2 1 1 1 0 | both generic 'regression analysis'
```
