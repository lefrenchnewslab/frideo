#!/usr/bin/env python3
"""No-prior refit (paper Appendix E).

The face-validity check in §4.3 — "all 30 assignments match established
characterizations in the literature" — is partly circular for the sparse outlets
whose S2 prior encodes the same historical characterization the label is being
checked against. This refits the whole panel with the prior removed
(alpha_i = 1 for every outlet, then re-standardized) and reports what changes.

If the sparse outlets' labels survive the prior's removal, the agreement was not
manufactured by the prior.

Writes results/no_prior_refit.json. Run: python3 scripts/no_prior_refit.py
"""
import json
import sys
from pathlib import Path

# This script imports analysis_v2 directly, so it can leave a __pycache__ in a
# shipped copy when run outside `make` (the Makefile sets PYTHONDONTWRITEBYTECODE
# for that reason). Guard the standalone path too.
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import analysis_v2 as A  # noqa: E402

# Outlets whose label the reviewer flagged as potentially circular: sparse
# (n <= 4) AND carrying a non-zero founding-tradition prior.
PRIOR_DEPENDENT_SPARSE = ["Blast", "Le HuffPost", "Atlantico"]


def _panel():
    outlets = A.load_v2_data()["outlets"]
    A.inject_d0(outlets)
    A.inject_d3_ppr(outlets)
    A.inject_d7(outlets)
    A.inject_d8_af(outlets)
    return outlets, A.build_standardized_matrix(outlets)


def _fit(outlets, z_matrix, drop_prior):
    latent = A.compute_latent_scores(outlets, z_matrix)
    if drop_prior:
        # alpha_i = 1: the blended score is the direct evidence mean, full stop.
        latent = {k: {**v, "z_blended": v["z_direct"]} for k, v in latent.items()}
    scored, _, _, _ = A.standardize_final(latent)
    _cutoffs, labels, _kde = A.compute_labels(scored)
    return ({n: round(v["final"], 4) for n, v in scored.items()}, labels)


def main():
    outlets, z_matrix = _panel()
    base_scores, base_labels = _fit(outlets, z_matrix, drop_prior=False)
    np_scores, np_labels = _fit(outlets, z_matrix, drop_prior=True)

    changes = [
        {"outlet": n, "from": base_labels[n], "to": np_labels[n]}
        for n in base_labels
        if base_labels[n] != np_labels[n]
    ]
    sparse = {
        n: {
            "full": base_scores[n],
            "no_prior": np_scores[n],
            "label_full": base_labels[n],
            "label_no_prior": np_labels[n],
            "label_held": base_labels[n] == np_labels[n],
        }
        for n in PRIOR_DEPENDENT_SPARSE
    }
    out = {
        "description": "Refit with alpha_i = 1 (structural prior removed), then "
                       "re-standardized across the same 30 outlets.",
        "prior_dependent_sparse": sparse,
        "all_prior_dependent_sparse_labels_held": all(
            v["label_held"] for v in sparse.values()
        ),
        "n_label_changes": len(changes),
        "label_changes": changes,
        "max_abs_shift": round(
            max(abs(np_scores[n] - base_scores[n]) for n in base_scores), 4
        ),
        "scores": {
            n: {"full": base_scores[n], "no_prior": np_scores[n]}
            for n in sorted(base_scores, key=base_scores.get)
        },
    }

    path = ROOT / "results" / "no_prior_refit.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")

    print("\n  No-prior refit (Appendix E)\n")
    for n, v in sparse.items():
        held = "label held" if v["label_held"] else "LABEL CHANGED"
        print(f"    {n:<14s} {v['full']:+.4f} -> {v['no_prior']:+.4f}   "
              f"{v['label_full']} -> {v['label_no_prior']}   ({held})")
    print(f"\n    panel-wide label changes: {len(changes)}")
    for c in changes:
        print(f"      {c['outlet']}: {c['from']} -> {c['to']}")
    print(f"\n  Saved: {path}\n")


if __name__ == "__main__":
    main()
