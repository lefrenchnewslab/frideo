# Second-rater study — D7 plain/qualified distancing

Independent inter-annotator check on the D7 adjudication codebook, 2026-08-04.
Reported in the paper's D7 section.

## Result

```
                             n     vs author gold        vs D7
ALL                        100   κ=0.940 (97.0%)   κ=0.718 (86.0%)
boundary (adjudicated)      70   κ=0.943 (97.1%)   κ=0.630 (81.4%)
  of which CONTESTED        13   κ=0.755 (92.3%)   κ=-0.345 (7.7%)
control (D7=LLM agreed)     30   κ=0.932 (96.7%)   κ=0.932 (96.7%)
left terms                  42   κ=0.905 (95.2%)   κ=0.667 (83.3%)
right terms                 58   κ=0.965 (98.3%)   κ=0.756 (87.9%)

tie-break on the 13 contested rows (author gold != D7):
  rater sided with the author 12/13, with D7 1/13
```

Reproduce with `python3 score_second_rater.py` (standard library only).

**Report the strata separately.** The sample deliberately over-weights boundary
cases (70/100) relative to their share of the gold (118/430), so the pooled
figure is not representative of the gold as a whole.

## Files

| File | What it is |
|---|---|
| `CODEBOOK.md` | The rule, six signals. The **only** instructions the annotator received. Identical (byte for byte) to the codebook the author adjudicated from — that is what makes this a test of the codebook rather than of one person's memory of it. |
| `second_rater_sheet_TEMPLATE.csv` | The sheet **as issued**: `item_id`, `term`, `sentence`, `pre_context`, and two empty columns. No outlet, no D7 label, no LLM label, no author gold, no term side. This is the blinding, inspectable. |
| `second_rater_sheet_BLIND.csv` | The same sheet **as returned**, 100/100 labelled, no UNCERTAIN. Read by the scorer. |
| `second_rater_KEY.csv` | Held back from the annotator: `record_id`, `side`, `stratum`, `d7_label`, `author_gold`. Joins the returned sheet to the gold. |
| `ANNOTATOR.md` | Provenance — recruitment, qualification, independence, materials, blinding, date, completion. |
| `score_second_rater.py` | Computes the table above from the sheet + key. |

## Relationship to the gold

Items are drawn from `../../results/exp_a/exp_a_gold_430.csv`, joined on
`record_id` + `term`. Every one of the 100 sheet sentences matches its gold row
exactly, and the visible text reproduces the stored `d7_label` on 100/100 rows —
so the labels are scored against the text the annotator actually saw.

Stratification is over `stratum`: `boundary` = rows the author adjudicated
(where D7 and the LLM judge disagreed), `control` = rows where D7 and the LLM
already agreed and the gold is theirs by construction.
