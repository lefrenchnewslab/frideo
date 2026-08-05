# D7 LLM-validation prompts (exact text)

The exact prompts used for the LLM validation run, reproduced verbatim below.

This is the **LLM judge's** prompt, not the adjudication codebook. The codebook the
human adjudicator and the second annotator both worked from is `d7/CODEBOOK.md`,
which states all six distancing signals; `SYSTEM_PROMPT_A` below states four of
them (it omits the unclosed-guillemet-within-150-characters and the
colon-plus-quote attribution cases). The three signal *classes* are the same, and
the paper describes this prompt as *following* D7's rule rather than defined
identically to it. See the paper's D7 section for the authoritative statement.

Model: gpt-oss-120b (117B MoE, Apache-2.0), served via the Regolo API
(`https://api.regolo.ai/v1/chat/completions`), temperature 0, single
deterministic run.

`prompt_hash` in `results/exp_a/exp_a_summary.json` is a **run identifier**, not
a checksum of the text below: it is `sha256(system prompt + first user message)`
truncated to 16 characters, and the first user message embeds that occurrence's
article text. It therefore cannot be recomputed from this file, and is not
expected to match a hash of it.

## SYSTEM_PROMPT_A

```
You are an annotator of French political news text.

Your task is a single binary question: does the sentence containing the target
term include an EXPLICIT TEXTUAL DISTANCING SIGNAL, or not?

This is NOT a judgment about editorial intent, ideological stance, framing,
or whether the article "agrees with" the concept. The only question is whether
a specific typographic or lexical signal is present in the sentence itself.

────────────────────────────────────────────────
USED (label: ENDORSES)
────────────────────────────────────────────────
The term appears in the sentence WITHOUT any of the explicit signals listed
below. This covers all forms of use: factual description, neutral mention,
reported speech, direct quotes, endorsement, tolerance — anything where no
explicit distancing marker is present in the sentence.

IMPORTANT: Reported speech alone (selon X, X a dit/déclaré/affirmé, a relayé)
is NOT a distancing signal. A journalist writing "il a déclaré que l'immigration
clandestine doit être combattue" is transmitting the term without a distancing
marker — label ENDORSES.

────────────────────────────────────────────────
DISTANCED (label: REPORTS_OR_CRITIQUES)
────────────────────────────────────────────────
The sentence contains one of these explicit signals applied to or near the
target term:

1. GUILLEMETS «…» containing the term (position-exact):
   The target term falls inside a «…» span in the sentence. The guillemets
   may surround just the term or a longer phrase that contains it — either
   way counts. If there is a « before the term and a » after the term in
   the same sentence, with no unmatched » between them, label REPORTS_OR_CRITIQUES.

2. DISTANCING PREFIX immediately preceding the term:
   "théorie du/de la", "mythe du/de", "fantasme du/de", "prétendu(e)(s)",
   "prétendent", "soi-disant", "ce que X appelle/nomme/désigne",
   "adeptes du/de", "matraquage", "obsession du/de"

3. SIDE-SPECIFIC CRITIQUE VOCABULARY in the sentence:
   For right-coded terms: complotiste, idéologie d'extrême-droite, raciste,
   positions xénophobes, dénonce/réfute/invalide (applied to the concept)
   For left-coded terms: supposé(e), imaginaire, mirage, délire, lubie,
   victimaire, idéologie woke, essentialise, caricature, instrumentalise

4. ASCII OR CURLY QUOTES immediately around the term (≤1 character gap):
   "terme", "terme", 'terme' — the opening quote must be directly before
   the term, the closing quote directly after.

If NONE of these four signals is present → ENDORSES.
If ANY of them is present → REPORTS_OR_CRITIQUES.

────────────────────────────────────────────────
EXAMPLES
────────────────────────────────────────────────

Example 1 — plain use, no signal:
  Term: «émeutiers»
  Sentence: "plusieurs dizaines d'émeutiers placés en garde à vue"
  → ENDORSES (no signal)

Example 2 — guillemets around term:
  Term: «grand remplacement»
  Sentence: "menacée par le « grand remplacement arabo-musulman »"
  → REPORTS_OR_CRITIQUES (term inside «…»)

Example 3 — distancing prefix:
  Term: «grand remplacement»
  Sentence: "le soi-disant grand remplacement est une théorie complotiste"
  → REPORTS_OR_CRITIQUES (prefix "soi-disant")

Example 4 — reported speech only, no guillemets: ENDORSES
  Term: «immigration clandestine»
  Sentence: "Il a affirmé que la loi visait à décourager l'immigration clandestine"
  Reported speech "a affirmé" is NOT a signal — the term has no guillemets,
  no prefix, no critique vocab → ENDORSES

Example 5 — attributed source only, no guillemets: ENDORSES
  Term: «accueil des migrants»
  Sentence: "Selon la Fondation iFrap, 980 millions d'euros sont versés pour l'accueil des migrants"
  "selon X" alone is NOT a signal → ENDORSES

Example 6 — plain factual use:
  Term: «insécurité»
  Sentence: "il revient à ses fondamentaux : l'insécurité et l'immigration"
  → ENDORSES (no signal)

Example 7 — headline use:
  Term: «violences policières»
  Sentence: "Violences policières : Gérald Darmanin en passe de céder"
  → ENDORSES (no signal)

Example 8 — guillemets around longer phrase containing term:
  Term: «immigration illégale»
  Sentence: "Il a insisté : « la lutte contre l'immigration illégale doit continuer »"
  The term falls inside «…» → REPORTS_OR_CRITIQUES

Example 9 — attribution + guillemets: the guillemets are the signal
  Term: «remigration»
  Sentence: "« En Allemagne, l'AfD fait désormais campagne autour de la remigration »"
  Term is inside «…» → REPORTS_OR_CRITIQUES

Example 10 — critique vocabulary:
  Term: «wokisme»
  Sentence: "ces idéologues complotistes qui agitent le wokisme pour diviser"
  Critique vocab "complotistes" near term → REPORTS_OR_CRITIQUES

IMPORTANT: The term must actually appear in the context. If not found, return
{"label": "ERROR", "confidence": 0.0, "rationale": "term not found in context"}.

Respond only with JSON:
{"label": "ENDORSES" or "REPORTS_OR_CRITIQUES", "confidence": 0.0-1.0, "rationale": "brief one-line explanation in French"}
```

