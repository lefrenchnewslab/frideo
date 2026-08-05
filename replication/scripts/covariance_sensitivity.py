"""
Covariance-adjusted uncertainty estimates.

The model's var_i = Σ σₖ² assumes independent families. This recomputes CIs
under a conservative pairwise ρ=0.3 among the families most likely to co-vary
(D4, D6b, D2 — all external-rating or audience-perception signals) and checks
whether any outlet's CI then spans an additional label boundary.

Output: results/covariance_sensitivity.csv  +  console summary
"""

import csv
import math
import sys
from pathlib import Path

# ── bootstrap analysis_v2 ─────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from analysis_v2 import (
    FAMILY_SIGMA,
    SHRINKAGE_LAMBDA,
    load_v2_data,
    inject_d0,
    inject_d3_ppr,
    inject_d7,
    inject_d8_af,
    build_standardized_matrix,
    compute_latent_scores,
    standardize_final,
    compute_uncertainty,
    compute_labels,
)

RESULTS_DIR = BASE / "results"

# ── covariance pairs and assumed ρ ───────────────────────────────────────────
# These families overlap in what they measure:
#   D4 (MBFC): third-party editorial bias rating
#   D6b (Wikipedia): third-party journalistic profiling
#   D2 (Pew): audience-perceived ideology survey
# All three track the same underlying "how is this outlet seen by outsiders" signal.
# Conservative assumption: pairwise ρ = 0.3 among the trio.
# D3 (Cointet network) also partially overlaps but reflects structural position more
# than perception — omitted from the trio to keep the analysis conservative.
CORRELATED_TRIO = {"D4", "D6b", "D2"}
RHO_CONSERVATIVE = 0.3


def adjusted_variance(available_fams: list) -> tuple:
    """
    Returns (var_base, var_cov, n_cov_pairs) for an outlet's available families.
    var_base = Σ σₖ²  (current formula, no covariance)
    var_cov  = Σ σₖ² + 2 Σ_{j<k in trio ∩ available} ρ σⱼ σₖ
    """
    var_base = sum(FAMILY_SIGMA[f] ** 2 for f in available_fams)

    # Add cross-terms for correlated pairs that are both available
    trio_avail = [f for f in available_fams if f in CORRELATED_TRIO]
    cov_sum = 0.0
    n_cov_pairs = 0
    for i in range(len(trio_avail)):
        for j in range(i + 1, len(trio_avail)):
            cov_sum += RHO_CONSERVATIVE * FAMILY_SIGMA[trio_avail[i]] * FAMILY_SIGMA[trio_avail[j]]
            n_cov_pairs += 1

    var_cov = var_base + 2 * cov_sum
    return var_base, var_cov, n_cov_pairs


def compute_adjusted_sigma(n_direct: int, var_cov: float, scale_factor: float) -> float:
    if n_direct == 0:
        return scale_factor * 1.5
    base_sigma = scale_factor * math.sqrt(var_cov) / n_direct
    sparsity = SHRINKAGE_LAMBDA / (n_direct + SHRINKAGE_LAMBDA)
    return base_sigma * (1 + sparsity)


