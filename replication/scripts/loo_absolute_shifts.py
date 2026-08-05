"""
Leave-one-family-out sensitivity, in absolute score shifts.

Rank correlation can stay perfect while a family shifts every outlet by 0.5σ,
so this reports max and mean absolute shift per dropped family alongside ρ.

Output: results/loo_absolute_shifts.csv  +  console summary
"""

import csv
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from analysis_v2 import (
    DIRECT_FAMILIES,
    load_v2_data,
    inject_d0,
    inject_d3_ppr,
    inject_d7,
    inject_d8_af,
    build_standardized_matrix,
    standardize_family,
    compute_latent_scores,
    standardize_final,
    spearman_rho,
)

RESULTS_DIR = BASE / "results"


def main():
    outlets = load_v2_data()["outlets"]
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)
    names = [o["name"] for o in outlets]

    # Full model
    z_full = build_standardized_matrix(outlets)
    lat_full = compute_latent_scores(outlets, z_full)
    scored_full, _, _, _ = standardize_final(lat_full)
    full_scores = {n: scored_full[n]["final"] for n in names}

    rows = []
    for drop_fam in DIRECT_FAMILIES:
        # Build LOO matrix
        z_loo = {fam: standardize_family(outlets, fam) for fam in DIRECT_FAMILIES if fam != drop_fam}
        z_loo[drop_fam] = {}

        lat_loo = compute_latent_scores(outlets, z_loo)
        scored_loo, _, _, _ = standardize_final(lat_loo)
        loo_scores = {n: scored_loo[n]["final"] for n in names}

        # Outlets affected (had this family in full model)
        affected = [n for n in names if z_full[drop_fam].get(n) is not None]
        n_affected = len(affected)

        # Spearman ρ on all outlets
        rho = spearman_rho(
            [full_scores[n] for n in names],
            [loo_scores[n] for n in names],
        )

        # Absolute shifts
        shifts = {n: abs(full_scores[n] - loo_scores[n]) for n in names}
        max_shift = max(shifts.values())
        mean_shift = sum(shifts.values()) / len(shifts)
        max_outlet = max(shifts, key=shifts.get)

        # Affected-only shifts (outlets that actually lost this family)
        if affected:
            shifts_affected = [shifts[n] for n in affected]
            max_shift_aff  = max(shifts_affected)
            mean_shift_aff = sum(shifts_affected) / len(shifts_affected)
        else:
            max_shift_aff  = 0.0
            mean_shift_aff = 0.0

        rows.append({
            "family_dropped": drop_fam,
            "n_outlets_with_family": n_affected,
            "spearman_rho": round(rho, 4),
            "max_abs_shift_all": round(max_shift, 4),
            "mean_abs_shift_all": round(mean_shift, 4),
            "max_shift_outlet": max_outlet,
            "max_abs_shift_affected": round(max_shift_aff, 4),
            "mean_abs_shift_affected": round(mean_shift_aff, 4),
        })

    # ── write CSV ──────────────────────────────────────────────────────────────
    out_path = RESULTS_DIR / "loo_absolute_shifts.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ── console summary ────────────────────────────────────────────────────────
    print("=" * 90)
    print("LOO SENSITIVITY — Rank Correlation + Absolute Score Shifts")
    print("=" * 90)
    print(f"\n{'Family':<8} {'n_outlets':>9} {'ρ':>7} {'max_Δ_all':>10} {'mean_Δ_all':>11} "
          f"{'max_Δ_affected':>14}  {'max_Δ outlet'}")
    print("-" * 90)
    for r in rows:
        print(f"{r['family_dropped']:<8} {r['n_outlets_with_family']:>9} "
              f"{r['spearman_rho']:>7.4f} {r['max_abs_shift_all']:>10.4f} "
              f"{r['mean_abs_shift_all']:>11.4f} {r['max_abs_shift_affected']:>14.4f}"
              f"  {r['max_shift_outlet']}")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
