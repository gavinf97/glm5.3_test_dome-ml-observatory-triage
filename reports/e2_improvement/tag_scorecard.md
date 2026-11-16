# Modelling-tag scorecard

Automatic checks from the correctness review, per run. Higher is better for the first three rows, lower is better for the next two. Two paradigms and vocabulary misses are context, not scores.

e2 is the EXPERIMENTAL local prompt (experimental/e2/PROVENANCE.md). "Model only" is what GLM itself returned; "with backfill" adds the logged family backfill.

## DeepSeek V4.1 (e1), enriched100 (100 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 17/22 (77%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 3/3 (100%) |
| Plain neural network/MLP that gets a neural family | 12/12 (100%) |
| Model types listed but family left empty | 1 |
| Records with a non-model item in model_type | 9 |
| Records with two paradigms | 12 |
| Records with a tag outside the vocabulary or over a cap | 0 |

## GLM e1, enriched100 (100 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 2/20 (10%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 1/2 (50%) |
| Plain neural network/MLP that gets a neural family | 9/10 (90%) |
| Model types listed but family left empty | 5 |
| Records with a non-model item in model_type | 21 |
| Records with two paradigms | 5 |
| Records with a tag outside the vocabulary or over a cap | 4 |

## GLM e2, enriched100 (model only) (100 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 20/20 (100%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 2/2 (100%) |
| Plain neural network/MLP that gets a neural family | 7/7 (100%) |
| Model types listed but family left empty | 2 |
| Records with a non-model item in model_type | 1 |
| Records with two paradigms | 9 |
| Records with a tag outside the vocabulary or over a cap | 1 |

## GLM e2, enriched100 (with backfill) (100 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 20/20 (100%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 2/2 (100%) |
| Plain neural network/MLP that gets a neural family | 7/7 (100%) |
| Model types listed but family left empty | 2 |
| Records with a non-model item in model_type | 1 |
| Records with two paradigms | 9 |
| Records with a tag outside the vocabulary or over a cap | 1 |

## GLM e2, enriched100, effort max (model only) (99 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 20/20 (100%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 2/2 (100%) |
| Plain neural network/MLP that gets a neural family | 7/7 (100%) |
| Model types listed but family left empty | 2 |
| Records with a non-model item in model_type | 1 |
| Records with two paradigms | 11 |
| Records with a tag outside the vocabulary or over a cap | 1 |

## GLM e2, enriched100, effort max (with backfill) (99 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 20/20 (100%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 2/2 (100%) |
| Plain neural network/MLP that gets a neural family | 7/7 (100%) |
| Model types listed but family left empty | 2 |
| Records with a non-model item in model_type | 1 |
| Records with two paradigms | 11 |
| Records with a tag outside the vocabulary or over a cap | 1 |

## GLM e1, wave1 (250 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 15/51 (29%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 4/9 (44%) |
| Plain neural network/MLP that gets a neural family | 28/30 (93%) |
| Model types listed but family left empty | 3 |
| Records with a non-model item in model_type | 20 |
| Records with two paradigms | 15 |
| Records with a tag outside the vocabulary or over a cap | 12 |

## GLM e2, wave1 (model only) (250 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 51/51 (100%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 7/7 (100%) |
| Plain neural network/MLP that gets a neural family | 24/24 (100%) |
| Model types listed but family left empty | 7 |
| Records with a non-model item in model_type | 2 |
| Records with two paradigms | 19 |
| Records with a tag outside the vocabulary or over a cap | 4 |

## GLM e2, wave1 (with backfill) (250 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 51/51 (100%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 7/7 (100%) |
| Plain neural network/MLP that gets a neural family | 24/24 (100%) |
| Model types listed but family left empty | 7 |
| Records with a non-model item in model_type | 2 |
| Records with two paradigms | 19 |
| Records with a tag outside the vocabulary or over a cap | 4 |

## GLM e1, heldout250 (250 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 8/29 (28%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 6/10 (60%) |
| Plain neural network/MLP that gets a neural family | 28/28 (100%) |
| Model types listed but family left empty | 6 |
| Records with a non-model item in model_type | 36 |
| Records with two paradigms | 15 |
| Records with a tag outside the vocabulary or over a cap | 14 |

## GLM e2, heldout250 (model only) (250 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 29/29 (100%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 9/9 (100%) |
| Plain neural network/MLP that gets a neural family | 13/13 (100%) |
| Model types listed but family left empty | 7 |
| Records with a non-model item in model_type | 3 |
| Records with two paradigms | 26 |
| Records with a tag outside the vocabulary or over a cap | 3 |

## GLM e2, heldout250 (with backfill) (250 records)

| Check | Result |
|---|---:|
| Tree ensembles that also get 'ensemble learning' | 29/29 (100%) |
| PCA/UMAP/t-SNE that also get 'dimensionality reduction' | 9/9 (100%) |
| Plain neural network/MLP that gets a neural family | 13/13 (100%) |
| Model types listed but family left empty | 7 |
| Records with a non-model item in model_type | 3 |
| Records with two paradigms | 26 |
| Records with a tag outside the vocabulary or over a cap | 3 |