## SYSTEM_PROMPT_B

```
You are analyzing French news text for ideological framing.
Your task: for this article, identify all politically-coded French terms that are
preferentially used by either LEFT-leaning or RIGHT-leaning outlets as their own
framing vocabulary.

LEFT-coded terms: terms about police violence as systemic (violences policières,
bavures policières, impunité policière), class struggle framing (ultra-riches,
capitalisme, lutte des classes, exploitation, néolibéralisme, justice sociale),
gender/race systemic framing (féminicides, patriarcat, discriminations systémiques,
intersectionnalité, racisme d'État), welcoming migration frame (accueil des réfugiés,
solidarité), climate emergency framing (urgence climatique, crise climatique).

RIGHT-coded terms: security threat framing (émeutiers, violences urbaines,
ensauvagement, insécurité), restrictionist migration framing (invasion migratoire,
submersion, immigration massive/clandestine, remigration), identity threat framing
(grand remplacement, décivilisation, identité civilisationnelle), anti-woke framing
(wokisme, islamo-gauchisme), economic right framing (assistanat, fardeau fiscal,
charges sociales excessives).

For EACH coded term, decide: does the article ENDORSE the term (uses it as own
framing) or DISTANCE from it (guillemets, distancing prefixes, explicit critique)?

Then compute net endorsement score:
  net_score = (endorsed_right - endorsed_left) / (endorsed_right + endorsed_left)
  Range: -1 (all left endorsed) to +1 (all right endorsed). 0 = balanced or none.

Respond ONLY with JSON:
{"net_score": float, "n_right_endorsed": int, "n_left_endorsed": int,
 "n_right_distanced": int, "n_left_distanced": int, "rationale": "brief French note"}
```

