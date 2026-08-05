"""
Empirical σₖ estimation via leave-one-family-out residual variance.

For each evidence family k:
  1. Run the model without k to get the "consensus" position from all other families
  2. Compute residual_ik = z_ik - mean_z_i^(-k) for every outlet i with data in k
  3. σ_k² = variance(residuals) across all outlets

This replaces manual σₖ assignments with data-driven estimates:
  low σₖ = family closely tracks the aggregate evidence
  high σₖ = family disagrees with the consensus (noisier source)

Usage: python3 scripts/estimate_sigma_empirical.py
"""

import json
import math
import os
import random
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_FILE = BASE / "data" / "outlets_evidence_v2.json"

DIRECT_FAMILIES = ["D0", "D1", "D2", "D3", "D4", "D6a", "D6b", "D7", "D8"]

# Manual σₖ for comparison
MANUAL_SIGMA = {
    "D0":  0.50,
    "D1":  0.5,
    "D2":  0.7,
    "D3":  0.8,
    "D4":  0.9,
    "D6a": 0.65,
    "D6b": 0.90,
    "D7":  0.80,
    "D8":  0.50,  # placeholder — replaced by empirical estimate on first run
}

def load_data():
    sys.path.insert(0, str(BASE))
    # Break the bootstrap circularity: importing analysis_v2 triggers its
    # module-level FAMILY_SIGMA load, which raises if family_sigma.json is
    # missing — exactly the file we are about to generate. This flag tells
    # analysis_v2 to load an empty sigma map during estimation (unused here).
    os.environ["IDEOLOGY_SIGMA_BOOTSTRAP"] = "1"
    from analysis_v2 import inject_d0 as _inject_d0, inject_d3_ppr as _inject_d3_ppr, inject_d7 as _inject_d7, inject_d8_af as _inject_d8_af
    with open(DATA_FILE) as f:
        data = json.load(f)
    outlets = data["outlets"]
    _inject_d0(outlets)      # uses analysis_v2 OWNER_STRUCTURAL — single source of truth
    _inject_d3_ppr(outlets)  # continuous PPR D3
    _inject_d7(outlets)      # endorsed D7 from CSV
    _inject_d8_af(outlets)   # Ad Fontes Media ratings from GN scrape
    return outlets


def _d4_ref_stats(outlets):
    """Return (mean, std) of D4 raw values — used as normalisation reference for D8."""
    d4_vals = [o["direct"]["D4"] for o in outlets if o["direct"].get("D4") is not None]
    if len(d4_vals) < 2:
        return None, None
    mu = sum(d4_vals) / len(d4_vals)
    sd = statistics.pstdev(d4_vals)
    return mu, sd


def z_score_family(outlets, family, ref_mean=None, ref_std=None):
    """Z-score a family across outlets that have data. Returns {name: z}.

    ref_mean / ref_std: normalisation override — used for D8 so it shares
    D4's reference distribution instead of its own compressed 7-outlet panel.
    """
    vals = {
        o["name"]: o["direct"][family]
        for o in outlets
        if o["direct"].get(family) is not None
    }
    if len(vals) < 2:
        return {k: 0.0 for k in vals}
    if ref_mean is not None and ref_std is not None:
        mu, sd = ref_mean, ref_std
    else:
        vlist = list(vals.values())
        mu = sum(vlist) / len(vlist)
        sd = statistics.pstdev(vlist)
    if sd < 1e-9:
        return {k: 0.0 for k in vals}
    return {k: (v - mu) / sd for k, v in vals.items()}


def _build_z_matrix(outlets, families):
    """Build z-matrix with D4-referenced normalisation for D8."""
    d4_mu, d4_sd = _d4_ref_stats(outlets)
    result = {}
    for fam in families:
        if fam == "D8" and d4_mu is not None:
            result[fam] = z_score_family(outlets, fam, ref_mean=d4_mu, ref_std=d4_sd)
        else:
            result[fam] = z_score_family(outlets, fam)
    return result


