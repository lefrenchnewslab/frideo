"""
MBFC validation against structurally independent families only.

D4 (MBFC), D2 (audience-perceived ideology), D6b (third-party profiling) and
D8 (Ad Fontes Media) are all external bias raters or audience-perception
proxies, so they overlap methodologically with the MBFC validation target.
This script drops all four and runs the comparison on the five structurally
independent families: D0, D1, D3, D6a, D7.

Usage:
  python scripts/validate_mbfc_independent.py
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from analysis_v2 import (
    DIRECT_FAMILIES,
    load_v2_data,
    inject_d0,
    inject_d3_ppr,
    inject_d7,
    inject_d8_af,
    build_standardized_matrix,
    compute_latent_scores,
    standardize_final,
    compute_labels,
    spearman_rho,
)

# Families excluded because they share methodological overlap with MBFC (D4):
#   D2  — audience-perceived ideology (external rating, partially co-measured)
#   D4  — MBFC itself (the validation target)
#   D6b — third-party journalistic profiling (Wikipedia/press typology; same signal class)
#   D8  — Ad Fontes Media (external media bias rater; same methodology class as D4)
EXCLUDED = {"D2", "D4", "D6b", "D8"}
INDEPENDENT_FAMILIES = [f for f in DIRECT_FAMILIES if f not in EXCLUDED]

MBFC_RAW = {
    "Far Left": -2.0,
    "Left": -2.0,
    "Left-Center": -1.0,
    "Center": 0.0,
    "Least-Biased": 0.0,
    "Right-Center": +1.0,
    "Right": +1.5,
    "Far Right": +2.0,
}

NUMERIC_TO_LABEL = {
    -2.0: "Far Left/Left",
    -1.0: "Left-Center",
     0.0: "Center/Least-Biased",
    +1.0: "Right-Center",
    +1.5: "Right",
    +2.0: "Far Right",
}

mbfc_to_label_map = {
    -2.0: "far-left",
    -1.0: "center-left",
     0.0: "center",
    +1.0: "center-right",
    +1.5: "right",
    +2.0: "far-right",
}

label_order = ["far-left", "left", "center-left", "center", "center-right", "right", "far-right"]
label_idx = {l: i for i, l in enumerate(label_order)}


def main():
    print("=" * 110)
    print("  MBFC VALIDATION: Structurally Independent Families Only")
    print(f"  Families used: {', '.join(INDEPENDENT_FAMILIES)}")
    print(f"  Excluded (methodological overlap with MBFC): {', '.join(sorted(EXCLUDED))}")
    print("=" * 110)

    data = load_v2_data()
    outlets = data["outlets"]
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)

    # Independent-only model
    z = build_standardized_matrix(outlets, families=INDEPENDENT_FAMILIES)
    lat = compute_latent_scores(outlets, z, families=INDEPENDENT_FAMILIES)
    scored, _, _, _ = standardize_final(lat)
    _, labels, _ = compute_labels(scored)

    # No-D4 model (existing comparison baseline from validate_mbfc.py)
    families_no_d4 = [f for f in DIRECT_FAMILIES if f != "D4"]
    z_no_d4 = build_standardized_matrix(outlets, families=families_no_d4)
    lat_no_d4 = compute_latent_scores(outlets, z_no_d4, families=families_no_d4)
    scored_no_d4, _, _, _ = standardize_final(lat_no_d4)

    # Full model (all families)
    z_full = build_standardized_matrix(outlets, families=DIRECT_FAMILIES)
    lat_full = compute_latent_scores(outlets, z_full, families=DIRECT_FAMILIES)
    scored_full, _, _, _ = standardize_final(lat_full)

    rows = []
    for o in outlets:
        name = o["name"]
        mbfc_val = o.get("direct", {}).get("D4")
        if mbfc_val is None:
            continue
        rows.append({
            "name": name,
            "indep_score": scored[name]["final"],
            "indep_label": labels.get(name, "?"),
            "no_d4_score": scored_no_d4[name]["final"],
            "full_score": scored_full[name]["final"],
            "mbfc_val": mbfc_val,
            "mbfc_label": mbfc_to_label_map.get(mbfc_val, "?"),
        })

    rows.sort(key=lambda r: r["indep_score"])

    print(f"\n  {'Outlet':<22} {'Indep Score':>11} {'Indep Label':<15} {'MBFC Label':<15} {'Match'}")
    print(f"  {'-'*80}")

    agree = adj = dist = 0
    for r in rows:
        gap = abs(label_idx.get(r["indep_label"], 3) - label_idx.get(r["mbfc_label"], 3))
        if gap == 0:
            match = "✓"; agree += 1
        elif gap == 1:
            match = "~"; adj += 1
        else:
            match = f"✗({gap})"; dist += 1
        print(f"  {r['name']:<22} {r['indep_score']:>+10.3f}  {r['indep_label']:<15} {r['mbfc_label']:<15} {match}")

    n = len(rows)
    indep_scores = [r["indep_score"] for r in rows]
    no_d4_scores = [r["no_d4_score"] for r in rows]
    full_scores  = [r["full_score"]  for r in rows]
    mbfc_vals    = [r["mbfc_val"]    for r in rows]

    rho_indep  = spearman_rho(indep_scores, mbfc_vals)
    rho_no_d4  = spearman_rho(no_d4_scores, mbfc_vals)
    rho_full   = spearman_rho(full_scores,  mbfc_vals)

    print(f"\n{'='*110}")
    print(f"  SUMMARY (n={n} outlets with MBFC labels)")
    print(f"{'='*110}")
    print(f"  Spearman ρ — independent families only ({','.join(INDEPENDENT_FAMILIES)}): {rho_indep:.4}")
    print(f"  Spearman ρ — no-D4 model (all families minus D4):             {rho_no_d4:.4}")
    print(f"  Spearman ρ — full model (all families):                       {rho_full:.4}")
    print("\n  Label agreement (independent model vs MBFC):")
    print(f"    Exact:    {agree}/{n}")
    print(f"    Adjacent: {adj}/{n}")
    print(f"    Distant:  {dist}/{n}")

    print("\n  Disagreement detail:")
    for r in rows:
        gap = abs(label_idx.get(r["indep_label"], 3) - label_idx.get(r["mbfc_label"], 3))
        if gap >= 1:
            diff = label_idx.get(r["indep_label"], 3) - label_idx.get(r["mbfc_label"], 3)
            direction = " (model more left)" if diff < 0 else " (model more right)"
            print(f"    {r['name']:<22} Indep={r['indep_label']:<14} MBFC={r['mbfc_label']:<14} gap={gap}{direction}")

    out = {
        "independent_families": INDEPENDENT_FAMILIES,
        "excluded_families": sorted(EXCLUDED),
        "n_outlets": n,
        "rho_independent_vs_mbfc": round(rho_indep, 4),
        "rho_no_d4_vs_mbfc": round(rho_no_d4, 4),
        "rho_full_vs_mbfc": round(rho_full, 4),
        "exact_match": agree,
        "adjacent": adj,
        "distant": dist,
        "outlet_scores": [
            {
                "outlet": r["name"],
                "independent_score": round(r["indep_score"], 4),
                "independent_label": r["indep_label"],
                "mbfc_label": r["mbfc_label"],
            }
            for r in rows
        ],
    }
    out_path = Path(__file__).parent.parent / "results" / "mbfc_independent_validation.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
