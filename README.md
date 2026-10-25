# GLM-5.3-Flash enrichment test

Does Z.ai's GLM-5.3-Flash enrich DOME Observatory records as well as DeepSeek V4.1-Flash?
This repository runs the observatory's validated enrichment (prompt `e1`, vocab sha256 `41db952f…`) with only the model changed. The prompt, vocabularies, parser and event format are byte-identical copies, in [`vendor/`](vendor/).
The production pipeline is [`dome-ml-observatory-triage`](https://github.com/BioComputingUP/dome-ml-observatory-triage). Nothing here writes to its database or loads anything into it.

## Cohorts

| Cohort | Records | What it answers |
|---|---:|---|
| `wave1` | 250 | Pilot: un-enriched positives, spread over year band × preprint/article, ≤2 per venue |
| `wave2` | 250 | The same draw's second half, run after the pilot is rated |
| `enriched100` | 100 | Positives DeepSeek V4.1 already enriched, spread over EDAM tier 1: how closely GLM matches |

## Steps

```bash
cp .env.example .env && chmod 600 .env        # then paste the Z.ai key into .env (see below)
python3 scripts/check_no_secrets.py --install # pre-commit hook: this repository is public
python3 scripts/check_vendor.py               # the vendored e1 copies are intact
python3 -m pytest tests

python3 scripts/export_cohorts.py             # read-only, needs the VPN to moros; done once
python3 scripts/probe_zai.py --confirm        # one tiny call: request shape and usage fields
python3 scripts/run_enrichment.py --cohort wave1 --limit 25 --confirm   # smoke run
python3 scripts/run_enrichment.py --cohort wave1 --confirm
python3 scripts/run_enrichment.py --cohort enriched100 --confirm
python3 scripts/compare_to_deepseek.py --examples 5

python3 viewer/serve.py                       # http://127.0.0.1:8765 -- rate each tag group
python3 scripts/summarise_ratings.py
```

Without `--confirm`, `run_enrichment.py` only prints what it would do and what it would cost. It refuses any run projected above `--max-usd` (default $3).
A run resumes if re-run, skipping records already done, and records each run's settings in `runs/<batch_id>.manifest.json`.
Add the billed figure from the Z.ai billing page to `runs/spend_log.csv`.

## What changes from production, and why

- **Model.** `glm-5.3-flash` at `https://api.z.ai/api/paas/v4`, the pay-as-you-go API, not the Coding Plan.
- **Thinking.** It is always on for GLM-5.3. `reasoning_effort` is `high`, which matches DeepSeek's default for the validated runs; Z.ai's default would be `max`.
- **Token counts.** Z.ai's `prompt_tokens_details.cached_tokens` is copied to DeepSeek's `prompt_cache_hit_tokens`, so the events record the cache share. Z.ai does not document a reasoning-token count; if it sends none, `reasoning_tokens` is 0.
- **Timeout.** The request timeout is 300 s, not 60 s.
- **Event label.** Events carry `model_tier = glm-5.3-flash`, so they can never be mistaken for DeepSeek's.

Everything else (temperature 0, JSON mode, the 16,000-token cap, the input read with `pd.read_csv(dtype=str)`, and resumption) is the production code path.

## Layout

```
vendor/        byte-identical e1 code, vocabularies and rendered prompt + MANIFEST.sha256
glm_enrich/    Z.ai client, fidelity check, cohort selection, review data
scripts/       export, probe, run, compare, summarise, secret check
viewer/        local review page (stdlib server, localhost only)
cohorts/       committed: which records, in which stratum and wave
runs/          committed: events (tags + rationale), run manifests, spend log
ratings/       committed: rubric log, append-only
reports/       committed: agreement and rating summaries
data/          NOT committed: input CSVs with titles and abstracts, the DeepSeek reference snapshot
```

## Security

The Z.ai key lives only in `.env`, which is gitignored. The moros address lives only in the triage repository's own gitignored `moros_pipeline/.env`.
`scripts/check_no_secrets.py` runs before every commit. It refuses API-key shapes, database URIs, private addresses, home paths, and anything under `data/`.
Setup notes for the Z.ai account and key are in `SETUP_ZAI.local.md`, which is gitignored. Create it from your own notes if you clone this elsewhere.