def compute_empirical_sigmas(outlets):
    """Estimate σₖ for each family via leave-one-out residual variance."""

    # Build full z-matrix
    z_full = _build_z_matrix(outlets, DIRECT_FAMILIES)

    results = {}
    for held_out_fam in DIRECT_FAMILIES:
        remaining = [f for f in DIRECT_FAMILIES if f != held_out_fam]

        # Build LOO z-matrix
        z_loo = _build_z_matrix(outlets, remaining)

        # Compute per-outlet mean of remaining families (the "consensus")
        consensus = {}
        for o in outlets:
            name = o["name"]
            vals = [z_loo[f].get(name) for f in remaining if z_loo[f].get(name) is not None]
            if vals:
                consensus[name] = sum(vals) / len(vals)
            # if no other families cover this outlet, skip

        # Compute residuals for outlets with data in the held-out family
        residuals = []
        n_outlets = 0
        for o in outlets:
            name = o["name"]
            z_ik = z_full[held_out_fam].get(name)
            consensus_i = consensus.get(name)
            if z_ik is not None and consensus_i is not None:
                residuals.append(z_ik - consensus_i)
                n_outlets += 1

        if len(residuals) >= 2:
            var_emp = statistics.variance(residuals)
            sigma_emp = math.sqrt(var_emp)
        else:
            sigma_emp = float("nan")
            var_emp = float("nan")

        results[held_out_fam] = {
            "manual": MANUAL_SIGMA[held_out_fam],
            "empirical_sigma": round(sigma_emp, 4) if not math.isnan(sigma_emp) else None,
            "empirical_var": round(var_emp, 4) if not math.isnan(var_emp) else None,
            "n_residuals": n_outlets,
            "residual_mean": round(statistics.mean(residuals), 4) if residuals else None,
            "residual_std": round(statistics.pstdev(residuals), 4) if residuals else None,
            "residuals": [round(r, 4) for r in residuals],
        }

    return results


def print_comparison(results, outlets):
    print("=" * 130)
    print("  EMPIRICAL σₖ ESTIMATION — Leave-One-Family-Out Residual Variance")
    print("=" * 130)
    print(f"  {'Family':<7} {'Source':<35} {'Manual':>8} {'Empirical':>10} {'n':>4} {'Resid μ':>8} {'Resid σ':>8}  {'Manual/Emp':>10}")
    print(f"  {'-' * 120}")

    fam_descriptions = {
        "D0":  "Owner ideology (structural map)",
        "D1":  "Guest ideology (Cagé et al.)",
        "D2":  "Perceived ideology (Pew)",
        "D3":  "Network block (Cointet et al.)",
        "D4":  "MBFC categorical label",
        "D6a": "Self-declared orientation",
        "D6b": "Third-party profiling (Wikipedia)",
        "D7":  "Content lexical (endorsed)",
        "D8":  "Ad Fontes Media (GN scrape, 7 outlets)",
    }

    for fam in DIRECT_FAMILIES:
        r = results[fam]
        man = r["manual"]
        emp = r["empirical_sigma"]
        n_res = r["n_residuals"]
        rm = r["residual_mean"]
        rs = r["residual_std"]
        ratio = f"{man / emp:.3f}" if emp and emp > 0 else "—"
        emp_str = f"{emp:.4f}" if emp is not None else "   N/A"
        print(f"  {fam:<7} {fam_descriptions[fam]:<35} {man:>8.2f} {emp_str:>10} {n_res:>4} {rm:>+8.4f} {rs:>8.4f}  {ratio:>10}")

    print()

    # Detailed residuals per outlet for each family
    for fam in DIRECT_FAMILIES:
        r = results[fam]
        resids = r["residuals"]
        if not resids:
            continue
        print(f"  [{fam}] n={r['n_residuals']}, σ_emp={r['empirical_sigma']}, manual={r['manual']}")
        print()

    # Summary
    print("  SUMMARY")
    print(f"  {'-' * 80}")
    ratios = []
    for fam in DIRECT_FAMILIES:
        r = results[fam]
        if r["empirical_sigma"] and r["empirical_sigma"] > 0:
            ratios.append(r["manual"] / r["empirical_sigma"])
    if ratios:
        print(f"  Mean manual/empirical ratio: {statistics.mean(ratios):.3f} (SD = {statistics.pstdev(ratios):.3f})")
    print()


