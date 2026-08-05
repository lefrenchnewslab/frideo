"""
Family-Contribution Share Decomposition — FrIdéo V2 Scoring Pipeline
=====================================================================
Additive decomposition of each outlet's final ideology score into
signed and absolute contributions from each evidence family (D0–D8)
and the structural prior.

Math
----
From analysis_v2.py, the blended latent score is:

    z_blended_i = alpha_i * z_direct_i + (1 - alpha_i) * z_struct_i
    alpha_i = n_i / (n_i + lambda)
    z_direct_i = (1/n_i) * sum_k(z_ik)   [equal-weight mean of available families]

Expanding:
    z_blended_i = sum_k [ (alpha_i/n_i) * z_ik ] + (1-alpha_i) * z_struct_i

So the blended contribution from family k is:
    C_ik^blend = (alpha_i / n_i) * z_ik

And from the structural prior:
    C_iS^blend = (1 - alpha_i) * z_struct_i

Sanity: sum_k C_ik^blend + C_iS^blend = z_blended_i  ✓

After rescaling to the final z-standardized scale (scale_factor = 1/std_B):
    C_ik^final = C_ik^blend * scale_factor
    C_iS^final = C_iS^blend * scale_factor

Note: sum C^final = z_blended_i / std_B = final_i + mean_B/std_B (≠ final_i unless mean_B=0).
The centering offset mean_B is a constant baseline common to all outlets; it does not
change relative family shares. Shares are therefore computed on the blended (pre-centering)
scale to avoid the baseline ambiguity.

Share definitions:
    abs_share_ik = |C_ik^blend| / (|C_iS^blend| + sum_k |C_jk^blend|)
    signed_share_ik = C_ik^blend / (|C_iS^blend| + sum_k |C_jk^blend|)

Outputs
-------
  results/family_contribution_shares.csv   — one row per outlet (wide format)
  results/family_shares_long.csv           — one row per outlet × component (long format)
  stdout                                   — formatted text table

Usage
-----
    python3 scripts/compute_family_shares.py     # from the replication/ directory
"""

import sys
import csv
from pathlib import Path

# Import analysis_v2 from the replication/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    DIRECT_FAMILIES,
    SHRINKAGE_LAMBDA,
    RESULTS_DIR,
)


# ── core decomposition ─────────────────────────────────────────────────────────

def decompose_contributions(outlets, z_matrix, latent, scale_factor,
                             shrinkage_lambda=SHRINKAGE_LAMBDA):
    """
    For each outlet, compute the additive contribution of each family and
    the structural prior to the blended latent score.

    Returns dict: {outlet_name: {family: contribution_blend, "prior": contribution_blend}}
    Contributions are on the blended (pre-centering) scale; multiply by scale_factor
    for the final SD-units scale.
    """
    decomp = {}
    for outlet in outlets:
        name = outlet["name"]
        lat = latent[name]
        n = lat["n_direct"]
        alpha = n / (n + shrinkage_lambda) if n > 0 else 0.0

        family_contribs = {}
        for fam in DIRECT_FAMILIES:
            z_val = z_matrix[fam].get(name)
            if z_val is not None and n > 0:
                family_contribs[fam] = (alpha / n) * z_val
            else:
                family_contribs[fam] = None  # family not available for this outlet

        prior_contrib = (1.0 - alpha) * lat["z_structural"]

        # Sanity: sum of available family contribs + prior_contrib ≈ z_blended
        total = prior_contrib + sum(v for v in family_contribs.values() if v is not None)
        expected = lat["z_blended"]
        if abs(total - expected) > 1e-6:
            print(f"  [WARN] {name}: sum={total:.6f}, z_blended={expected:.6f}, "
                  f"diff={total-expected:.2e}")

        decomp[name] = {
            "family_contribs_blend": family_contribs,   # {fam: float or None}
            "prior_contrib_blend": prior_contrib,
            "n_direct": n,
            "alpha": alpha,
            # Scaled to final SD units (ignoring constant centering offset)
            "family_contribs_final": {
                fam: v * scale_factor if v is not None else None
                for fam, v in family_contribs.items()
            },
            "prior_contrib_final": prior_contrib * scale_factor,
        }

    return decomp


