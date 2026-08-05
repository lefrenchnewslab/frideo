"""
Validation: Compare no-D4 model scores against MBFC labels.

Since D4 (MBFC) is near-redundant as input (ρ=0.9992),
we can repurpose it as an independent validation signal.

Usage:
  python scripts/validate_mbfc.py
"""

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

# MBFC scale: same as in outlets_evidence_v2.json _meta.direct_families.D4.scale
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

# Reverse: numeric → label (closest match)
NUMERIC_TO_LABEL = {
    -2.0: "Far Left/Left",
    -1.0: "Left-Center",
     0.0: "Center/Least-Biased",
    +1.0: "Right-Center",
    +1.5: "Right",
    +2.0: "Far Right",
}

def get_mbfc_value(outlet):
    """Get MBFC numeric value for an outlet if available."""
    d4 = outlet.get("direct", {}).get("D4")
    return d4 if d4 is not None else None

def get_mbfc_label(outlet):
    """Get human-readable MBFC label."""
    d4_mbfc = outlet.get("d4_mbfc", {})
    return d4_mbfc.get("label", "N/A")


def main():
    print("=" * 110)
    print("  MBFC VALIDATION: No-D4 Model Scores vs MBFC Labels")
    print("=" * 110)

    # Load data
    data = load_v2_data()
    outlets = data["outlets"]
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)

    # ── No-D4 model ──────────────────────────────────────────────────────
    families_no_d4 = [f for f in DIRECT_FAMILIES if f != "D4"]
    z_no_d4 = build_standardized_matrix(outlets, families=families_no_d4)
    lat_no_d4 = compute_latent_scores(outlets, z_no_d4, families=families_no_d4)
    scored_no_d4, _, _, _ = standardize_final(lat_no_d4)
    cutoffs_no_d4, labels_no_d4, _ = compute_labels(scored_no_d4)

    # ── Collect MBFC-outlet data ─────────────────────────────────────────
    rows = []
    for o in outlets:
        name = o["name"]
        mbfc_val = get_mbfc_value(o)
        if mbfc_val is None:
            continue  # skip outlets without MBFC label
        model_score = scored_no_d4[name]["final"]
        model_label = labels_no_d4.get(name, "?")
        mbfc_label = get_mbfc_label(o)
        mbfc_label_clean = NUMERIC_TO_LABEL.get(mbfc_val, f"Unknown({mbfc_val})")
        rows.append({
            "name": name,
            "model_score": model_score,
            "model_label": model_label,
            "mbfc_val": mbfc_val,
            "mbfc_label": mbfc_label,
            "mbfc_label_canon": mbfc_label_clean,
        })

    # Sort by model score
    rows.sort(key=lambda r: r["model_score"])

    # ── Print comparison table ───────────────────────────────────────────
    print(f"\n  {'Outlet':<22} {'Model Score':>11} {'Model Label':<14} {'MBFC Val':>9} {'MBFC Label':<20} {'Agree':<6}")
    print(f"  {'-'*90}")

    # Map labels to ordinal for comparison
    label_order = ["far-left", "left", "center-left", "center", "center-right", "right", "far-right"]
    label_idx = {l: i for i, l in enumerate(label_order)}

    # Normalize MBFC values to rank order for label comparison
    # MBFC: Far Left=-2 → far-left, Left-Center=-1 → center-left/center, 
    # Center=0 → center, Right-Center=+1 → center-right, Right=+1.5 → right, Far Right=+2 → far-right
    mbfc_to_label_map = {
        -2.0: "far-left",
        -1.0: "center-left",
         0.0: "center",
        +1.0: "center-right",
        +1.5: "right",
        +2.0: "far-right",
    }

    agree_count = 0
    adj_count = 0
    diff_count = 0

    for r in rows:
        model_lbl = r["model_label"]
        mbfc_lbl = mbfc_to_label_map.get(r["mbfc_val"], "?")
        r["mbfc_label_canon_full"] = mbfc_lbl

        gap = abs(label_idx.get(model_lbl, 3) - label_idx.get(mbfc_lbl, 3))
        if gap == 0:
            match = "✓"
            agree_count += 1
        elif gap == 1:
            match = "~"
            adj_count += 1
        else:
            match = f"✗({gap})"
            diff_count += 1

        print(f"  {r['name']:<22} {r['model_score']:>+10.3f}  {model_lbl:<14} "
              f"{r['mbfc_val']:>+8.1f}  {r['mbfc_label_canon']:<20} {match:<6}")

    n_total = len(rows)

    # ── Correlations ─────────────────────────────────────────────────────
    model_scores = [r["model_score"] for r in rows]
    mbfc_values = [r["mbfc_val"] for r in rows]
    rho = spearman_rho(model_scores, mbfc_values)

    print(f"\n{'='*110}")
    print("  SUMMARY")
    print(f"{'='*110}")
    print(f"  Spearman ρ (no-D4 model vs MBFC): {rho:.4f}  (n={n_total} outlets)")
    print("")
    print("  Label agreement (no-D4 model labels vs MBFC canonical labels):")
    print(f"    Exact match:  {agree_count}/{n_total} ({100*agree_count/n_total:.0f}%)")
    print(f"    Adjacent:     {adj_count}/{n_total} ({100*adj_count/n_total:.0f}%)")
    print(f"    Disagree (≥2): {diff_count}/{n_total} ({100*diff_count/n_total:.0f}%)")

    # ── Detail on disagreements ──────────────────────────────────────────
    print("\n  Disagreement detail:")
    for r in rows:
        model_lbl = r["model_label"]
        mbfc_lbl = r["mbfc_label_canon_full"]
        gap = abs(label_idx.get(model_lbl, 3) - label_idx.get(mbfc_lbl, 3))
        if gap >= 1:
            direction = ""
            if model_lbl in label_order and mbfc_lbl in label_order:
                diff = label_idx[model_lbl] - label_idx[mbfc_lbl]
                direction = " (model more left)" if diff < 0 else " (model more right)"
            print(f"    {r['name']:<22} Model={model_lbl:<14} MBFC={mbfc_lbl:<14} gap={gap}{direction}")

    # ── Full-model comparison ────────────────────────────────────────────
    families_all = DIRECT_FAMILIES
    z_all = build_standardized_matrix(outlets, families=families_all)
    lat_all = compute_latent_scores(outlets, z_all, families=families_all)
    scored_all, _, _, _ = standardize_final(lat_all)

    full_scores = [scored_all[r["name"]]["final"] for r in rows]
    rho_full = spearman_rho(full_scores, mbfc_values)

    print("\n  For comparison:")
    print(f"    Spearman ρ (full model vs MBFC):      {rho_full:.4f}")
    print(f"    Spearman ρ (no-D4 model vs MBFC):     {rho:.4f}")
    print(f"    Δρ (D4 inclusion impact):             {rho_full - rho:+.4f}")

    # ── Verdict ──────────────────────────────────────────────────────────
    print("\n  VERDICT:")
    if rho >= 0.85:
        print(f"  ✓ ρ = {rho:.4} — MBFC strongly validates the no-D4 model")
    elif rho >= 0.70:
        print(f"  ~ ρ = {rho:.4f} — MBFC moderately validates the no-D4 model")
    elif rho >= 0.50:
        print(f"  ⚠ ρ = {rho:.4} — MBFC weakly validates the no-D4 model")
    else:
        print(f"  ✗ ρ = {rho:.4} — MBFC does not validate the no-D4 model")

    # ── Write machine-readable output ────────────────────────────────────
    import json as _json
    import math as _math
    from pathlib import Path as _Path

    # Fisher z-transform 95% CI for Spearman rho
    _z = _math.atanh(rho)
    _se = 1.0 / _math.sqrt(n_total - 3)
    _rho_ci_lo = round(_math.tanh(_z - 1.96 * _se), 3)
    _rho_ci_hi = round(_math.tanh(_z + 1.96 * _se), 3)
    print(f"  Fisher z 95% CI for ρ = {rho:.4f} (n={n_total}): [{_rho_ci_lo:.3f}, {_rho_ci_hi:.3f}]")

    out = {
        "no_d4_vs_mbfc_rho": round(rho, 4),
        "no_d4_vs_mbfc_rho_ci_95": [_rho_ci_lo, _rho_ci_hi],
        "full_vs_mbfc_rho": round(rho_full, 4),
        "n_outlets": n_total,
        "exact_match": agree_count,
        "adjacent": adj_count,
        "distant": diff_count,
        "outlet_scores": [
            {"outlet": r["name"], "no_d4_score": round(r["model_score"], 4),
             "no_d4_label": r["model_label"], "mbfc_label": r["mbfc_label_canon_full"]}
            for r in rows
        ],
    }
    out_path = _Path(__file__).parent.parent / "results" / "mbfc_validation.json"
    with open(out_path, "w") as _f:
        _json.dump(out, _f, indent=2)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
