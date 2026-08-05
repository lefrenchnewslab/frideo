# FrIdéo — replication

Pipeline, evidence inputs and validation runs behind the scores in the parent
directory.

```bash
pip install -r requirements.txt
make check     # verify the paper's headline numbers against the shipped outputs
make scores    # rebuild results/scores_v2.csv from the evidence inputs
make all       # scores + every sensitivity and validation run
make clean     # delete regenerated outputs (shipped inputs untouched)
```

`make check` asserts 29 paper numbers against the shipped files. `make all`
regenerates every CSV, JSON and Markdown output byte-identical, and `make check`
still passes after it. Plot bytes are not reproducible across matplotlib builds;
the numbers they render are.

Bootstrap seed 42. Requires `numpy`, `matplotlib`, `scikit-learn`, pinned in
`requirements.txt` to the versions the shipped results were verified with; otherwise
standard library. No network, database, API key or LaTeX.

## Layout

```
analysis_v2.py   fuse families, shrink toward the prior, bootstrap, LOO, label
data/, gn/       evidence inputs
d7/              D7 term lists, LLM-validation prompts, adjudication codebook,
                 gold-standard provenance (adjudication/) and second-rater study
                 (second_rater/)
results/         shipped inputs, generated outputs, plots
scripts/         one entry point per analysis, plus pipeline_check.py for `make check`
Makefile         the dependency graph behind the commands above
```

## D7 reference material

Cited by the paper, not touched by the four commands above.

| Path | What it is |
|---|---|
| `d7/d7_score.py` | Reference implementation of the symmetric plain/qualified scorer — the six distancing signals, the article-level majority vote, and per-outlet aggregation. Runs on any JSONL corpus with `outlet_json_name`, `headline` and `article_body_clean` fields; the corpus behind the shipped scores is third-party copyrighted and is not distributed |
| `d7/d7_terms.py` | Full left- and right-coded term lists, distancing prefixes and critique vocabulary |
| `d7/PROMPT_d7_distancing.md` | The exact LLM-validation prompts, and the written rule the adjudication applied |
| `d7/d7_endorsed_discrimination.csv` | Per-term endorsed firing rates and discrimination ratios across left/centre/right clusters (median 4.6×) |
| `d7/d7_rule_ablation_scores.csv` | Per-outlet D7-raw under each distancing variant — `bow`, `guillemets_only`, `guillemets_prefix`, `full_symmetric`. Backs the distancing-ablation panel of the paper's sensitivity table |
| `d7/d7_rule_ablation_summary.csv` | The same ablation collapsed to one row per variant: ρ vs the full model, coverage, largest absolute shift |
| `d7/probe_metrics.json` | CamemBERT probe metrics and the per-term outlet–PC1 correlations (max \|ρ\| = 0.36) |
| `d7/umap/umap_*.png` | UMAP embedding plots, one per term |
| `d7/CODEBOOK.md` | The written adjudication rule — the six signals, what is explicitly *not* a signal, worked examples. Sections 1–7 are what both raters worked from |
| `d7/adjudication/` | Provenance for the 430-row gold: the blind worksheets, the withheld keys, and the script that assembles and scores them. See its `README.md` |
| `d7/second_rater/` | Independent inter-annotator check: 100 blind items relabelled by a second rater, κ = 0.94 vs the author gold. `python3 score_second_rater.py` reproduces every figure in the paper's D7 section |

They live outside `results/` because `make clean` empties that directory.

## Evidence families

Nine direct families plus one structural prior. Values are z-scored per family
inside `analysis_v2.py`; an empty value means *not applicable*, not zero.

