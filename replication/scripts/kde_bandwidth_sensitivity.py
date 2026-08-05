"""
KDE bandwidth sensitivity analysis.

The main model assigns interpretive labels via KDE valley detection at
h = 1.5 × Silverman's rule-of-thumb.  This script re-runs the label
assignment at five multipliers (1.0 to 2.0 × Silverman) to determine
which outlet labels — if any — are bandwidth-sensitive.

Scores are fixed (bandwidth does not affect the continuous scores, only
the cut-points).  Only the KDE label step is swept.

Output
------
  results/kde_bandwidth_sensitivity.csv   per-outlet label at each multiplier
  results/kde_bandwidth_sensitivity.json  summary (boundary outlets, stable count)
  console summary

Usage
-----
  python scripts/kde_bandwidth_sensitivity.py
"""

import csv
import json
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from analysis_v2 import (
    N_LABEL_CUTS,
    IDEOLOGY_LABELS,
    load_v2_data,
    inject_d0,
    inject_d3_ppr,
    inject_d7,
    inject_d8_af,
    build_standardized_matrix,
    compute_latent_scores,
    standardize_final,
    _kde_density,
    _find_valleys,
    _equal_sd_cutoffs,
    _try_gmm_cutoffs,
)

RESULTS_DIR = BASE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Bandwidth multipliers to test (relative to the 1.5× Silverman base).
# The base multiplier is 1.5, so these are expressed as absolute multipliers
# on the raw Silverman bandwidth (0.9 * std * n^-0.2).
RAW_SILVERMAN_MULT = 1.5          # what the main model uses
BW_MULTIPLIERS = [1.0, 1.25, 1.5, 1.75, 2.0]

N_GRID = 500


