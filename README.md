# FrIdéo — French News Outlet Ideology Scores

Continuous, ecosystem-wide ideology scores for **30 French national news
outlets**, fusing nine independent evidence families with empirical-Bayes
shrinkage toward a structural prior.

Companion resource for *"FrIdéo: French News Outlet Ideology Scoring via
Multi-Source Evidence Fusion and Distancing-Aware Lexical Scoring"* (ICNLSP 2026).
Amr Sobhy · Le French News Lab · <amr@frenchnewslab.org>

## Scores

| File | Use it for |
|---|---|
| `frideo_scores.csv` | spreadsheets, R, pandas |
| `frideo_scores.json` | code — same rows plus scale metadata (bounds, direction, cutoffs, family list) |
| `DATA_DICTIONARY.md` | column definitions and the scale's limits |
| `MANIFEST.txt` | SHA-256 checksum for every shipped file |

30 rows, sorted left to right. Negative = left, positive = right.

Both are a view of `replication/results/scores_v2.csv`, rebuilt by `make scores`.

The scale is zero-mean and unit-variance by construction across this panel, so
it measures position within the French national news ecosystem rather than
absolute ideology. Five outlets with thin evidence are shrunk toward the prior
and flagged `sparse`. See `DATA_DICTIONARY.md` before using the scores in an
analysis.

## Replication

```bash
shasum -a 256 -c MANIFEST.txt   # verify nothing was altered in transit
cd replication
pip install -r requirements.txt
make check     # verify the paper's headline numbers against the shipped outputs
make scores    # rebuild results/scores_v2.csv from the evidence inputs
make all       # scores + every sensitivity and validation run
```

See `replication/README.md` for layout, evidence families, and shipped inputs.

## Licence

Code MIT (`LICENSE`). Scores CC BY 4.0 (`LICENSE-DATA`).

## Citation

`CITATION.cff` drives GitHub's "Cite this repository" button and is read by
Zenodo and Zotero. It is configured to return the paper, not the repository.

```bibtex
@inproceedings{sobhy2026frideo,
  title     = {{FrIdéo}: French News Outlet Ideology Scoring via Multi-Source
               Evidence Fusion and Distancing-Aware Lexical Scoring},
  author    = {Sobhy, Amr},
  booktitle = {Proceedings of ICNLSP 2026},
  year      = {2026}
}
```