| Family | Evidence | Stored in |
|---|---|---|
| D0 | Ownership ideology | `data/outlets_evidence_v2.json` → `structural.S1_owner_category`, mapped by `OWNER_STRUCTURAL` |
| D1 | Broadcast guest ideological bias | `data/outlets_evidence_v2.json` → `direct.D1` |
| D2 | Survey perceived ideology | `data/outlets_evidence_v2.json` → `direct.D2` |
| D3 | Hyperlink / follower network position | `results/cointet_d3_continuous.csv`, with a categorical fallback in `direct.D3` |
| D4 | Media Bias/Fact Check rating | `data/outlets_evidence_v2.json` → `direct.D4` |
| D6a | Stated editorial orientation | `data/outlets_evidence_v2.json` → `direct.D6a` |
| D6b | Third-party encyclopedic profiling | `data/outlets_evidence_v2.json` → `direct.D6b` |
| D7 | Distancing-aware lexical score | `results/d5_score_d5_allcat_2024-2025_endorsed.csv` |
| D8 | Ad Fontes Media rating | `gn/gn_bias_ratings.json` |
| S2 | Founding-tradition prior | `data/outlets_evidence_v2.json` → `structural.S2_tradition` |

Naming: **`d5_` in filenames means D7**; **`direct.D5` is dead**, excluded from
`DIRECT_FAMILIES`; **`exp_a_gold_430.csv` holds 430 rows** — 527 drawn, 526
valid, 506 after stratified balancing, 505 distinct (one exact duplicate), 430
after removing occurrences whose term did not survive lexicon curation
(75 `émeutiers`), composed of 312 auto-gold + 118 author-adjudicated. See
`d7/adjudication/README.md` for the per-source breakdown.

## Shipped, not rebuilt

These `results/` files are inputs. Everything downstream of them is rebuilt by
`make all`.

| File | Source |
|---|---|
| `d5_score_d5_allcat_2024-2025_endorsed.csv`, `d5_score_d5_politique_pooled_all_current_endorsed.csv` | D7 scoring over full article text; the corpus is third-party copyrighted and not distributed |
| `d7_period_stability.csv`, `d7_period_stability_summary.json` | Same, split by calendar year |
| `jdd_bollore_trajectory.json` | Same, plus a pre-2023 window |
| `cointet_d3_continuous.csv` | Cointet et al. 2019 web-link crawl (HAL halshs-03299024) |
| `exp_a/exp_a_gold_430.csv`, `exp_a/exp_a_summary.json` | Human-adjudicated gold set; `make check` recomputes the κ values from it |

## Outputs

`make all` regenerates all of the following. `make check` reads them back.

| File | Produced by |
|---|---|
| `results/scores_v2.csv`, `results/bootstrap_stats.json` | `analysis_v2.py` |
| `results/family_sigma.json` | `scripts/estimate_sigma_empirical.py` |
| `results/loo_absolute_shifts.csv` | `scripts/loo_absolute_shifts.py` |
| `results/mbfc_validation.json` | `scripts/validate_mbfc.py` |
| `results/mbfc_independent_validation.json` | `scripts/validate_mbfc_independent.py` |
| `results/d4_ablation.json` | `scripts/ablate_mbfc.py` |
| `results/known_groups_validation.json` | `scripts/known_groups_validation.py` |
| `results/covariance_sensitivity.csv` | `scripts/covariance_sensitivity.py` |
| `results/lambda_sensitivity.{csv,json}` | `scripts/lambda_sensitivity.py` |
| `results/cross_family_corr.csv`, `results/cross_family_pca.json` | `scripts/cross_family_convergence.py` |
| `results/unidimensional_validation_report.md`, `results/plots/pca_{scree,biplot}.png` | `scripts/unidimensional_validation.py` |
| `results/kde_bandwidth_sensitivity.{csv,json}` | `scripts/kde_bandwidth_sensitivity.py` |
| `results/family_contribution_shares.csv`, `results/family_shares_long.csv`, `results/plots/family_*.png` | `scripts/compute_family_shares.py` |
| `results/d7_period_vs_fullmodel.csv` | `scripts/d7_period_vs_fullmodel_stability.py` |
| `results/no_prior_refit.json` | `scripts/no_prior_refit.py` |
| `results/plots/ideology_scores_v2.{png,pdf}`, `evidence_coverage_v2.png`, `kde_label_distribution.png` | `analysis_v2.py` |
