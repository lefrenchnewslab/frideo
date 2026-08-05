"""
Ablation: Run model WITHOUT D4 (MBFC), compare scores, ranks, and labels to full model.

If the no-D4 model barely shifts, D4 can be repurposed as a validation signal.

Usage:
  python scripts/ablate_mbfc.py
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


def main():
    print("Loading data...")
    data = load_v2_data()
    outlets = data["outlets"]
    print(f"Loaded {len(outlets)} outlets.")

    # Inject D0
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)

    # ── Full model ──────────────────────────────────────────────────────────
    print("\nRunning full model (all families)...")
    families_all = DIRECT_FAMILIES
    z_all = build_standardized_matrix(outlets, families=families_all)
    lat_all = compute_latent_scores(outlets, z_all, families=families_all)
    scored_all, _, _, _ = standardize_final(lat_all)
    cutoffs_all, labels_all, _ = compute_labels(scored_all)

    # ── No-D4 model ─────────────────────────────────────────────────────────
    print("Running no-D4 model (D4 excluded)...")
    families_no_d4 = [f for f in DIRECT_FAMILIES if f != "D4"]
    z_no_d4 = build_standardized_matrix(outlets, families=families_no_d4)
    lat_no_d4 = compute_latent_scores(outlets, z_no_d4, families=families_no_d4)
    scored_no_d4, _, _, _ = standardize_final(lat_no_d4)
    cutoffs_no_d4, labels_no_d4, _ = compute_labels(scored_no_d4)

    # ── Coverage ────────────────────────────────────────────────────────────
    n_d4 = sum(1 for o in outlets if o["direct"].get("D4") is not None)
    d4_outlets = [o["name"] for o in outlets if o["direct"].get("D4") is not None]
    print(f"\n  D4 (MBFC) coverage: {n_d4}/{len(outlets)} outlets")
    print(f"  D4 outlets: {', '.join(sorted(d4_outlets))}")

    # ── Comparison table ────────────────────────────────────────────────────
    names = sorted(outlets, key=lambda o: scored_all[o["name"]]["final"])

    # Compute ranks
    rank_all = {o["name"]: i+1 for i, o in enumerate(names)}
    names_no_d4_sorted = sorted(outlets, key=lambda o: scored_no_d4[o["name"]]["final"])
    rank_no_d4 = {o["name"]: i+1 for i, o in enumerate(names_no_d4_sorted)}

    print(f"\n{'='*120}")
    print("  ABLATION: FULL MODEL vs NO-D4 MODEL")
    print(f"{'='*120}")
    hdr = (f"  {'Outlet':<22} {'Full':>8} {'NoD4':>8} {'ΔScore':>8} "
           f"{'Rank Full':>9} {'Rank NoD4':>9} {'ΔRank':>6} {'Label Full':<12} {'Label NoD4':<12} {'Has D4':<6}")
    print(hdr)
    print(f"  {'-'*115}")

    for o in names:
        name = o["name"]
        fs = scored_all[name]["final"]
        nd4s = scored_no_d4[name]["final"]
        delta = fs - nd4s
        r_full = rank_all[name]
        r_no_d4 = rank_no_d4[name]
        r_delta = r_full - r_no_d4
        l_full = labels_all.get(name, "?")
        l_no_d4 = labels_no_d4.get(name, "?")
        has_d4 = "✓" if o["direct"].get("D4") is not None else "✗"
        print(f"  {name:<22} {fs:>+8.3f} {nd4s:>+8.3f} {delta:>+8.3f} "
              f"{r_full:>9} {r_no_d4:>9} {r_delta:>+6} {l_full:<12} {l_no_d4:<12} {has_d4:<6}")

    # ── Correlations ────────────────────────────────────────────────────────
    all_full = [scored_all[o["name"]]["final"] for o in names]
    all_no_d4 = [scored_no_d4[o["name"]]["final"] for o in names]
    rho = spearman_rho(all_full, all_no_d4)

    # Label shifts
    label_shifts = 0
    detail_shifts = []
    for o in names:
        name = o["name"]
        lf = labels_all.get(name, "?")
        ln = labels_no_d4.get(name, "?")
        if lf != ln:
            label_shifts += 1
            detail_shifts.append((name, ln, lf))

    print(f"\n{'='*120}")
    print("  SUMMARY")
    print(f"{'='*120}")
    print(f"  Spearman ρ (Full vs No-D4): {rho:.4f}")
    print(f"  Label shifts: {label_shifts}/{len(outlets)} outlets")
    for name, old, new in detail_shifts:
        print(f"    {name:<22} {old} → {new}")
    if not detail_shifts:
        print("    (none)")

    # Show D4-outlet-specific deltas
    print("\n  D4-outlet detail (outlets where MBFC label was used as input):")
    for o in names:
        name = o["name"]
        if o["direct"].get("D4") is not None:
            fs = scored_all[name]["final"]
            nd4s = scored_no_d4[name]["final"]
            delta = fs - nd4s
            d4_val = o["direct"]["D4"]
            d4_label = o.get("d4_mbfc", {}).get("label", "?")
            print(f"    {name:<22} Full={fs:+.3f} NoD4={nd4s:+.3f} Δ={delta:+.3f}  "
                  f"D4_raw={d4_val:+.1f} MBFC_label={d4_label}")

    # ── Verdict ─────────────────────────────────────────────────────────────
    print("\n  VERDICT:")
    if rho >= 0.99:
        print(f"  ✓ ρ = {rho:.4} — D4 is near-redundant as input")
    elif rho >= 0.98:
        print(f"  ~ ρ = {rho:.4f} — D4 contributes modestly")
    else:
        print(f"  ✗ ρ = {rho:.4} — D4 is load-bearing")

    if label_shifts == 0:
        print("  ✓ Zero label shifts — D4 removal doesn't change category assignments")
    else:
        print(f"  ⚠ {label_shifts} label shifts — D4 influences some category boundaries")

    # ── Max absolute score shift ─────────────────────────────────────────────
    max_shift = max(abs(scored_all[o["name"]]["final"] - scored_no_d4[o["name"]]["final"])
                    for o in names)
    max_shift_outlet = max(names,
                           key=lambda o: abs(scored_all[o["name"]]["final"] - scored_no_d4[o["name"]]["final"]))

    # ── Write machine-readable output ────────────────────────────────────────
    import json as _json
    from pathlib import Path as _Path
    out = {
        "full_vs_no_d4_rho": round(rho, 4),
        "label_shifts": label_shifts,
        "max_abs_shift": round(max_shift, 4),
        "max_shift_outlet": max_shift_outlet["name"],
        "outlet_deltas": [
            {"outlet": o["name"],
             "full_score": round(scored_all[o["name"]]["final"], 4),
             "no_d4_score": round(scored_no_d4[o["name"]]["final"], 4),
             "delta": round(scored_all[o["name"]]["final"] - scored_no_d4[o["name"]]["final"], 4)}
            for o in names
        ],
    }
    out_path = _Path(__file__).parent.parent / "results" / "d4_ablation.json"
    with open(out_path, "w") as _f:
        _json.dump(out, _f, indent=2)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
