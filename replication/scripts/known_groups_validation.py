#!/usr/bin/env python3
"""
known_groups_validation.py — formal known-groups separation test.

Validity question: do outlets that an EXTERNAL taxonomy places on the left vs the
right separate on the FrIdéo scale? To keep the test non-circular, groups are
defined by Media Bias Fact Check (MBFC) bands and the scores tested are the
*no-D4 holdout* scores (MBFC/D4 removed from the model), so the grouping variable
is not an input to the scores being separated.

Reads:  results/d4_ablation.json  (no_d4_score per outlet)
Writes: results/known_groups_validation.json

Stats reported: group means/ranges, Mann-Whitney U + rank-biserial AUC,
Cohen's d (pooled SD), and an EXACT one-sided permutation p-value.
Pure standard library; deterministic.
"""
import json, itertools, statistics as st
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "results"

# External MBFC bands (categorical), from the MBFC holdout panel (n=15).
MBFC = {
    'Mediapart':'L','Libération':'L','Le Monde':'L','Le HuffPost':'L','Marianne':'L',
    'Franceinfo':'L','20 Minutes':'L','RFI':'C','France 24':'C','Le Parisien':'R',
    'Le Point':'R','Le Figaro':'R','Causeur':'R','Fdesouche':'R','Valeurs actuelles':'R',
}

def mann_whitney(a, b):
    na, nb = len(a), len(b)
    U = sum((x < y) + 0.5*(x == y) for x in a for y in b)   # U for "a<b"
    return U, U/(na*nb)                                       # AUC = P(right > left)

def cohen_d(a, b):
    na, nb = len(a), len(b)
    sp = (((na-1)*st.variance(a) + (nb-1)*st.variance(b))/(na+nb-2))**0.5
    return (st.mean(b) - st.mean(a))/sp

def exact_perm_p(a, b):
    """Exact one-sided permutation p for mean(b)-mean(a) >= observed, over all
    C(n, nb) relabelings of the pooled values."""
    pool = a + b; n = len(pool); nb = len(b)
    obs = st.mean(b) - st.mean(a)
    tot = ge = 0
    for idx in itertools.combinations(range(n), nb):
        idx = set(idx)
        gb = [pool[i] for i in range(n) if i in idx]
        ga = [pool[i] for i in range(n) if i not in idx]
        ge += (st.mean(gb) - st.mean(ga)) >= obs - 1e-12
        tot += 1
    return ge/tot, tot

def main():
    d = json.load(open(R/"d4_ablation.json"))
    noD4 = {o['outlet']: o['no_d4_score'] for o in d['outlet_deltas']}
    L = sorted(noD4[o] for o,g in MBFC.items() if g == 'L')
    C = sorted(noD4[o] for o,g in MBFC.items() if g == 'C')
    Rr = sorted(noD4[o] for o,g in MBFC.items() if g == 'R')

    U, auc = mann_whitney(L, Rr)
    p, nperm = exact_perm_p(L, Rr)
    out = {
        "grouping": "MBFC bands (external); scores = no-D4 holdout (non-circular)",
        "left":   {"n": len(L), "mean": round(st.mean(L), 4),  "min": round(min(L),4),  "max": round(max(L),4)},
        "center": {"n": len(C), "mean": round(st.mean(C), 4) if C else None},
        "right":  {"n": len(Rr),"mean": round(st.mean(Rr), 4), "min": round(min(Rr),4), "max": round(max(Rr),4)},
        "mann_whitney_U": U,
        "auc": round(auc, 4),
        "cohens_d": round(cohen_d(L, Rr), 3),
        "perm_p_one_sided_exact": round(p, 6),
        "perm_total_relabelings": nperm,
    }
    (R/"known_groups_validation.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