def compute_shares(decomp):
    """
    Add abs_share and signed_share to each outlet's decomp entry.

    Share denominator = |prior_contrib| + sum_k |family_contrib_k|  (absolute mass).
    Missing families contribute 0 to the denominator (they do not exist for this outlet).
    """
    for name, d in decomp.items():
        fc = d["family_contribs_blend"]
        pc = d["prior_contrib_blend"]

        abs_mass = abs(pc) + sum(abs(v) for v in fc.values() if v is not None)

        abs_shares = {}
        signed_shares = {}
        for fam in DIRECT_FAMILIES:
            v = fc.get(fam)
            if v is not None and abs_mass > 1e-12:
                abs_shares[fam] = abs(v) / abs_mass
                signed_shares[fam] = v / abs_mass
            else:
                abs_shares[fam] = None
                signed_shares[fam] = None

        prior_abs_share = abs(pc) / abs_mass if abs_mass > 1e-12 else 0.0
        prior_signed_share = pc / abs_mass if abs_mass > 1e-12 else 0.0

        d["abs_shares"] = abs_shares
        d["signed_shares"] = signed_shares
        d["prior_abs_share"] = prior_abs_share
        d["prior_signed_share"] = prior_signed_share
        d["abs_mass"] = abs_mass

    return decomp


# ── output ─────────────────────────────────────────────────────────────────────

def print_share_table(outlets, decomp, scored, labels):
    print(f"\n{'='*110}")
    print("  EVIDENCE FAMILY CONTRIBUTION SHARES — per-outlet decomposition")
    print("  Interpretation: what fraction of this outlet's blended signal comes from each source?")
    print("  abs_share = |contribution_k| / total_abs_mass (bars below)")
    print(f"{'='*110}\n")

    # Group header
    fam_labels = {
        "D0": "Owner",  "D1": "Cagé",   "D2": "Pew",  "D3": "Cointet",
        "D4": "MBFC",   "D6a": "Self",  "D6b": "3rdParty",
        "D7": "Content", "D8": "AdFontes", "prior": "Prior",
    }

    for outlet in sorted(outlets, key=lambda o: scored[o["name"]]["final"]):
        name = outlet["name"]
        s = scored[name]
        d = decomp[name]
        final = s["final"]
        n = d["n_direct"]
        alpha = d["alpha"]
        lbl = labels.get(name, "?")

        print(f"  {name:<22}  score={final:+.3f}  label={lbl:<12}  n_direct={n}  alpha={alpha:.2f}")

        row_parts = []
        for fam in DIRECT_FAMILIES:
            v_blend = d["family_contribs_blend"].get(fam)
            v_final = d["family_contribs_final"].get(fam)
            share = d["abs_shares"].get(fam)
            if v_blend is None:
                row_parts.append(f"    {fam_labels[fam]:>8}({fam}): —")
            else:
                bar = "█" * int(round(share * 20)) if share is not None else ""
                row_parts.append(
                    f"    {fam_labels[fam]:>8}({fam}): {v_final:+.3f}SD  {share*100:5.1f}%  {bar}"
                )

        # Prior
        v_prior_final = d["prior_contrib_final"]
        pa_share = d["prior_abs_share"]
        bar = "█" * int(round(pa_share * 20))
        row_parts.append(
            f"    {'Prior':>8}(S2): {v_prior_final:+.3f}SD  {pa_share*100:5.1f}%  {bar}"
        )

        for part in row_parts:
            print(part)
        print()


