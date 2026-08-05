# D7 gold standard — how the 430 occurrences were composed

Provenance for `../../results/exp_a/exp_a_gold_430.csv`, the 430-occurrence
PLAIN/QUALIFIED gold standard the paper's D7 validation rests on.

## How the set was drawn

A stratified sample of 527 term occurrences was drawn from the 2023-H2 and
2024-H1 *politique* corpus, stratified by term side, D7 decision and outlet
ideology band, with outlet identity masked. Occurrences whose term did not
survive lexicon curation are excluded: `émeutiers` ('rioters') was rejected for
event saturation — it mass-fires on factual coverage of the May 2024
Nouvelle-Calédonie unrest — so its 75 occurrences are not in the gold set.

```
527 drawn
526 valid
506 after stratified balancing
505 distinct                  (one exact duplicate removed)
430 after dropping 75 émeutiers occurrences
    = 312 auto-gold (D7 and the LLM agree) + 118 author-adjudicated
```

## Files

| File | Rows | What |
|---|---|---|
| `adjudication_sheet_BLIND.csv` | 73 | Round-1 worksheet: D7/LLM disagreements requiring a human decision. Outlet-masked; `your_label_PLAIN_or_QUALIFIED` filled by the adjudicator. |
| `adjudication_KEY.csv` | 73 | Round-1 key — D7 label, LLM label, side. Withheld until the sheet was complete. |
| `reusable_prior_adjudications.csv` | 45 | Disagreements whose sentence, term and rule were unaffected by lexicon curation, carried over rather than re-judged. |
| `adjudication_sheet_ROUND2_BLIND.csv` | 45 | Round-2 worksheet — an independent re-check of those 45, same blind format. |
| `adjudication_KEY_ROUND2.csv` | 45 | Round-2 key. |
| `autogold_no_action.csv` | 313 (312 distinct) | Rows where D7 and the LLM already agree. No human action; the gold is the agreed label. One exact duplicate is dropped downstream, giving the 312 auto rows in the final file. |
| `score_gold.py` | — | Recomposes the gold from the five sources above, checks it row-for-row against the released `exp_a_gold_430.csv`, and recomputes κ(D7, gold) and κ(LLM, gold) over the full 430 and over the 118 human-adjudicated rows alone. |

73 + 45 = 118 adjudicated; 118 + 312 = 430.

## Adjudicator

Both rounds were done by one author against `../CODEBOOK.md`. That is the
limitation the paper states, and it is why the independent second-rater check in
`../second_rater/` exists: a different person, given the same codebook and
nothing else, relabelled a blind sample and agreed with this gold at κ = 0.94.

The headline κ = 0.938 measures fidelity to the codebook as applied by one
coder, not agreement with an independently constituted gold standard.

## Reproduce

```bash
python3 score_gold.py
```

`make check` at `replication/` recomputes the same κ values directly from
`../../results/exp_a/exp_a_gold_430.csv`.
