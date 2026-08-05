# D7 Adjudication Codebook — PLAIN vs QUALIFIED

Use this and nothing else. It matches `d7_score.py::_occurrence_distanced()`,
`d7_terms.py` (current), and the paper's D7 section. Six signals.

## The task

For each row you see a **target term** and the **sentence** containing it
(`pre_context` is there only if the sentence is ambiguous on its own).

Decide whether the sentence carries an **explicit textual distancing signal**
applied to that term.

- **QUALIFIED** — any one of the six signals below is present.
- **PLAIN** — none of them is present. Absence defaults to PLAIN.

Write `PLAIN`, `QUALIFIED`, or `UNCERTAIN` in `your_label_PLAIN_or_QUALIFIED`.
`UNCERTAIN` is excluded from scoring, not counted against you — use it rather
than guessing.

## This is mechanical, not interpretive

Judge **only** whether the signal is physically present in the text. Do **not**
judge whether the outlet endorses the idea, whether the claim is true, or the
politics of the article. Same rule as the original study.

## The six signals — any one ⇒ QUALIFIED

1. **Guillemets.** The term falls inside a « … » pair.
2. **ASCII / curly quotes.** The term is tightly wrapped in `"…"` or `"…"`
   (opening quote immediately before, closing immediately after — ≤1 char gap).
3. **Unclosed guillemet.** A « opens within ~150 characters before the term and
   never closes before it.
4. **Colon-plus-quote attribution.** The term follows a `: «` / `: "` construction
   within ~100 characters. (A section header like `débat :` does not count.)
5. **Distancing prefix** immediately before the term — *théorie du/de la*,
   *mythe du/de*, *fantasme du/de*, *prétendu(e)(s)*, *prétendent*, *soi-disant*,
   *ce que X appelle/nomme/désigne*, *adeptes du/de*, *matraquage*, *obsession du/de*.
6. **Side-specific critique vocabulary** anywhere in the sentence:
   - for **right**-coded terms: *complotiste*, *idéologie d'extrême-droite*,
     *raciste*, *positions xénophobes*, *dénonce / réfute / invalide* applied to
     the concept
   - for **left**-coded terms: *supposé(e)*, *imaginaire*, *mirage*, *délire*,
     *lubie*, *victimaire*, *idéologie woke*, *essentialise*, *caricature*,
     *instrumentalise*

The sheet does not tell you the side. If signal 6 is your deciding factor and
you are unsure which side the term is coded on, use `UNCERTAIN`.

## Explicitly NOT signals

- **Reported speech or attribution on its own.** *selon X*, *X a dit / déclaré /
  affirmé*, *a relayé* — none of these qualifies. A term inside a quotation is
  QUALIFIED only because of signals 1–4 (the quote marks), never because someone
  is being quoted.
- The general tone of the article, whether the claim is factually correct, or
  your own view of the term.

## Examples

| Text | Label | Why |
|---|---|---|
| `le « grand remplacement » théorisé par Renaud Camus` | QUALIFIED | signal 1 |
| `la théorie du grand remplacement` | QUALIFIED | signal 5 |
| `lutter contre l'immigration massive` | PLAIN | no signal |
| `il a déclaré qu'il faut stopper l'ensauvagement` | PLAIN | reported speech is not a signal |
| `ces complotistes qui agitent le wokisme` | QUALIFIED | signal 6 (right-coded term) |

## Files

This is the codebook the first adjudicator worked from, and — sections 1–7
byte-identical — the one given to the independent second rater
(`second_rater/CODEBOOK.md`). Only the manifest below differs between the two,
because the two passes have different worksheets.

The worksheets for this pass are in `adjudication/`:

| File | What |
|---|---|
| `adjudication/adjudication_sheet_BLIND.csv` | **73 rows — round-1 work.** Fill `your_label_PLAIN_or_QUALIFIED`. Keep the filename. |
| `adjudication/adjudication_KEY.csv` | Round-1 key — do **not** open before finishing. |
| `adjudication/adjudication_sheet_ROUND2_BLIND.csv` | 45 rows, round 2 — an independent re-check of the carried-over adjudications. |
| `adjudication/adjudication_KEY_ROUND2.csv` | Round-2 key. |
| `adjudication/reusable_prior_adjudications.csv` | 45 rows carried over unchanged because lexicon curation did not affect their sentence, term or rule; round 2 re-checks them. |
| `adjudication/autogold_no_action.csv` | 313 rows (312 distinct) where D7 and the LLM agree; no action. |

Then: `python3 adjudication/score_gold.py`

See `adjudication/README.md` for how the four sources compose into the 430-row
gold standard.