def write_wide_csv(outlets, decomp, scored, labels):
    path = RESULTS_DIR / "family_contribution_shares.csv"

    fam_cols = DIRECT_FAMILIES + ["prior"]

    header = (
        ["outlet", "final_score", "label", "n_direct", "alpha", "z_blended", "abs_mass"]
        + [f"{f}_contrib_blend" for f in fam_cols]
        + [f"{f}_contrib_final" for f in fam_cols]
        + [f"{f}_abs_share" for f in fam_cols]
        + [f"{f}_signed_share" for f in fam_cols]
    )

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)

        for outlet in sorted(outlets, key=lambda o: scored[o["name"]]["final"]):
            name = outlet["name"]
            s = scored[name]
            d = decomp[name]

            def _r(v):
                return round(v, 6) if v is not None else ""

            blend_contribs = [
                _r(d["family_contribs_blend"].get(fam)) for fam in DIRECT_FAMILIES
            ] + [_r(d["prior_contrib_blend"])]

            final_contribs = [
                _r(d["family_contribs_final"].get(fam)) for fam in DIRECT_FAMILIES
            ] + [_r(d["prior_contrib_final"])]

            abs_shares = [
                _r(d["abs_shares"].get(fam)) for fam in DIRECT_FAMILIES
            ] + [_r(d["prior_abs_share"])]

            signed_shares = [
                _r(d["signed_shares"].get(fam)) for fam in DIRECT_FAMILIES
            ] + [_r(d["prior_signed_share"])]

            w.writerow([
                name,
                round(s["final"], 6),
                labels.get(name, ""),
                d["n_direct"],
                round(d["alpha"], 4),
                round(s["z_blended"], 6),
                round(d["abs_mass"], 6),
            ] + blend_contribs + final_contribs + abs_shares + signed_shares)

    return path


def write_long_csv(outlets, decomp, scored, labels):
    """Long format: one row per outlet × component (easier to filter/plot)."""
    path = RESULTS_DIR / "family_shares_long.csv"

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "outlet", "final_score", "label", "n_direct", "alpha",
            "component", "is_prior",
            "contrib_blend", "contrib_final",
            "abs_share", "signed_share",
        ])

        for outlet in sorted(outlets, key=lambda o: scored[o["name"]]["final"]):
            name = outlet["name"]
            s = scored[name]
            d = decomp[name]

            base_row = [
                name, round(s["final"], 6), labels.get(name, ""),
                d["n_direct"], round(d["alpha"], 4),
            ]

            for fam in DIRECT_FAMILIES:
                cb = d["family_contribs_blend"].get(fam)
                cf = d["family_contribs_final"].get(fam)
                ab = d["abs_shares"].get(fam)
                sg = d["signed_shares"].get(fam)
                w.writerow(base_row + [
                    fam, False,
                    round(cb, 6) if cb is not None else "",
                    round(cf, 6) if cf is not None else "",
                    round(ab, 6) if ab is not None else "",
                    round(sg, 6) if sg is not None else "",
                ])

            # Prior row
            w.writerow(base_row + [
                "prior", True,
                round(d["prior_contrib_blend"], 6),
                round(d["prior_contrib_final"], 6),
                round(d["prior_abs_share"], 6),
                round(d["prior_signed_share"], 6),
            ])

    return path


