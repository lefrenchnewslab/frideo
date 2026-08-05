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

Sections 1–7 above are byte-identical to `../CODEBOOK.md`, the codebook the
first adjudicator worked from. That is deliberate: the two raters must apply the
same rule for their agreement to mean anything. Only this manifest differs,
because the two passes have different worksheets.

| File | What |
|---|---|
| `second_rater_sheet_TEMPLATE.csv` | **100 rows — this is your work.** Blank `your_label_PLAIN_or_QUALIFIED` column; fill it in and save as `second_rater_sheet_BLIND.csv`. |
| `second_rater_sheet_BLIND.csv` | The same 100 rows as returned by the second rater, labels filled. This is what `score_second_rater.py` reads. |
| `second_rater_KEY.csv` | Stratum, side, D7 label and author gold for each item. Withheld from the rater until the pass was complete — do **not** open before finishing. |

Then: `python3 score_second_rater.py`

You were given `CODEBOOK.md` and `second_rater_sheet_TEMPLATE.csv` and nothing
else — no D7 output, no LLM labels, no author gold, no key. See `ANNOTATOR.md`.