def labels_at_bandwidth(scored: dict, bw_mult: float, n_grid: int = N_GRID) -> tuple:
    """
    Run KDE label assignment at a specified absolute bandwidth multiplier
    (applied to raw Silverman: 0.9 * std * n^(-0.2)).

    Returns (cutoffs, assignments, bandwidth_used).
    """
    vals = [v["final"] for v in scored.values()]
    n = len(vals)
    std = statistics.pstdev(vals)
    bw = max(0.1, bw_mult * 0.9 * std * n ** (-0.2))

    x_min = min(vals) - max(1.0, 2 * bw)
    x_max = max(vals) + max(1.0, 2 * bw)
    step = (x_max - x_min) / (n_grid - 1)
    x_grid = [x_min + step * i for i in range(n_grid)]

    density = _kde_density(vals, x_grid, bw)
    order = max(10, n_grid // 20)
    valleys = _find_valleys(x_grid, density, order=order)

    if len(valleys) > N_LABEL_CUTS:
        valley_depths = []
        for v in valleys:
            idx = min(range(n_grid), key=lambda i: abs(x_grid[i] - v))
            valley_depths.append((v, density[idx]))
        valley_depths.sort(key=lambda x: x[1])
        valleys = sorted(v for v, _ in valley_depths[:N_LABEL_CUTS])
    elif len(valleys) < N_LABEL_CUTS:
        gmm_cuts = _try_gmm_cutoffs(vals, N_LABEL_CUTS + 1)
        if gmm_cuts is not None and len(gmm_cuts) >= N_LABEL_CUTS:
            valleys = sorted(gmm_cuts[:N_LABEL_CUTS])
        else:
            valleys = _equal_sd_cutoffs(vals, N_LABEL_CUTS)

    cutoffs = sorted(valleys)
    assignments = {}
    for name, v in scored.items():
        idx = sum(1 for cut in cutoffs if v["final"] > cut)
        assignments[name] = IDEOLOGY_LABELS[min(idx, len(IDEOLOGY_LABELS) - 1)]

    return cutoffs, assignments, bw


def main():
    # ── run pipeline once to get fixed final scores ───────────────────────────
    outlets = load_v2_data()["outlets"]
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)

    z_matrix = build_standardized_matrix(outlets)
    latent = compute_latent_scores(outlets, z_matrix)
    scored, _, _, _ = standardize_final(latent)

    outlet_names = sorted(scored.keys())

    # ── sweep bandwidth multipliers ───────────────────────────────────────────
    results = {}   # {outlet: {mult: label}}
    cutoffs_by_mult = {}

    for mult in BW_MULTIPLIERS:
        cutoffs, assignments, bw_used = labels_at_bandwidth(scored, mult)
        cutoffs_by_mult[mult] = {"cutoffs": [round(c, 4) for c in cutoffs], "bw": round(bw_used, 4)}
        for name in outlet_names:
            if name not in results:
                results[name] = {}
            results[name][mult] = assignments[name]

    # ── identify boundary-sensitive outlets ──────────────────────────────────
    baseline_label = {name: results[name][RAW_SILVERMAN_MULT] for name in outlet_names}
    boundary_outlets = []
    stable_outlets = []

    for name in outlet_names:
        labels_across = [results[name][m] for m in BW_MULTIPLIERS]
        unique_labels = set(labels_across)
        if len(unique_labels) > 1:
            boundary_outlets.append({
                "outlet": name,
                "baseline_label": baseline_label[name],
                "labels": {str(m): results[name][m] for m in BW_MULTIPLIERS},
                "variants": sorted(unique_labels),
            })
        else:
            stable_outlets.append(name)

    # ── console report ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  KDE BANDWIDTH SENSITIVITY ANALYSIS")
    print(f"  Multipliers tested: {BW_MULTIPLIERS}  (baseline = {RAW_SILVERMAN_MULT}×)")
    print("=" * 70)

    print(f"\n  Stable outlets ({len(stable_outlets)} / {len(outlet_names)}):")
    for name in stable_outlets:
        print(f"    {name:<24}  {baseline_label[name]}")

    print(f"\n  Bandwidth-sensitive outlets ({len(boundary_outlets)}):")
    if boundary_outlets:
        for bo in boundary_outlets:
            label_seq = "  |  ".join(
                f"{m}×: {bo['labels'][str(m)]}" for m in BW_MULTIPLIERS
            )
            print(f"    {bo['outlet']:<24}  {label_seq}")
    else:
        print("    (none — all labels stable across full range)")

    print("\n  Cut-points by multiplier:")
    print(f"  {'Mult':>6}  {'bw':>6}  {'Cut-points':}")
    for mult in BW_MULTIPLIERS:
        d = cutoffs_by_mult[mult]
        cuts_str = "  ".join(f"{c:+.3f}" for c in d["cutoffs"])
        marker = "  ← baseline" if mult == RAW_SILVERMAN_MULT else ""
        print(f"  {mult:>6.2f}  {d['bw']:>6.4f}  {cuts_str}{marker}")

    print()

    # ── write CSV ─────────────────────────────────────────────────────────────
    csv_path = RESULTS_DIR / "kde_bandwidth_sensitivity.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["outlet", "score"] + [f"label_bw{m}x" for m in BW_MULTIPLIERS] + ["stable"]
        writer.writerow(header)
        for name in outlet_names:
            score = round(scored[name]["final"], 4)
            labels_row = [results[name][m] for m in BW_MULTIPLIERS]
            is_stable = all(l == labels_row[0] for l in labels_row)
            writer.writerow([name, score] + labels_row + [is_stable])
    print(f"  CSV written: {csv_path}")

    # ── write JSON summary ────────────────────────────────────────────────────
    json_path = RESULTS_DIR / "kde_bandwidth_sensitivity.json"
    summary = {
        "multipliers_tested": BW_MULTIPLIERS,
        "baseline_multiplier": RAW_SILVERMAN_MULT,
        "n_outlets": len(outlet_names),
        "n_stable": len(stable_outlets),
        "n_boundary": len(boundary_outlets),
        "stable_outlets": stable_outlets,
        "boundary_outlets": boundary_outlets,
        "cutoffs_by_multiplier": {str(m): cutoffs_by_mult[m] for m in BW_MULTIPLIERS},
    }
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  JSON written: {json_path}")
    print()


if __name__ == "__main__":
    main()
