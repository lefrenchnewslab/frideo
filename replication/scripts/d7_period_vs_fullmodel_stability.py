"""
Compare D7's own period-to-period stability with the full model's, when only
D7 varies across periods.

  1. Load per-outlet D7 scores for 2024 and 2025 from d7_period_stability.csv
  2. Run the full pipeline twice, injecting each period's D7 in turn
  3. Spearman ρ between the two runs shows how much of D7's period variance
     the fusion absorbs

Output: results/d7_period_vs_fullmodel.csv  +  console summary
"""

import csv
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from analysis_v2 import (
    inject_d0,
    inject_d3_ppr,
    inject_d7,
    inject_d8_af,
    build_standardized_matrix,
    compute_latent_scores,
    standardize_final,
    spearman_rho,
)

RESULTS_DIR = BASE / "results"
PERIOD_STABILITY_CSV = RESULTS_DIR / "d7_period_stability.csv"


def load_period_d7() -> tuple:
    """Returns ({outlet: d7_2024}, {outlet: d7_2025}) from the CSV."""
    d7_2024, d7_2025 = {}, {}
    with open(PERIOD_STABILITY_CSV) as f:
        for row in csv.DictReader(f):
            name = row["outlet"]
            try:
                d7_2024[name] = float(row["d7_2024"])
            except (ValueError, KeyError):
                pass
            try:
                d7_2025[name] = float(row["d7_2025"])
            except (ValueError, KeyError):
                pass
    return d7_2024, d7_2025


def inject_d7_period(outlets: list, d7_map: dict) -> None:
    """Overwrite each outlet's D7 direct value with the supplied period score."""
    for o in outlets:
        name = o["name"]
        o["direct"]["D7"] = d7_map.get(name)  # None if not in period data


def run_full_model(outlets: list, d7_map: dict) -> dict:
    """Inject period D7, run full pipeline, return {outlet: final_score}."""
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)           # baseline D7 from combined CSV
    inject_d8_af(outlets)
    inject_d7_period(outlets, d7_map)  # override with period-specific values
    z_matrix = build_standardized_matrix(outlets)
    latent = compute_latent_scores(outlets, z_matrix)
    scored, _, _, _ = standardize_final(latent)
    return {name: scored[name]["final"] for name in scored}


def main():
    d7_2024, d7_2025 = load_period_d7()

    # We need two independent copies of the outlet list because inject mutates in place
    import json, copy
    from analysis_v2 import DATA_FILE
    with open(DATA_FILE) as f:
        raw = json.load(f)["outlets"]

    outlets_2024 = copy.deepcopy(raw)
    outlets_2025 = copy.deepcopy(raw)

    scores_2024 = run_full_model(outlets_2024, d7_2024)
    scores_2025 = run_full_model(outlets_2025, d7_2025)

    # Common outlets in both periods
    common = sorted(set(scores_2024) & set(scores_2025))

    rho_full_model = spearman_rho(
        [scores_2024[n] for n in common],
        [scores_2025[n] for n in common],
    )

    # D7-alone ρ — computed from d7_period_stability.csv, not hardcoded
    with open(PERIOD_STABILITY_CSV) as _f:
        _period_rows = list(csv.DictReader(_f))
    d7_pairs = [
        (float(r["d7_2024"]), float(r["d7_2025"]))
        for r in _period_rows
        if r.get("d7_2024") and r.get("d7_2025")
    ]
    d7_n = len(d7_pairs)
    d7_rho = spearman_rho([p[0] for p in d7_pairs], [p[1] for p in d7_pairs])

    # Per-outlet shifts
    rows = []
    for name in common:
        v2024 = d7_2024.get(name)
        v2025 = d7_2025.get(name)
        d7_delta = (v2025 - v2024) if (v2024 is not None and v2025 is not None) else None
        full_delta = scores_2025[name] - scores_2024[name]
        rows.append({
            "outlet": name,
            "d7_2024": round(v2024, 4) if v2024 is not None else "",
            "d7_2025": round(v2025, 4) if v2025 is not None else "",
            "d7_delta": round(d7_delta, 4) if d7_delta is not None else "",
            "full_score_2024": round(scores_2024[name], 4),
            "full_score_2025": round(scores_2025[name], 4),
            "full_delta": round(full_delta, 4),
            "d7_abs_delta": round(abs(d7_delta), 4) if d7_delta is not None else "",
            "full_abs_delta": round(abs(full_delta), 4),
        })

    # Sort by |D7 delta| descending
    rows.sort(key=lambda r: abs(float(r["d7_delta"])) if r["d7_delta"] != "" else 0, reverse=True)

    # ── write CSV ──────────────────────────────────────────────────────────────
    out_path = RESULTS_DIR / "d7_period_vs_fullmodel.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ── console summary ────────────────────────────────────────────────────────
    print("=" * 80)
    print("D7 PERIOD STABILITY vs FULL-MODEL STABILITY")
    print("=" * 80)
    print(f"\n  D7-alone rank correlation  (2024 vs 2025, n={d7_n}): ρ = {d7_rho:.4f}")
    print(f"  Full-model rank correlation (D7 period swap, n={len(common)}):  ρ = {rho_full_model:.4f}")

    full_abs_deltas = [abs(float(r["full_abs_delta"])) for r in rows]
    d7_abs_deltas   = [abs(float(r["d7_abs_delta"])) for r in rows if r["d7_abs_delta"] != ""]
    print(f"\n  Full-model max score shift:  {max(full_abs_deltas):.4f}σ")
    print(f"  Full-model mean score shift: {sum(full_abs_deltas)/len(full_abs_deltas):.4f}σ")
    print(f"  D7-alone max |delta|:        {max(d7_abs_deltas):.4f}")
    print(f"  D7-alone mean |delta|:       {sum(d7_abs_deltas)/len(d7_abs_deltas):.4f}")

    print(f"\n{'Outlet':<22} {'D7_2024':>8} {'D7_2025':>8} {'D7_Δ':>7} "
          f"{'Full_2024':>10} {'Full_2025':>10} {'Full_Δ':>8}")
    print("-" * 75)
    for r in rows:
        print(f"{r['outlet']:<22} {r['d7_2024']:>8} {r['d7_2025']:>8} {r['d7_delta']:>7} "
              f"{r['full_score_2024']:>10} {r['full_score_2025']:>10} {r['full_delta']:>8}")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
