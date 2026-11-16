# Validation: is GLM-5.3-Flash with prompt e2 good enough for production?

One human rater and one LLM judge (Claude Opus 5.5) rate the same papers with the same rubric. We measure how far they agree, settle the disagreements into a consensus, and test the consensus against a bar set in advance.

**Nothing here uses the Anthropic API.** The judge runs through the Claude Code CLI (`claude -p`) on a normal subscription, with `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` removed from its environment. The only paid API in this folder's workflow is Z.ai, for the GLM tagging run (about $0.15).

## Design (pre-registered in `config.json`)

| | |
|---|---|
| Test set | `wave2`: 250 confirmed AI/ML positives never run through any model or seen by a reviewer |
| What is tested | GLM-5.3-Flash, prompt e2 as frozen (sha256 `c3196ff7…`), reasoning effort high |
| Raters | Human: a stratified random 150 of the 250. Opus 5.5 judge: all 250 |
| Rating units | domain (EDAM tiers 1–3), learning_paradigm, model_family, model_type, model_use |
| Verdicts | correct / minor / major / unsure; **acceptable = correct or minor** |
| Blinding | Neither rater sees GLM's rationale or the other rater's verdicts |
| Consensus | Human verdict where the raters agree on acceptable/not; otherwise the adjudicated verdict |
| Accuracy test | Per primary unit: one-sided exact binomial, H0 acceptable ≤ 80%, Holm-adjusted over the 4 primary units, α = 0.05; target 90% |
| Reliability gate | Gwet's AC1 ≥ 0.70 per primary unit (Cohen's kappa, weighted kappa, PABAK, specific agreement and McNemar reported alongside) |
| **GO** | All four primary units pass both the accuracy test and the reliability gate |

**Why 150 papers?** At a true acceptable rate of 90%, the 95% Wilson CI is 84–94%. The power to reject "≤ 80%" is 0.96 unadjusted and 0.83 at the strictest Holm step. With 100 papers the power at that step would be only 0.58.

**Why AC1 and not kappa as the gate?** When about 90% of tags are acceptable, kappa is pulled down by prevalence. In simulation, two raters who are each 95% accurate get a kappa of about 0.60 (95% range 0.39–0.77 at n=150). AC1 does not have this problem. Kappa is still reported.

## Files

| File | What it is |
|---|---|
| `config.json` | Frozen settings. Commit before rating starts and do not edit afterwards |
| `RUBRIC.md` | The rubric. The judge reads its RATER INSTRUCTIONS section word for word |
| `make_sample.py` | Draws `sample.csv` once (seeded, stratified); refuses to overwrite |
| `rate_app.py`, `rate.html` | Local rating app (127.0.0.1), plus adjudication mode |
| `judge_opus.py` | Opus 5.5 second rater via the Claude Code CLI; resumable |
| `analyse.py`, `agreement_stats.py` | Statistics, CSV tables, figures, dashboard |
| `ratings/<rater>.csv` | Append-only ratings; the latest row per paper and unit counts |
| `results/` | Everything `analyse.py` writes, plus judge run manifests |

## Run order

```bash
# 1. Pre-register: commit config.json and RUBRIC.md before any rating
git add validation/config.json validation/RUBRIC.md && git commit -m "Pre-register tag validation"

# 2. Tag wave2 with GLM-5.3-Flash, prompt e2 (Z.ai, ~$0.15; add the billed figure to runs/spend_log.csv)
python3 scripts/run_enrichment.py --cohort wave2 --prompt e2 --confirm

# 3. Draw the sample once, and commit it
python3 validation/make_sample.py
git add validation/sample.csv && git commit -m "Validation sample"

# 4. Human rating: 150 papers, about 1-2 min each, can stop and resume any time
python3 validation/rate_app.py --rater gf          # open http://127.0.0.1:8766

# 5. Opus 5.5 judge on your Claude subscription (about 25 s per paper; ~2 h for 250)
python3 validation/judge_opus.py                   # dry run: shows what it would do
python3 validation/judge_opus.py --limit 5 --confirm
python3 validation/judge_opus.py --confirm         # re-run to resume after a usage-limit stop

# 6. First analysis: agreement, and the list of disagreements
python3 validation/analyse.py

# 7. Adjudicate the disagreements (saved as rater "consensus")
python3 validation/rate_app.py --adjudicate --rater gf

# 8. Final analysis, then commit the ratings and results
python3 validation/analyse.py
git add validation/ratings validation/results && git commit -m "Validation results"
```

Steps 4 and 5 can run in parallel; the judge never reads the human's ratings. Open `results/report.html` for the dashboard: progress, the go/no-go box, tables, figures and limitations. Every number is also in the CSVs beside it.

## Outputs (`results/`)

| File | Contents |
|---|---|
| `accuracy.csv` | Per view (human, judge on the 150, consensus, judge on all 250) × unit: counts, % correct, % acceptable, Wilson CI, exact p, Holm p, pass. Also a paper-level "all 4 primary units acceptable" row |
| `agreement.csv` | Per unit: pairs, % agreement, AC1, kappa, weighted kappa (3 levels), with bootstrap CIs; PABAK, positive/negative agreement, McNemar p, gate |
| `confusion.csv` | Human × judge verdict counts per unit |
| `error_codes.csv` | Error-code counts per rater view and unit |
| `by_stratum.csv` | Acceptable rate by year band × article/preprint |
| `ratings_long.csv` | Every latest rating, one row per rater × paper × unit |
| `to_adjudicate.csv` | Disagreements still open |
| `fig_accuracy`, `fig_reliability`, `fig_confusion`, `fig_errors` | `.png` and `.svg` |
| `report.html`, `report.md`, `summary.json` | Dashboard, the same numbers as Markdown, and the decision as JSON |

## Dry run without touching wave2

Point a copy of `config.json` at heldout250, with all outputs in a scratch folder:

```bash
python3 - <<'EOF'
import json; c = json.load(open("validation/config.json"))
c.update(cohort="heldout250", input="data/input_heldout_250.csv", events="runs/e2/events_heldout250.csv",
         sample_path="/tmp/dry/sample.csv", ratings_dir="/tmp/dry/ratings", results_dir="/tmp/dry/results")
json.dump(c, open("/tmp/dry_config.json", "w"), indent=2)
EOF
python3 validation/make_sample.py --config /tmp/dry_config.json
python3 validation/rate_app.py --rater gf --config /tmp/dry_config.json
```

Every script takes `--config`.

## Limitations (also stated in the report)

- One human rater, who also adjudicates. If time allows, a second human rates a random 30 of the 150.
- Judgements use the title and abstract only, which is all GLM sees.
- The judge is a different model family from the tagger, but an earlier Claude review shaped e2. The human ratings are the anchor.
- Results apply to un-enriched positives like wave2.

## After the decision

- **GO:** port e2 into `dome-ml-observatory-triage` as a real prompt version. That means the vocabulary files, the renderer, parser steps E2-PP1–3, the `model_use` column, and a prompt hash in `prompts/PROMPT_HASHES.json`. Add Z.ai as a model tier. Then run on the official triage set and ingest into `dome-ml-observatory`.
- **NO-GO:** use `error_codes.csv` and the adjudicated majors to write e3, tune it on heldout250 only, and validate it on a new untouched draw. wave2 is then used up.
