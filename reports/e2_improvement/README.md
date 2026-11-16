# EXPERIMENTAL prompt e2 for GLM-5.3-Flash: results

**Status:** e2 is an experiment that exists only in this repository. It is not part of the production prompts or vocabulary in dome-ml-observatory-triage, and nothing from it is written to moros. e1 in `vendor/` is unchanged and is still the validated prompt (sha256 `41db952f…`). Every change e2 makes, and where it comes from, is listed in [`experimental/e2/PROVENANCE.md`](../../experimental/e2/PROVENANCE.md). The frozen e2 prompt has sha256 `c3196ff7…`.

## Bottom line

On 250 held-out papers that e2 was never tuned on, e2 makes GLM-5.3-Flash much better on the modelling fields:

| Field | GLM with e1 | GLM with e2 |
|---|---:|---:|
| Learning paradigm acceptable | 96% | 98% |
| Model family acceptable | 80% | **96%** |
| Model type acceptable | 62% | **90%** |
| All three right on the same paper | 48% | **87%** |
| model_use acceptable (new field) | | 99% |

The figures come from a hand review of every paper ([heldout250_correctness_review.md](heldout250_correctness_review.md)); read that file's limitations first. For reference, the first review put DeepSeek V4.1 at about 87% for family and 85% for type, on a different set of papers (enriched100).

The improvement comes from the prompt itself. The logged post-processing (adding missing families) had nothing to add in any run: in the [scorecard](tag_scorecard.md), "model only" and "with backfill" are identical.

## Automatic checks across all runs

[tag_scorecard.md](tag_scorecard.md) has the full figures. The summary:

| Check | DeepSeek, enriched100 | GLM e1, enriched100 | GLM e2, enriched100 | GLM e1, wave1 | GLM e2, wave1 | GLM e1, heldout250 | GLM e2, heldout250 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tree ensembles that also get `ensemble learning` | 77% | 10% | 100% | 29% | 100% | 28% | 100% |
| PCA and similar that also get `dimensionality reduction` | 3/3 | 1/2 | 2/2 | 4/9 | 7/7 | 6/10 | 9/9 |
| Papers with a non-model item in model_type | 9 | 21 | 1 | 20 | 2 | 36 | 3 |
| Papers with a tag outside the vocabulary or over a cap | 0 | 4 | 1 | 12 | 4 | 14 | 3 |

## Agreement with DeepSeek (enriched100)

See [agreement_e2_vs_deepseek.md](agreement_e2_vs_deepseek.md). Compared with GLM e1:
- model-type agreement rose from 38% to 52%;
- paradigm agreement went from 89% to 85%;
- family agreement went from 58% to 56%.

Family agreement did not improve because e2 now does two things DeepSeek doesn't. It always adds `ensemble learning` (DeepSeek does in 77% of cases), and it stops guessing a family for unnamed methods (DeepSeek guesses). Agreement with DeepSeek therefore no longer tracks correctness for this field.

## Maximum reasoning effort is not worth it

e2 at `reasoning_effort max` on enriched100 gave the same scorecard as at `high`. It used about 6× more reasoning tokens (293,680 against 34,110), took longer, and one paper was cut off at the 16,000-token limit. Details: [agreement_e2_effort_max_vs_deepseek.md](agreement_e2_effort_max_vs_deepseek.md).

## Cost

List prices; the billed figures still need entering from the Z.ai billing page into `runs/spend_log.csv`.

| Run | Papers | List USD | Input tokens per paper | Output tokens per paper |
|---|---:|---:|---:|---:|
| e2, enriched100 | 100 | 0.093 | 5,627 | 501 |
| e2, wave1 | 250 | 0.151 | 5,588 | 425 |
| e1, heldout250 | 250 | 0.117 | 3,154 | 361 |
| e2, heldout250 | 250 | 0.140 | 5,637 | 464 |
| e2, enriched100, max effort | 100 | 0.224 | 5,627 | 3,111 |
| **Total for this experiment** | | **0.725** | | |

The e2 prompt is about twice as long as e1, but most of it is served from the prompt cache (67–77% on the larger runs). Per paper, e2 cost about 20% more than e1 on heldout250: $0.00056 against $0.00047.

## Where e2 still fails, and next steps

The full list is in the held-out review. In summary:
- e2 sometimes over-applies its exclusions. It drops stated clustering, trained baselines, latent profile analysis, and protein-language-model embeddings.
- The family cap of 3 can squeeze out `natural language processing`.
- A few generic phrases remain in model_type.

These suggest four more prompt rules (an e3), listed in the review. None of them has been built.

## Files

| | |
|---|---|
| `experimental/e2/` | e2 vocabularies, rendered prompt, PROVENANCE.md, MANIFEST.sha256, build and freeze scripts |
| `glm_enrich/e2.py` | e2 prompt renderer, parser wrapper (with logged post-processing) and run loop |
| `runs/e2/` | e2 event logs |
| `runs/events_heldout250.csv` | e1 events for the held-out cohort |
| `cohorts/heldout_manifest.csv`, `cohorts/heldout_summary.json` | which papers are in heldout250, and how they were drawn |
| `scripts/export_heldout.py`, `scripts/score_tags.py` | held-out draw and scorecard |