def plot_contribution_decomposition(outlets, decomp, scored, labels):
    """
    Two figures:

    Fig 1 — Diverging stacked bar chart (one row per outlet, sorted by final score).
      Negative contributions stack left, positive stack right.
      Each segment is one evidence family or the structural prior.
      The black tick marks the final score; the dashed line is 0 (sample mean).

    Fig 2 — Absolute-share heatmap.
      Rows = outlets (sorted by score), columns = families.
      Cell colour = share intensity; grey = family not available for that outlet.
      Annotated with the share percentage.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import matplotlib.colors as mcolors
        import numpy as np
    except ImportError:
        print("  (matplotlib/numpy not installed; skipping plots)")
        return

    plots_dir = RESULTS_DIR / "plots"
    plots_dir.mkdir(exist_ok=True)

    ALL_COMPONENTS = DIRECT_FAMILIES + ["prior"]
    COMPONENT_COLORS = {
        "D0":    "#E64A19",   # burnt orange — ownership
        "D1":    "#1565C0",   # dark blue — Cagé guest data
        "D2":    "#2E7D32",   # dark green — Pew survey
        "D3":    "#F57F17",   # amber — Cointet network
        "D4":    "#6A1B9A",   # purple — MBFC
        "D6a":   "#4E342E",   # brown — self-declared
        "D6b":   "#37474F",   # blue-grey — 3rd party
        "D7":    "#00695C",   # teal — content score
        "D8":    "#F06292",   # pink — Ad Fontes Media
        "prior": "#9E9E9E",   # neutral grey — structural prior
    }
    COMPONENT_LABELS = {
        "D0": "D0 Owner", "D1": "D1 Cagé", "D2": "D2 Pew",
        "D3": "D3 Cointet", "D4": "D4 MBFC",
        "D6a": "D6a Self", "D6b": "D6b 3rdParty",
        "D7": "D7 Content", "D8": "D8 AdFontes", "prior": "Prior (S2)",
    }
    LABEL_BAND_COLORS = {
        "far-left":     "#1a3a6b",
        "left":         "#1a6bb0",
        "center-left":  "#5b8db8",
        "center":       "#888888",
        "center-right": "#b87050",
        "right":        "#b01a1a",
        "far-right":    "#6b0000",
    }

    outlets_sorted = sorted(outlets, key=lambda o: scored[o["name"]]["final"])
    names = [o["name"] for o in outlets_sorted]
    n = len(names)
    y = np.arange(n)

    # ── Figure 1: Diverging stacked bar chart ──────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 11))

    for i, name in enumerate(names):
        d = decomp[name]
        s = scored[name]
        final = s["final"]

        # Split each component into its positive / negative signed contribution (final-scale)
        pos_left = 0.0   # cursor for stacking positive values (rightward)
        neg_left = 0.0   # cursor for stacking negative values (leftward)

        for comp in ALL_COMPONENTS:
            if comp == "prior":
                val = d["prior_contrib_final"]
            else:
                val = d["family_contribs_final"].get(comp)

            if val is None:
                continue

            color = COMPONENT_COLORS[comp]
            if val >= 0:
                ax.barh(i, val, left=pos_left, height=0.65,
                        color=color, alpha=0.85, linewidth=0)
                pos_left += val
            else:
                ax.barh(i, val, left=neg_left, height=0.65,
                        color=color, alpha=0.85, linewidth=0)
                neg_left += val

        # Final score tick
        ax.plot(final, i, "D", color="black", ms=5, zorder=6)

    # Label band background strips
    all_finals = [scored[n]["final"] for n in names]
    x_lo = min(all_finals) - 0.8
    x_hi = max(all_finals) + 0.8

    # y-axis labels with ideology colour
    ax.set_yticks(y)
    yticklabels = ax.set_yticklabels(names, fontsize=9)
    for tick, name in zip(yticklabels, names):
        lbl = labels.get(name, "center")
        tick.set_color(LABEL_BAND_COLORS.get(lbl, "#333"))

    ax.axvline(0, color="#333", lw=1.0, ls="--", zorder=2, alpha=0.6)
    ax.set_xlabel("Contribution to ideology score (SD units, mean=0)", fontsize=10)
    ax.set_title(
        "Evidence-Family Contribution Decomposition — V2 Ideology Scores\n"
        "Each segment = one family's signed additive contribution; ◆ = final score",
        fontsize=11,
    )
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(-0.6, n - 0.4)

    legend_handles = [
        mpatches.Patch(facecolor=COMPONENT_COLORS[c], label=COMPONENT_LABELS[c], alpha=0.85)
        for c in ALL_COMPONENTS
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8,
              ncol=2, framealpha=0.9)

    # Light grid
    ax.xaxis.grid(True, color="#ddd", lw=0.6, zorder=0)
    ax.set_axisbelow(True)

    plt.tight_layout()
    p1 = plots_dir / "family_contributions_diverging.png"
    fig.savefig(p1, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {p1}")

    # ── Figure 2: Absolute-share heatmap ──────────────────────────────────────
    # Build matrix: rows=outlets (sorted by score), cols=ALL_COMPONENTS
    share_matrix = np.full((n, len(ALL_COMPONENTS)), np.nan)
    for i, name in enumerate(names):
        d = decomp[name]
        for j, comp in enumerate(ALL_COMPONENTS):
            if comp == "prior":
                share_matrix[i, j] = d["prior_abs_share"]
            else:
                v = d["abs_shares"].get(comp)
                if v is not None:
                    share_matrix[i, j] = v

    fig2, ax2 = plt.subplots(figsize=(13, 10))

    # Grey background for NA cells
    ax2.set_facecolor("#eeeeee")

    # Draw colored cells
    cmap_base = plt.cm.YlOrRd
    for i in range(n):
        for j, comp in enumerate(ALL_COMPONENTS):
            val = share_matrix[i, j]
            if np.isnan(val):
                color = "#d8d8d8"
                text = "—"
                text_color = "#aaa"
            else:
                # Normalize share to [0,1] for colour intensity (cap at 60%)
                intensity = min(val / 0.60, 1.0)
                rgba = cmap_base(0.15 + 0.85 * intensity)
                color = mcolors.to_hex(rgba)
                text = f"{val*100:.0f}%"
                text_color = "white" if intensity > 0.55 else "#333"

            rect = plt.Rectangle((j, i), 1, 1, color=color)
            ax2.add_patch(rect)
            ax2.text(j + 0.5, i + 0.5, text,
                     ha="center", va="center", fontsize=8,
                     color=text_color, fontweight="bold")

    col_labels = [COMPONENT_LABELS[c] for c in ALL_COMPONENTS]
    ax2.set_xticks([j + 0.5 for j in range(len(ALL_COMPONENTS))])
    ax2.set_xticklabels(col_labels, rotation=35, ha="right", fontsize=9)

    ax2.set_yticks([i + 0.5 for i in range(n)])
    yticklabels2 = ax2.set_yticklabels(names, fontsize=9)
    for tick, name in zip(yticklabels2, names):
        lbl = labels.get(name, "center")
        tick.set_color(LABEL_BAND_COLORS.get(lbl, "#333"))

    ax2.set_xlim(0, len(ALL_COMPONENTS))
    ax2.set_ylim(0, n)

    ax2.set_title(
        "Absolute Evidence-Share per Outlet — what fraction of signal comes from each source?\n"
        "(grey = family not available; colour intensity ∝ share; rows sorted left→right)",
        fontsize=11,
    )

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap_base,
                                norm=mcolors.Normalize(vmin=0, vmax=60))
    sm.set_array([])
    cbar = fig2.colorbar(sm, ax=ax2, fraction=0.025, pad=0.02)
    cbar.set_label("Absolute share (%)", fontsize=9)
    cbar.set_ticks([0, 20, 40, 60])
    cbar.set_ticklabels(["0%", "20%", "40%", "≥60%"])

    plt.tight_layout()
    p2 = plots_dir / "family_shares_heatmap.png"
    fig2.savefig(p2, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {p2}")

    # ── Figure 3: Panel-level mean absolute share (bar chart) ─────────────────
    panel_means = {}
    panel_n = {}
    for comp in ALL_COMPONENTS:
        if comp == "prior":
            vals = [d["prior_abs_share"] for d in decomp.values()]
        else:
            vals = [d["abs_shares"].get(comp) for d in decomp.values()
                    if d["abs_shares"].get(comp) is not None]
        panel_means[comp] = sum(vals) / len(vals) if vals else 0.0
        panel_n[comp] = len(vals)

    comps_sorted = sorted(ALL_COMPONENTS, key=lambda c: -panel_means[c])
    fig3, ax3 = plt.subplots(figsize=(9, 5))

    x_pos = np.arange(len(comps_sorted))
    bar_vals = [panel_means[c] * 100 for c in comps_sorted]
    bar_colors = [COMPONENT_COLORS[c] for c in comps_sorted]
    bars = ax3.bar(x_pos, bar_vals, color=bar_colors, alpha=0.85, width=0.6)

    for bar, comp, val in zip(bars, comps_sorted, bar_vals):
        n_outs = panel_n[comp]
        ax3.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.5,
                 f"{val:.1f}%\n(n={n_outs})",
                 ha="center", va="bottom", fontsize=8, color="#333")

    ax3.set_xticks(x_pos)
    ax3.set_xticklabels([COMPONENT_LABELS[c] for c in comps_sorted],
                        rotation=30, ha="right", fontsize=9)
    ax3.set_ylabel("Mean absolute share across outlets (%)", fontsize=10)
    ax3.set_title(
        "Panel-Level Family Importance\n"
        "Mean |contribution| / total_abs_mass, averaged over outlets where family is available",
        fontsize=11,
    )
    ax3.yaxis.grid(True, color="#ddd", lw=0.6)
    ax3.set_axisbelow(True)
    ax3.set_ylim(0, max(bar_vals) * 1.25)

    plt.tight_layout()
    p3 = plots_dir / "family_panel_importance.png"
    fig3.savefig(p3, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {p3}")


def plot_grouped_contributions(outlets, decomp, scored, labels):
    """
    Appendix figure: grouped diverging stacked bar.

    Families are collapsed into five interpretable groups:
      Ownership       — D0
      Academic/network — D1, D2, D3
      Ratings         — D4, D8
      Editorial/content — D6a, D6b, D7
      Tradition prior — S2

    Each bar segment is the sum of signed final-scale contributions within
    the group. The diamond marks the final score; label text colours track
    ideology category. Clean 5-colour palette for paper readability.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np
    except ImportError:
        print("  (matplotlib/numpy not installed; skipping grouped plot)")
        return

    plots_dir = RESULTS_DIR / "plots"
    plots_dir.mkdir(exist_ok=True)

    GROUPS = {
        "Ownership":          (["D0"],               "#E64A19"),  # orange-red
        "Academic & network": (["D1", "D2", "D3"], "#1565C0"),  # blue
        "Ratings":            (["D4", "D8"],          "#6A1B9A"),  # purple
        "Editorial & content":(["D6a", "D6b", "D7"],"#00695C"),  # teal
        "Tradition prior":    (["prior"],             "#9E9E9E"),  # grey
    }
    GROUP_ORDER = list(GROUPS.keys())

    LABEL_BAND_COLORS = {
        "far-left":     "#1a3a6b",
        "left":         "#1a6bb0",
        "center-left":  "#5b8db8",
        "center":       "#555555",
        "center-right": "#b87050",
        "right":        "#b01a1a",
        "far-right":    "#6b0000",
    }

    outlets_sorted = sorted(outlets, key=lambda o: scored[o["name"]]["final"])
    names = [o["name"] for o in outlets_sorted]
    n = len(names)

    # Build grouped signed contributions (final scale) for each outlet
    group_contribs = {g: [] for g in GROUP_ORDER}
    for name in names:
        d = decomp[name]
        for g in GROUP_ORDER:
            members, _ = GROUPS[g]
            total = 0.0
            for comp in members:
                if comp == "prior":
                    total += d["prior_contrib_final"]
                else:
                    v = d["family_contribs_final"].get(comp)
                    if v is not None:
                        total += v
            group_contribs[g].append(total)

    fig, ax = plt.subplots(figsize=(12, 10))
    y = np.arange(n)

    for i, name in enumerate(names):
        pos_cursor = 0.0
        neg_cursor = 0.0
        for g in GROUP_ORDER:
            val = group_contribs[g][i]
            _, color = GROUPS[g]
            if val == 0.0:
                continue
            if val > 0:
                ax.barh(i, val, left=pos_cursor, height=0.68,
                        color=color, alpha=0.88, linewidth=0)
                pos_cursor += val
            else:
                ax.barh(i, val, left=neg_cursor, height=0.68,
                        color=color, alpha=0.88, linewidth=0)
                neg_cursor += val

        # Final score diamond
        ax.plot(scored[name]["final"], i, "D", color="black", ms=5, zorder=6)

    # y-axis labels coloured by ideology
    ax.set_yticks(y)
    ticks = ax.set_yticklabels(names, fontsize=9)
    for tick, name in zip(ticks, names):
        tick.set_color(LABEL_BAND_COLORS.get(labels.get(name, "center"), "#333"))

    ax.axvline(0, color="#444", lw=1.0, ls="--", zorder=2, alpha=0.55)
    ax.xaxis.grid(True, color="#e0e0e0", lw=0.6, zorder=0)
    ax.set_axisbelow(True)

    all_finals = [scored[n]["final"] for n in names]
    ax.set_xlim(min(all_finals) - 0.7, max(all_finals) + 0.7)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlabel("Normalized additive contribution to ideology score (SD units, mean = 0)",
                  fontsize=10)
    ax.set_title(
        "Normalized Additive Contribution Shares by Evidence Group — FrIdéo V2\n"
        "Segments = signed group contributions; ◆ = final score; "
        "outlet labels colour-coded by ideology",
        fontsize=11,
    )

    legend_handles = [
        mpatches.Patch(facecolor=GROUPS[g][1], label=g, alpha=0.88)
        for g in GROUP_ORDER
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=9,
              framealpha=0.92)

    plt.tight_layout()
    out = plots_dir / "family_contributions_grouped.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")
    return out