def main():
    outlets = load_v2_data()["outlets"]
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)

    z_matrix = build_standardized_matrix(outlets)
    latent = compute_latent_scores(outlets, z_matrix)
    scored, mean_z, std_z, scale_factor = standardize_final(latent)
    cutoffs, labels_base, _ = compute_labels(scored)

    # Baseline (no covariance)
    sigma_base = compute_uncertainty(outlets, scored, scale_factor)

    rows = []
    label_changes = []

    for outlet in sorted(outlets, key=lambda o: scored[o["name"]]["final"]):
        name = outlet["name"]
        s = scored[name]
        final = s["final"]
        n = s["n_direct"]
        prof = s["evidence_profile"]

        available_fams = [f for f in prof if prof[f] is not None]
        var_base, var_cov, n_cov_pairs = adjusted_variance(available_fams)

        sig_base = sigma_base[name]
        sig_cov = compute_adjusted_sigma(n, var_cov, scale_factor)

        ci_base = (final - 1.96 * sig_base, final + 1.96 * sig_base)
        ci_cov  = (final - 1.96 * sig_cov,  final + 1.96 * sig_cov)

        # Label under base vs. covariance-adjusted CIs:
        # Label assignment is based on the point estimate (unchanged), so the
        # label itself doesn't change — but we check whether the CI now spans
        # an additional label boundary, which would indicate the assignment is uncertain.
        label = labels_base[name]

        # Which label boundaries does the adjusted CI span?
        boundaries_in_base_ci = [c for c in cutoffs if ci_base[0] <= c <= ci_base[1]]
        boundaries_in_cov_ci  = [c for c in cutoffs if ci_cov[0]  <= c <= ci_cov[1]]

        newly_spanned = [c for c in boundaries_in_cov_ci if c not in boundaries_in_base_ci]

        if newly_spanned:
            label_changes.append({
                "outlet": name,
                "label": label,
                "n_new_boundaries": len(newly_spanned),
                "ci_base": f"[{ci_base[0]:+.3f}, {ci_base[1]:+.3f}]",
                "ci_cov":  f"[{ci_cov[0]:+.3f},  {ci_cov[1]:+.3f}]",
            })

        rows.append({
            "outlet": name,
            "final_score": round(final, 4),
            "label": label,
            "n_direct": n,
            "n_cov_pairs": n_cov_pairs,
            "var_base": round(var_base, 6),
            "var_cov": round(var_cov, 6),
            "var_inflation_pct": round(100 * (var_cov - var_base) / var_base, 1) if var_base > 0 else 0,
            "sigma_base": round(sig_base, 4),
            "sigma_cov": round(sig_cov, 4),
            "sigma_inflation_pct": round(100 * (sig_cov - sig_base) / sig_base, 1) if sig_base > 0 else 0,
            "ci_base_lo": round(ci_base[0], 4),
            "ci_base_hi": round(ci_base[1], 4),
            "ci_cov_lo": round(ci_cov[0], 4),
            "ci_cov_hi": round(ci_cov[1], 4),
            "ci_halfwidth_base": round(1.96 * sig_base, 4),
            "ci_halfwidth_cov": round(1.96 * sig_cov, 4),
            "new_boundaries_spanned": len(newly_spanned),
        })

    # ── write CSV ──────────────────────────────────────────────────────────────
    out_path = RESULTS_DIR / "covariance_sensitivity.csv"
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # ── console summary ────────────────────────────────────────────────────────
    print("=" * 72)
    print("COVARIANCE SENSITIVITY ANALYSIS")
    print(f"Conservative pairwise ρ = {RHO_CONSERVATIVE} among {{ D4, D6b, D2 }}")
    print("=" * 72)

    mean_inflation = sum(r["sigma_inflation_pct"] for r in rows) / len(rows)
    max_inflation  = max(r["sigma_inflation_pct"] for r in rows)
    mean_halfwidth_base = sum(r["ci_halfwidth_base"] for r in rows) / len(rows)
    mean_halfwidth_cov  = sum(r["ci_halfwidth_cov"]  for r in rows) / len(rows)

    print(f"\nMean CI half-width (base):  {mean_halfwidth_base:.3f}σ")
    print(f"Mean CI half-width (cov):   {mean_halfwidth_cov:.3f}σ")
    print(f"Mean σ inflation:           {mean_inflation:.1f}%")
    print(f"Max σ inflation:            {max_inflation:.1f}%")

    print(f"\n{'Outlet':<22} {'Label':<12} {'n':<3} {'pairs':<6} "
          f"{'σ_base':>7} {'σ_cov':>7} {'infl%':>6} {'new_bnd':>8}")
    print("-" * 78)
    for r in rows:
        print(f"{r['outlet']:<22} {r['label']:<12} {r['n_direct']:<3} "
              f"{r['n_cov_pairs']:<6} {r['sigma_base']:>7.4f} {r['sigma_cov']:>7.4f} "
              f"{r['sigma_inflation_pct']:>5.1f}% {r['new_boundaries_spanned']:>8}")

    print("\n── Label boundary crossings under covariance-adjusted CIs ──────────────")
    if label_changes:
        for lc in label_changes:
            print(f"  {lc['outlet']:<22} {lc['label']:<12}  base={lc['ci_base']}  cov={lc['ci_cov']}  "
                  f"({lc['n_new_boundaries']} new boundary)")
    else:
        print("  None — no outlet's CI crosses an additional label boundary.")
        print("  Point-estimate label assignments are unchanged under conservative covariance.")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
