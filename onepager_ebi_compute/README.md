# One-pager: EMBL-EBI LLM compute request

- `onepager.md`: the text, ready to paste into a Google Doc
- `pipeline_figure.png` / `.svg`: the pipeline figure
- `make_pipeline_figure.py`: draws the figure. Matplotlib only. The output is byte-identical every run.

```bash
python3 onepager_ebi_compute/make_pipeline_figure.py
```

## Where the numbers come from
`T` = dome-ml-observatory-triage, `R` = dome-triage, `O` = dome-ml-observatory.

| Number | Source |
|---|---|
| 876k screened, 367k positive | `T/COST_DASHBOARD.md:10-11` |
| 91% (95% CI 89–93%) before review, 99% (95% CI 98.2–99.5%) after review, on 1,000 held-out papers (Wilson intervals) | `R/analysis/paper_figures/04_llm_second_curator/output/table_llm_benchmark_paper_table.md` |
| 82 of 97 disagreements resolved to the model | `R/.../04_llm_second_curator/output/table_heldout_review_outcomes.md` |
| ~6,400 expert-labelled papers (3,209 yes / 3,213 no) | `R/analysis/paper_figures/NOTES_for_paper.md:22-23` |
| Classify tokens: 8,667 in / 172 out | `T/pricing/token_profiles.yaml` |
| Enrich tokens, DeepSeek V4.1-Flash reference: 3,148 in / 1,481 out (1,336 reasoning) | `T/COST_DASHBOARD.md:45` |
| Enrich tokens, GLM-5.3-Flash experimental: 3,116 in / 346 out, 230–300 papers/min at concurrency 50 | `runs/spend_log.csv` (this repo, 350 GLM papers) |
| GLM vs DeepSeek agreement on 100 papers: 89% (95% CI 81–94%) learning type, 74% (65–82%) top field; Wilson intervals computed here | `reports/agreement_glm53flash_vs_deepseek.md` |
| 4 journals, 3,532 papers enriched | `O/observatory-ui/.../about-processing/processing-rounds.ts` |
| Journal coverage: top 829 journals = 268,863 papers; top 2,488 = 309,063; 8,294 journals with a positive | `R/.../07_journal_insights/output/table_journals_all.csv` |
| DeepSeek parallel requests: classify 400; enrich 800 → 418 papers/min, 40 → 53/min | `T/README.md:139,222-223`, `T/pricing/token_profiles.yaml:41` |
| Tokens per scenario | papers × 4,629 (DeepSeek reference) and papers × 3,462 (GLM test) |