def recompute_ci_comparison(outlets, results):
    """Recompute uncertainty with empirical σₖ and compare CI widths vs manual σₖ."""
    import sys
    sys.path.insert(0, str(BASE))
    from analysis_v2 import (
        DIRECT_FAMILIES as DF,
        inject_d0, inject_d3_ppr, inject_d7, inject_d8_af,
        build_standardized_matrix, compute_latent_scores,
        standardize_final, compute_uncertainty, SHRINKAGE_LAMBDA,
         spearman_rho,
    )

    # Reload fresh
    with open(DATA_FILE) as f:
        data = json.load(f)
    outlets_fresh = data["outlets"]
    inject_d0(outlets_fresh)
    inject_d3_ppr(outlets_fresh)
    inject_d7(outlets_fresh)
    inject_d8_af(outlets_fresh)

    # Full pipeline with manual σₖ
    z_matrix = build_standardized_matrix(outlets_fresh)
    latent = compute_latent_scores(outlets_fresh, z_matrix)
    scored, mean_z, std_z, scale_factor = standardize_final(latent)

    import analysis_v2 as aw
    orig_sigma = aw.FAMILY_SIGMA.copy() if aw.FAMILY_SIGMA else {}

    # Uncertainty with manual σₖ — set the baseline explicitly from MANUAL_SIGMA
    # rather than the module-global, which is empty during the sigma bootstrap
    # import (IDEOLOGY_SIGMA_BOOTSTRAP=1). This also makes the "Manual" column
    # genuinely use MANUAL_SIGMA, matching the printed header.
    manual_FAMILY_SIGMA = {fam: MANUAL_SIGMA.get(fam, 1.0) for fam in DF}
    aw.FAMILY_SIGMA = manual_FAMILY_SIGMA.copy()
    sigma_manual = compute_uncertainty(outlets_fresh, scored, scale_factor)

    # Build empirical σₖ dict
    empirical_FAMILY_SIGMA = {}
    for fam in DF:
        emp = results.get(fam, {}).get("empirical_sigma")
        if emp is not None and emp > 0:
            empirical_FAMILY_SIGMA[fam] = emp
        else:
            empirical_FAMILY_SIGMA[fam] = MANUAL_SIGMA.get(fam, 1.0)

    # Recompute uncertainty under empirical σₖ
    aw.FAMILY_SIGMA = empirical_FAMILY_SIGMA.copy()
    sigma_emp = compute_uncertainty(outlets_fresh, scored, scale_factor)

    # Restore original
    aw.FAMILY_SIGMA = orig_sigma

    # Compare CI widths
    print("=" * 130)
    print("  CI WIDTH COMPARISON — Manual σₖ vs Empirical σₖ")
    print("=" * 130)
    print(f"  {'Outlet':<22} {'Manual CI':>16} {'Empirical CI':>16} {'Δ width':>10} {'Manual σ':>10} {'Empirical σ':>10}")
    print(f"  {'-' * 95}")

    width_diffs = []
    for o in sorted(outlets_fresh, key=lambda x: scored[x["name"]]["final"]):
        name = o["name"]
        final = scored[name]["final"]
        ci_w_man = 1.96 * sigma_manual[name] * 2
        ci_w_emp = 1.96 * sigma_emp[name] * 2
        diff = ci_w_emp - ci_w_man
        width_diffs.append(diff)
        print(f"  {name:<22} [{final - 1.96 * sigma_manual[name]:+.2f}, {final + 1.96 * sigma_manual[name]:+.2f}]  "
              f"[{final - 1.96 * sigma_emp[name]:+.2f}, {final + 1.96 * sigma_emp[name]:+.2f}]  "
              f"{diff:>+9.4f}  {sigma_manual[name]:>8.4f}  {sigma_emp[name]:>10.4f}")

    mean_diff = sum(width_diffs) / len(width_diffs) if width_diffs else 0
    print(f"\n  Mean CI width change: {mean_diff:+.4f}")
    print()

    # Bootstrap rank stability with empirical σₖ
    print("  Running bootstrap with empirical σₖ (1000 iterations)...")
    rng = random.Random(42)
    rho_vals = []
    for _ in range(1000):
        lam = max(0.1, SHRINKAGE_LAMBDA * (1 + rng.uniform(-0.5, 0.5)))
        z_p = {
            fam: {n: z + rng.gauss(0, empirical_FAMILY_SIGMA[fam] * 0.3)
                  for n, z in z_matrix[fam].items()}
            for fam in DF
        }
        lat_p = compute_latent_scores(outlets_fresh, z_p, shrinkage_lambda=lam)
        sc_p, _, _, _ = standardize_final(lat_p)
        pert_scores = [sc_p[o["name"]]["final"] for o in outlets_fresh]
        base_scores = [scored[o["name"]]["final"] for o in outlets_fresh]
        rho_vals.append(spearman_rho(base_scores, pert_scores))

    print(f"  Bootstrap rank stability with empirical σₖ: ρ = {sum(rho_vals) / len(rho_vals):.4f}")
    print()


