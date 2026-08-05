"""
λ (shrinkage) sensitivity (§5.3).

Recomputes every outlet's score and KDE label at λ = 1 and λ = 3 against the
λ = 2 baseline, reporting per-outlet scores, label changes, and the maximum
absolute score shift. Rank correlation alone (ρ = 0.996 across λ ∈ [1, 3]) can
stay high while a sparse outlet crosses a label boundary, so labels are checked
directly.

Correctness gate: λ = 2 must reproduce the canonical 11/8/11 label distribution
(pipeline_check Part A). If it does not, this script is off the canonical path
and the comparison is invalid.

Output: results/lambda_sensitivity.csv + results/lambda_sensitivity.json + console.
"""

import csv
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from analysis_v2 import (
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

RESULTS_DIR = BASE / "results"

LAMBDA_BASELINE = 2.0
LAMBDAS = [1.0, 2.0, 3.0]
EXPECTED_BASELINE_DIST = (11, 8, 11)  # (left, center, right) — pipeline_check Part A

LEFT = ("far-left", "left", "center-left")
RIGHT = ("center-right", "right", "far-right")


def label_distribution(labels: dict) -> tuple:
    nl = sum(1 for v in labels.values() if v in LEFT)
    nc = sum(1 for v in labels.values() if v == "center")
    nr = sum(1 for v in labels.values() if v in RIGHT)
    return nl, nc, nr


def score_at_lambda(outlets, z_matrix, lam):
    latent = compute_latent_scores(outlets, z_matrix, shrinkage_lambda=lam)
    scored, _, _, _ = standardize_final(latent)
    _, labels, _ = compute_labels(scored)
    finals = {name: scored[name]["final"] for name in scored}
    return finals, labels


def main():
    outlets = load_v2_data()["outlets"]
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)
    z_matrix = build_standardized_matrix(outlets)

    by_lambda = {lam: score_at_lambda(outlets, z_matrix, lam) for lam in LAMBDAS}
    base_finals, base_labels = by_lambda[LAMBDA_BASELINE]

    # ── correctness gate ─────────────────────────────────────────────────────
    base_dist = label_distribution(base_labels)
    if base_dist != EXPECTED_BASELINE_DIST:
        print(f"FAIL: λ=2 distribution {base_dist} != canonical {EXPECTED_BASELINE_DIST}; "
              f"off canonical path, aborting.")
        sys.exit(1)

    names_sorted = sorted(base_finals, key=lambda n: base_finals[n])
    order = names_sorted  # rank reference for spearman

    summary = {
        "lambda_baseline": LAMBDA_BASELINE,
        "lambdas_tested": [l for l in LAMBDAS if l != LAMBDA_BASELINE],
        "label_distribution": {f"{l:g}": list(label_distribution(by_lambda[l][1])) for l in LAMBDAS},
        "n_label_changes": {},
        "label_changes": {},
        "max_abs_shift": {},
        "argmax_shift_outlet": {},
        "spearman_rho_vs_baseline": {},
    }

    rows = []
    for name in names_sorted:
        row = {"outlet": name, "label_lambda2": base_labels[name],
               "score_lambda2": round(base_finals[name], 4)}
        for lam in LAMBDAS:
            if lam == LAMBDA_BASELINE:
                continue
            f_l, l_l = by_lambda[lam]
            tag = f"{lam:g}"
            row[f"score_lambda{tag}"] = round(f_l[name], 4)
            row[f"label_lambda{tag}"] = l_l[name]
            row[f"shift_vs_lambda2_{tag}"] = round(f_l[name] - base_finals[name], 4)
            row[f"label_changed_{tag}"] = (l_l[name] != base_labels[name])
        rows.append(row)

    for lam in LAMBDAS:
        if lam == LAMBDA_BASELINE:
            continue
        tag = f"{lam:g}"
        f_l, l_l = by_lambda[lam]
        changes = [{"outlet": n, "from": base_labels[n], "to": l_l[n]}
                   for n in names_sorted if l_l[n] != base_labels[n]]
        shifts = {n: abs(f_l[n] - base_finals[n]) for n in names_sorted}
        argmax = max(shifts, key=shifts.get)
        rho = spearman_rho([base_finals[n] for n in order], [f_l[n] for n in order])
        summary["n_label_changes"][tag] = len(changes)
        summary["label_changes"][tag] = changes
        summary["max_abs_shift"][tag] = round(shifts[argmax], 4)
        summary["argmax_shift_outlet"][tag] = argmax
        summary["spearman_rho_vs_baseline"][tag] = round(rho, 4)

    # ── write CSV + JSON ─────────────────────────────────────────────────────
    out_csv = RESULTS_DIR / "lambda_sensitivity.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    out_json = RESULTS_DIR / "lambda_sensitivity.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)

    # ── console summary ──────────────────────────────────────────────────────
    print("=" * 72)
    print("λ (SHRINKAGE) SENSITIVITY (§5.3)")
    print(f"Baseline λ = {LAMBDA_BASELINE} (canonical); testing λ = "
          f"{summary['lambdas_tested']}")
    print("=" * 72)
    print(f"λ=2 label distribution (gate): {base_dist}  == {EXPECTED_BASELINE_DIST} ✓")
    for lam in summary["lambdas_tested"]:
        tag = f"{lam:g}"
        print(f"\n── λ = {tag} vs λ = 2 ──")
        print(f"  Spearman ρ:        {summary['spearman_rho_vs_baseline'][tag]:.4f}")
        print(f"  Max |Δ score|:     {summary['max_abs_shift'][tag]:.4f}σ "
              f"({summary['argmax_shift_outlet'][tag]})")
        print(f"  Label distribution: {tuple(summary['label_distribution'][tag])}")
        print(f"  Label changes:      {summary['n_label_changes'][tag]}")
        for c in summary["label_changes"][tag]:
            print(f"     {c['outlet']}: {c['from']} → {c['to']}")
        if summary["n_label_changes"][tag] == 0:
            print("     None — no outlet crosses a label boundary.")
    print(f"\nSaved: {out_csv}")
    print(f"Saved: {out_json}")


if __name__ == "__main__":
    main()