def print_cross_outlet_summary(decomp, scored, labels):
    """
    For each evidence family, what share of total signal does it contribute
    across all outlets (aggregated over the panel)?
    """
    print(f"\n{'='*80}")
    print("  PANEL-LEVEL FAMILY IMPORTANCE")
    print("  Mean absolute contribution share across all outlets")
    print(f"{'='*80}")

    fam_mean_shares = {}
    for fam in DIRECT_FAMILIES:
        shares = [
            d["abs_shares"].get(fam)
            for d in decomp.values()
            if d["abs_shares"].get(fam) is not None
        ]
        fam_mean_shares[fam] = (sum(shares) / len(shares), len(shares)) if shares else (0.0, 0)

    prior_shares = [d["prior_abs_share"] for d in decomp.values()]
    fam_mean_shares["prior"] = (
        sum(prior_shares) / len(prior_shares) if prior_shares else 0.0,
        len(prior_shares),
    )

    all_components = DIRECT_FAMILIES + ["prior"]
    for comp in sorted(all_components, key=lambda c: -fam_mean_shares[c][0]):
        mean_sh, n_outlets = fam_mean_shares[comp]
        bar = "█" * int(round(mean_sh * 30))
        print(f"  {comp:<8}: {mean_sh*100:5.1f}%  (n={n_outlets} outlets)  {bar}")


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading V2 data and running scoring pipeline...")
    data = load_v2_data()
    outlets = data["outlets"]
    print(f"  {len(outlets)} outlets loaded.")

    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)

    z_matrix = build_standardized_matrix(outlets)
    latent = compute_latent_scores(outlets, z_matrix)
    scored, mean_z, std_z, scale_factor = standardize_final(latent)
    cutoffs, labels, _ = compute_labels(scored)

    print(f"  Pipeline complete: mean_z={mean_z:+.4f}, std_z={std_z:.4f}, "
          f"scale_factor={scale_factor:.4f}")

    print("\nDecomposing family contributions...")
    decomp = decompose_contributions(outlets, z_matrix, latent, scale_factor)
    decomp = compute_shares(decomp)
    print("  Decomposition complete.")

    # Print human-readable output
    print_share_table(outlets, decomp, scored, labels)
    print_cross_outlet_summary(decomp, scored, labels)

    # Write CSVs
    wide_path = write_wide_csv(outlets, decomp, scored, labels)
    long_path = write_long_csv(outlets, decomp, scored, labels)
    print(f"\n  Saved wide CSV:  {wide_path}")
    print(f"  Saved long CSV:  {long_path}")

    print("\nGenerating plots...")
    plot_contribution_decomposition(outlets, decomp, scored, labels)
    plot_grouped_contributions(outlets, decomp, scored, labels)
    print("\n  Done.")


if __name__ == "__main__":
    main()