def main():
    outlets = load_data()
    results = compute_empirical_sigmas(outlets)

    print_comparison(results, outlets)

    # Print per-outlet residuals for each family
    print("=" * 130)
    print("  PER-OUTLET RESIDUALS")
    print("=" * 130)

    # Recompute z-scores for detailed reporting
    z_full = _build_z_matrix(outlets, DIRECT_FAMILIES)

    for fam in DIRECT_FAMILIES:
        remaining = [f for f in DIRECT_FAMILIES if f != fam]
        z_loo = _build_z_matrix(outlets, remaining)
        consensus = {}
        for o in outlets:
            name = o["name"]
            vals = [z_loo[f].get(name) for f in remaining if z_loo[f].get(name) is not None]
            if vals:
                consensus[name] = sum(vals) / len(vals)

        print(f"\n  [{fam}] Empirical σ = {results[fam]['empirical_sigma']}  |  Manual σ = {MANUAL_SIGMA[fam]}")
        print(f"  {'Outlet':<22} {'z_ik':>8} {'Consensus':>10} {'Residual':>10}")
        print(f"  {'-' * 55}")
        for o in outlets:
            name = o["name"]
            z_ik = z_full[fam].get(name)
            cons = consensus.get(name)
            if z_ik is not None and cons is not None:
                print(f"  {name:<22} {z_ik:>+8.4f} {cons:>+10.4f} {z_ik - cons:>+10.4f}")

    # Write empirical σₖ values to JSON so analysis_v2.py can load them directly
    sigma_out = {
        fam: results[fam]["empirical_sigma"]
        for fam in DIRECT_FAMILIES
        if results[fam]["empirical_sigma"] is not None
    }
    sigma_path = BASE / "results" / "family_sigma.json"
    import json as _json
    with open(sigma_path, "w") as _f:
        _json.dump(sigma_out, _f, indent=2)
    print(f"  Saved empirical σₖ → {sigma_path}")
    for fam, val in sigma_out.items():
        print(f"    {fam}: {val:.4f}")

    # Recompute CI comparison
    recompute_ci_comparison(outlets, results)


if __name__ == "__main__":
    main()
