"""
Cross-family convergence: pairwise correlations + PCA.

Latent construct validity: whether conceptually distinct evidence families
point in the same direction, and whether a single dominant dimension explains
most shared variance.

Families included: D0, D3, D4, D6a, D6b, D7 (n>=10 pairwise overlap).
Excluded: D1, D2, D8 (too few overlapping outlets for a reliable r).

PCA uses the 4 highest-coverage families (D0, D3, D6b, D7) on their
complete-case outlets to avoid imputation artifacts.

Output:
  results/cross_family_corr.csv      — pairwise r and n matrix
  results/cross_family_pca.json      — PC1 variance explained + loadings
  Console summary of key numbers for paper reporting.
"""

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from analysis_v2 import (
    load_v2_data,
    inject_d0,
    inject_d3_ppr,
    inject_d7,
    inject_d8_af,
    build_standardized_matrix,
)

RESULTS = BASE / "results"

# Families with sufficient pairwise overlap (n >= 10 for at least some pairs)
FAMILIES = ["D0", "D3", "D4", "D6a", "D6b", "D7"]

# Families used for PCA (coverage >= 21 outlets)
PCA_FAMILIES = ["D0", "D3", "D6b", "D7"]


def pearson_r(xs, ys):
    """Pearson r on paired non-null values; returns (r, n)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, n
    xs_, ys_ = zip(*pairs)
    mx, my = sum(xs_) / n, sum(ys_) / n
    num = sum((x - mx) * (y - my) for x, y in pairs)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs_))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys_))
    if sx == 0 or sy == 0:
        return None, n
    return num / (sx * sy), n


def pca_1d(matrix):
    """Return (pc1_variance_explained, loadings) via covariance eigen-decomposition."""
    arr = np.array(matrix, dtype=float)
    # centre columns
    arr = arr - arr.mean(axis=0)
    cov = np.cov(arr.T)
    if cov.ndim == 0:
        return 1.0, [1.0]
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # eigh returns ascending order — reverse
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    total = eigenvalues.sum()
    pc1_var = float(eigenvalues[0] / total) if total > 0 else 0.0
    loadings = eigenvectors[:, 0].tolist()
    return pc1_var, loadings, eigenvalues.tolist()


def main():
    outlets = load_v2_data()["outlets"]
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)
    z_matrix = build_standardized_matrix(outlets)

    outlet_names = [o["name"] for o in outlets]

    # Build per-family z vectors (None for missing)
    fam_vecs = {}
    for fam in FAMILIES:
        fam_vecs[fam] = [z_matrix[fam].get(name) for name in outlet_names]

    # ── Pairwise correlation matrix ───────────────────────────────────────────
    corr_rows = []
    print("\n=== Pairwise Pearson correlations (pairwise complete obs) ===\n")

    for fam_a in FAMILIES:
        row = {"family": fam_a}
        for fam_b in FAMILIES:
            r, n = pearson_r(fam_vecs[fam_a], fam_vecs[fam_b])
            row[f"r_{fam_b}"] = round(r, 3) if r is not None else None
            row[f"n_{fam_b}"] = n
        corr_rows.append(row)

    # Print readable matrix
    print(f"{'':6s}", end="")
    for f in FAMILIES:
        print(f"{f:>9s}", end="")
    print()
    for row in corr_rows:
        print(f"{row['family']:6s}", end="")
        for f in FAMILIES:
            r = row[f"r_{f}"]
            n = row[f"n_{f}"]
            cell = f"{r:.2f}({n})" if r is not None else f"--({n})"
            print(f"{cell:>9s}", end="")
        print()

    # Save CSV
    corr_csv = RESULTS / "cross_family_corr.csv"
    with open(corr_csv, "w", newline="") as f:
        fieldnames = ["family"] + [f"r_{x}" for x in FAMILIES] + [f"n_{x}" for x in FAMILIES]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(corr_rows)
    print(f"\nSaved: {corr_csv}")

    # ── PCA on D0, D3, D6b, D7 (complete cases) ──────────────────────────────
    pca_vecs = {f: fam_vecs[f] for f in PCA_FAMILIES}
    complete = [
        i for i in range(len(outlet_names))
        if all(pca_vecs[f][i] is not None for f in PCA_FAMILIES)
    ]
    pca_outlets = [outlet_names[i] for i in complete]
    matrix = [[pca_vecs[f][i] for f in PCA_FAMILIES] for i in complete]

    print(f"\n=== PCA on {PCA_FAMILIES} (n={len(pca_outlets)} complete-case outlets) ===\n")
    print("Outlets included:", ", ".join(pca_outlets))

    pc1_var, loadings, eigenvalues = pca_1d(matrix)

    print(f"\nPC1 variance explained: {pc1_var:.1%}")
    print(f"Eigenvalues: {[round(e, 3) for e in eigenvalues]}")
    print("PC1 loadings:")
    for f, l in zip(PCA_FAMILIES, loadings):
        sign = "+" if l >= 0 else ""
        print(f"  {f}: {sign}{l:.3f}")

    pca_result = {
        "families": PCA_FAMILIES,
        "n_outlets": len(pca_outlets),
        "outlets": pca_outlets,
        "pc1_variance_explained": round(pc1_var, 4),
        "eigenvalues": [round(e, 4) for e in eigenvalues],
        "pc1_loadings": {f: round(l, 4) for f, l in zip(PCA_FAMILIES, loadings)},
    }
    pca_json = RESULTS / "cross_family_pca.json"
    with open(pca_json, "w") as f:
        json.dump(pca_result, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {pca_json}")

    # ── Off-diagonal mean r (excluding self-correlations and sparse pairs) ────
    off_diag_rs = []
    for row in corr_rows:
        for f in FAMILIES:
            if f != row["family"]:
                r = row[f"r_{f}"]
                n = row[f"n_{f}"]
                if r is not None and n >= 10:
                    off_diag_rs.append(r)
    if off_diag_rs:
        mean_r = sum(off_diag_rs) / len(off_diag_rs)
        print(f"\nMean pairwise r (n>=10 pairs, off-diagonal): {mean_r:.3f} (k={len(off_diag_rs)} pairs)")

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
