# FrIdéo — data dictionary

`frideo_scores.csv` and `frideo_scores.json` carry identical rows. Use the CSV
for spreadsheets and R/pandas; use the JSON if you also want the scale metadata
(bounds, direction, cutoffs, family list) alongside the values.

**30 outlets**, sorted left to right by `score`.

## Columns

| Column | Type | Meaning |
|---|---|---|
| `outlet` | string | Outlet name as used in the paper |
| `score` | float | Latent ideology score. Negative = left, positive = right |
| `sigma` | float | Analytic standard error of `score` |
| `ci_low_95`, `ci_high_95` | float | 95% **analytic** confidence interval, `score ± 1.96 × sigma`. This is the interval the paper reports. It is *not* the bootstrap interval — see the note below |
| `ci_spans_zero` | bool | True if the CI includes 0 (15 of 30 outlets) |
| `label` | string | Seven-band label, for interpretability only |
| `n_direct_families` | int | Direct evidence families available for this outlet (max 9) |
| `sparse` | bool | True when `n_direct_families` ≤ 4 (5 outlets) |
| `structural_prior_z` | float | S2 founding-tradition prior the score is shrunk toward |
| `bootstrap_mean`, `bootstrap_std` | float | Bootstrap distribution of `score`, seed 42 |

**Two different uncertainties, don't mix them up.** `sigma` and the `ci_*`
columns are *analytic*: they propagate the per-family source-consistency
parameters σₖ plus a sparsity penalty, and they answer "how much evidence stands
behind this outlet's position". `bootstrap_std` is a *stability* quantity: it is
the spread of the score under 10 000 joint perturbations of σₖ and λ, and it
answers "how much does the score move if we had chosen the tuning constants
differently". The bootstrap spread is much narrower — for L'Humanité the
analytic CI is [−3.06, −1.76] while the bootstrap SD is 0.05. Report the
analytic CI when you quote a score; use `bootstrap_std` only when you are
discussing robustness to modelling choices. The full bootstrap interval is in
`replication/results/scores_v2.csv` as `bootstrap_ci_low` / `bootstrap_ci_high`.
| `D0_z` … `D8_z` | float or empty | Per-family z-scores. **Empty means not applicable, not zero** |

## Reading the scale

1. **It is panel-relative.** The scale is zero-mean, unit-variance *by
   construction* across these 30 outlets. A score of `+1.0` means "one SD right
   of the centre of the French national news ecosystem", not an absolute
   position. Do not compare to scores from a different outlet set without
   re-standardising.

2. **`label` is not the measurement.** The seven bands exist to make tables
   readable. All analysis in the paper uses the continuous `score`. Outlets near
   a cutoff can change band under small perturbations.

3. **Sparse outlets are shrunk.** The 5 outlets with ≤ 4 direct families
   have roughly a third of their score coming from the structural prior
   (α = 0.67 at n = 4). Their labels are indicative. `sparse` flags them.

`ci_spans_zero` is true for 15 outlets, all near the centre — treat the
centre of the distribution as an ordering, not as resolved differences.

## Families

| ID | Evidence |
|---|---|
| `D0` | Ownership ideology |
| `D1` | Broadcast guest ideological bias |
| `D2` | Survey perceived ideology |
| `D3` | Hyperlink/follower network position |
| `D4` | Media Bias Fact Check rating |
| `D6a` | Stated editorial orientation |
| `D6b` | Third-party encyclopedic profiling |
| `D7` | Distancing-aware lexical score |
| `D8` | Ad Fontes Media bias rating |

The structural prior S2 (founding tradition) is not a direct family; it is the
target of the empirical-Bayes shrinkage. Full per-family construction is in the
paper, §4 and Appendix A.

## Citation

```bibtex
@inproceedings{sobhy2026frideo,
  title     = {{FrIdéo}: French News Outlet Ideology Scoring via Multi-Source
               Evidence Fusion and Distancing-Aware Lexical Scoring},
  author    = {Sobhy, Amr},
  booktitle = {Proceedings of ICNLSP 2026},
  year      = {2026}
}
```

Resource version 1.0. Both files are derived from
`replication/results/scores_v2.csv`, which `replication/` rebuilds via
`make scores`.
