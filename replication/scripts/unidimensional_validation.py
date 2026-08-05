"""
Unidimensionality Validation — Expanded PCA Analysis

Purpose:
  Test whether the left-right ideology space in FrIdéo is truly unidimensional,
  and whether a second dimension captures separate economic vs cultural axes
  (e.g. La Croix via Catholic conservatism vs Les Echos via economic liberalism).

Output:
  results/unidimensional_validation_report.md  — human-readable report
  results/plots/pca_scree.png                   — scree plot
  results/plots/pca_biplot.png                  — PC1 vs PC2 scatter with loadings
  Console summary for quick verification.
"""

import math
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from analysis_v2 import (
    load_v2_data,
    inject_d0,
    inject_d3_ppr,
    inject_d7,
    inject_d8_af,
    build_standardized_matrix,
    DIRECT_FAMILIES,
)

RESULTS = BASE / "results"
PLOTS_DIR = RESULTS / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

# ── Families for different analyses ──────────────────────────────────────────
# High-coverage families (n >= 10 pairwise overlap) for primary PCA
HIGH_COV = ["D0", "D3", "D4", "D6a", "D6b", "D7"]

# Ultra-high-coverage for complete-case PCA (n >= 21)
PCA_CORE = ["D0", "D3", "D6b", "D7"]



def spearman_rho(x, y):
    """Spearman rank correlation."""
    def rank(lst):
        sorted_lst = sorted(enumerate(lst), key=lambda t: t[1])
        ranks = [0] * len(lst)
        for rv, (idx, _) in enumerate(sorted_lst, 1):
            ranks[idx] = rv
        return ranks
    rx, ry = rank(x), rank(y)
    n = len(rx)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    den_x = math.sqrt(sum((r - mean_rx) ** 2 for r in rx))
    den_y = math.sqrt(sum((r - mean_ry) ** 2 for r in ry))
    if den_x == 0 or den_y == 0:
        return float("nan")
    return num / (den_x * den_y)


def pca_full(matrix, families):
    """Full PCA via covariance eigen-decomposition. Returns all components."""
    arr = np.array(matrix, dtype=float)
    # Centre columns
    arr = arr - arr.mean(axis=0)
    n, p = arr.shape
    cov = np.cov(arr.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # eigh returns ascending — reverse
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Fix the sign of each eigenvector. Eigen-decomposition determines each
    # component only up to a sign, and LAPACK's choice varies across builds, so
    # loadings and projections can flip wholesale between machines while the
    # decomposition is unchanged. Orient every component so its dominant loading
    # is negative — arbitrary, like any sign convention, but deterministic.
    for j in range(eigenvectors.shape[1]):
        dominant = np.argmax(np.abs(eigenvectors[:, j]))
        if eigenvectors[dominant, j] > 0:
            eigenvectors[:, j] = -eigenvectors[:, j]

    # Variance explained
    total = eigenvalues.sum()
    var_explained = [float(e / total) for e in eigenvalues]
    cum_var = [sum(var_explained[:i+1]) for i in range(len(var_explained))]

    # Loadings (correlations of variables with components)
    # For component j: loading_j = eigenvector_j * sqrt(eigenvalue_j)
    loadings = {}
    for j in range(p):
        loading_vec = eigenvectors[:, j] * math.sqrt(max(0, eigenvalues[j]))
        # Normalize to unit-sum absolute loadings for interpretability
        loadings[f"PC{j+1}"] = {f: float(loading_vec[i]) for i, f in enumerate(families)}

    # Projections of each outlet onto components
    projections = arr @ eigenvectors

    return {
        "eigenvalues": [float(e) for e in eigenvalues],
        "var_explained": var_explained,
        "cum_var": cum_var,
        "loadings": loadings,
        "eigenvectors": eigenvectors,
        "projections": projections,
    }


def find_complete_cases(z_matrix, families):
    """Find outlets with data in ALL given families (complete cases)."""
    all_outlets = set()
    for fam in families:
        all_outlets.update(z_matrix[fam].keys())
    
    complete = []
    for name in sorted(all_outlets):
        vals = [z_matrix[fam].get(name) for fam in families]
        if all(v is not None for v in vals):
            complete.append(name)
    return complete


def build_complete_matrix(z_matrix, families, outlet_list):
    """Build n x p matrix for complete cases."""
    return [[z_matrix[fam][name] for fam in families] for name in outlet_list]


def pairwise_pearson(z_matrix, families, outlet_names):
    """Compute all pairwise Pearson r between families using all available data."""
    results = {}
    for i, fa in enumerate(families):
        for fb in families[i+1:]:
            pairs = []
            for name in outlet_names:
                va = z_matrix[fa].get(name)
                vb = z_matrix[fb].get(name)
                if va is not None and vb is not None:
                    pairs.append((va, vb))
            n = len(pairs)
            if n < 3:
                results[(fa, fb)] = (None, n)
                continue
            xs, ys = zip(*pairs)
            mx, my = sum(xs)/n, sum(ys)/n
            num = sum((x - mx)*(y - my) for x, y in zip(xs, ys))
            sx = math.sqrt(sum((x - mx)**2 for x in xs))
            sy = math.sqrt(sum((y - my)**2 for y in ys))
            if sx == 0 or sy == 0:
                results[(fa, fb)] = (None, n)
            else:
                results[(fa, fb)] = (num / (sx * sy), n)
    return results


def main():
    print("=" * 80)
    print("  UNIDIMENSIONALITY VALIDATION — Expanded PCA Analysis")
    print("=" * 80)

    # ── Load data ────────────────────────────────────────────────────────────
    outlets = load_v2_data()["outlets"]
    inject_d0(outlets)
    inject_d3_ppr(outlets)
    inject_d7(outlets)
    inject_d8_af(outlets)
    z_matrix = build_standardized_matrix(outlets)
    outlet_names = [o["name"] for o in outlets]
    
    print(f"\nLoaded {len(outlets)} outlets, {len(DIRECT_FAMILIES)} families.")

    # ── 1. Pairwise correlations (all families) ──────────────────────────────
    print("\n" + "─" * 80)
    print("  1. PAIRWISE FAMILY CORRELATIONS (Pearson r, pairwise complete)")
    print("─" * 80)
    pairwise = pairwise_pearson(z_matrix, DIRECT_FAMILIES, outlet_names)
    
    all_rs = []
    r_table = {}
    for fa in DIRECT_FAMILIES:
        for fb in DIRECT_FAMILIES:
            if fa < fb:
                r, n = pairwise.get((fa, fb), pairwise.get((fb, fa), (None, 0)))
                r_table[(fa, fb)] = (r, n)
                if r is not None:
                    all_rs.append(r)
                    if n >= 5:
                        print(f"    {fa} vs {fb}: r={r:.3f} (n={n})")
    
    if all_rs:
        mean_r = sum(all_rs) / len(all_rs)
        min_r = min(all_rs)
        max_r = max(all_rs)
        print(f"\n    Summary: mean r={mean_r:.3f}, min={min_r:.3f}, max={max_r:.3f}")
        print(f"    (k={len(all_rs)} pairs with any non-null data)")

    # ── 2. PCA on high-coverage families (complete cases) ────────────────────
    print("\n" + "─" * 80)
    print(f"  2. PCA ON HIGH-COVERAGE FAMILIES: {HIGH_COV}")
    print("─" * 80)
    
    complete_outlets = find_complete_cases(z_matrix, HIGH_COV)
    print(f"    Complete-case outlets: {len(complete_outlets)}")
    for name in complete_outlets:
        print(f"      {name}")
    
    matrix = build_complete_matrix(z_matrix, HIGH_COV, complete_outlets)
    pca_result = pca_full(matrix, HIGH_COV)
    
    print("\n    -- Eigenvalues & Variance Explained --")
    for j, (ev, vr, cv) in enumerate(zip(
        pca_result["eigenvalues"], pca_result["var_explained"], pca_result["cum_var"]
    )):
        print(f"    PC{j+1}: λ={ev:.4f}, var={vr:.1%}, cum={cv:.1%}")
    
    print("\n    -- PC1 Loadings --")
    for fam, loading in sorted(pca_result["loadings"]["PC1"].items(), key=lambda x: -abs(x[1])):
        print(f"      {fam}: {loading:+.4f}")
    
    print("\n    -- PC2 Loadings --")
    for fam, loading in sorted(pca_result["loadings"]["PC2"].items(), key=lambda x: -abs(x[1])):
        print(f"      {fam}: {loading:+.4f}")
    
    # PC1 vs PC2 scatter for each outlet
    print("\n    -- PC1 vs PC2 Projections --")
    for i, name in enumerate(complete_outlets):
        pc1 = pca_result["projections"][i, 0]
        pc2 = pca_result["projections"][i, 1]
        print(f"      {name:<22} PC1={pc1:+.3f}  PC2={pc2:+.3f}")

    # Spearman between PC1 and final FrIdéo score
    # Get final scores from a quick model run
    from analysis_v2 import compute_latent_scores, standardize_final
    lat = compute_latent_scores(outlets, z_matrix)
    scored, _, _, _ = standardize_final(lat)
    
    pc1_vals = [pca_result["projections"][i, 0] for i in range(len(complete_outlets))]
    final_vals = [scored[name]["final"] for name in complete_outlets]
    rho_pc1_final = spearman_rho(pc1_vals, final_vals)
    print(f"\n    Spearman ρ(PC1, final FrIdéo score): {rho_pc1_final:.4f}")

    # ── 3. PCA on CORE families (D0, D3, D6b, D7) ───────────────────────────
    print("\n" + "─" * 80)
    print(f"  3. PCA ON CORE FAMILIES: {PCA_CORE}")
    print("─" * 80)
    
    core_outlets = find_complete_cases(z_matrix, PCA_CORE)
    print(f"    Complete-case outlets: {len(core_outlets)}")
    
    core_matrix = build_complete_matrix(z_matrix, PCA_CORE, core_outlets)
    core_pca = pca_full(core_matrix, PCA_CORE)
    
    for j, (ev, vr, cv) in enumerate(zip(
        core_pca["eigenvalues"], core_pca["var_explained"], core_pca["cum_var"]
    )):
        print(f"    PC{j+1}: λ={ev:.4f}, var={vr:.1%}, cum={cv:.1%}")
    
    print("\n    -- PC1 Loadings --")
    for fam, loading in sorted(core_pca["loadings"]["PC1"].items(), key=lambda x: -abs(x[1])):
        print(f"      {fam}: {loading:+.4f}")
    
    print("\n    -- PC2 Loadings --")
    for fam, loading in sorted(core_pca["loadings"]["PC2"].items(), key=lambda x: -abs(x[1])):
        print(f"      {fam}: {loading:+.4f}")
    
    # ── 4. Economic vs Cultural axis test ─────────────────────────────────────
    print("\n" + "─" * 80)
    print("  4. ECONOMIC vs CULTURAL AXIS TEST")
    print("─" * 80)
    print("""
    Hypothesis: if a second dimension separates economic conservatism (D0/ownership)
    from cultural conservatism (D4 ratings, D6a self-declared, D6b third-party),
    then outlets like La Croix and Les Echos should occupy different regions
    in PC1-PC2 space.
    """)
    
    # Check specific outlets in PC1-PC2 space
    ec_cultural_outlets = ["La Croix", "Les Echos", "Marianne", "Le Monde", "Le Figaro", "Franceinfo"]
    print("    Target outlets in PC1-PC2 space (core PCA, 4 families):")
    for name in ec_cultural_outlets:
        if name in core_outlets:
            idx = core_outlets.index(name)
            pc1 = core_pca["projections"][idx, 0]
            pc2 = core_pca["projections"][idx, 1]
            final = scored[name]["final"]
            # Show z-scores per family
            fam_zs = {f: z_matrix[f].get(name) for f in PCA_CORE}
            fam_str = ", ".join(f"{f}={fam_zs[f]:+.2f}" if fam_zs[f] is not None else f"{f}=NA" for f in PCA_CORE)
            print(f"      {name:<22} PC1={pc1:+.3f}  PC2={pc2:+.3f}  (final={final:+.3f})  [{fam_str}]")
    
    # Compute correlation between PC2 and "economic minus cultural" index
    # PC2 loadings: positive = economic, negative = cultural (or vice versa)
    pc2_load = core_pca["loadings"]["PC2"]
    # If D0 loads positively on PC2, then outlets with high PC2 are "economic right"
    # If D6b loads negatively on PC2, then outlets with low PC2 are "cultural right"
    print(f"\n    PC2 loading for D0 (ownership/economic): {pc2_load.get('D0', 0):+.4f}")
    print(f"    PC2 loading for D6b (third-party/cultural): {pc2_load.get('D6b', 0):+.4f}")
    print(f"    PC2 loading for D7 (content/lexical): {pc2_load.get('D7', 0):+.4f}")
    print(f"    PC2 loading for D3 (network/academic): {pc2_load.get('D3', 0):+.4f}")
    
    # Does D0 correlate with final score differently from D6b?
    d0_vals = []
    d6b_vals = []
    final_vals_all = []
    for name in outlet_names:
        d0 = z_matrix["D0"].get(name)
        d6b = z_matrix["D6b"].get(name)
        if d0 is not None and d6b is not None:
            d0_vals.append(d0)
            d6b_vals.append(d6b)
            final_vals_all.append(scored[name]["final"])
    
    rho_d0_final = spearman_rho(d0_vals, final_vals_all)
    rho_d6b_final = spearman_rho(d6b_vals, final_vals_all)
    rho_d7_final = spearman_rho(
        [z_matrix["D7"][name] for name in outlet_names if z_matrix["D7"].get(name) is not None],
        [scored[name]["final"] for name in outlet_names if z_matrix["D7"].get(name) is not None]
    )
    print(f"\n    Spearman ρ(D0 ownership, final score): {rho_d0_final:.4f}  (n={len(d0_vals)})")
    print(f"    Spearman ρ(D6b third-party, final score): {rho_d6b_final:.4f}  (n={len(d6b_vals)})")
    print(f"    Spearman ρ(D7 content, final score): {rho_d7_final:.4f}")

    # ── 5. Could a second dimension meaningfully change the ranking? ──────────
    print("\n" + "─" * 80)
    print("  5. SECOND-DIMENSION IMPACT ASSESSMENT")
    print("─" * 80)
    
    pc2_var = core_pca["var_explained"][1] if len(core_pca["var_explained"]) > 1 else 0
    pc1_var = core_pca["var_explained"][0] if len(core_pca["var_explained"]) > 0 else 0
    ratio = pc1_var / pc2_var if pc2_var > 0 else float("inf")
    
    print(f"""
    PC1 explains {pc1_var:.1%} of shared variance among 4 core families.
    PC2 explains {pc2_var:.1%}.
    PC1/PC2 ratio: {ratio:.1f}x

    Interpretation:
    - A ratio > 3x with strong loadings on a single dimension supports unidimensionality.
    - PC2 likely captures residual methodological variance (e.g. D0 vs D6b disagreement
      on specific outlets) rather than a substantively separate ideological dimension.
    - For a second dimension to be substantively meaningful, we would need:
      (a) PC2 variance >~15%, and (b) interpretable outlet separation on PC2.
    """)

    # ── 6. Cross-validation: within-family vs between-family agreement ─────────
    print("\n" + "─" * 80)
    print("  6. WITHIN-DOMAIN vs BETWEEN-DOMAIN AGREEMENT")
    print("─" * 80)

    # Group families by methodological provenance
    groups = {
        "Ownership": ["D0"],
        "Academic & Network": ["D1", "D2", "D3"],
        "Ratings": ["D4"],
        "Editorial & Content": ["D6a", "D6b", "D7"],
    }
    
    print("\n    Within-group correlations (mean absolute r):")
    for gname, gfamilies in groups.items():
        grs = []
        for fa in gfamilies:
            for fb in gfamilies:
                if fa < fb:
                    r, n = r_table.get((fa, fb), (None, 0))
                    if r is not None and n >= 3:
                        grs.append(abs(r))
        if grs:
            mean_gr = sum(grs) / len(grs)
            print(f"      {gname}: mean |r| = {mean_gr:.3f} (k={len(grs)} pairs within group)")
        else:
            print(f"      {gname}: insufficient pairs")
    
    print("\n    Between-group correlations (mean absolute r):")
    bg_rs = []
    for ga_name, ga_fams in groups.items():
        for gb_name, gb_fams in groups.items():
            if ga_name >= gb_name:
                continue
            for fa in ga_fams:
                for fb in gb_fams:
                    r, n = r_table.get((fa, fb), r_table.get((fb, fa), (None, 0)))
                    if r is not None and n >= 5:
                        bg_rs.append(abs(r))
    if bg_rs:
        mean_bgr = sum(bg_rs) / len(bg_rs)
        print(f"      Between all groups: mean |r| = {mean_bgr:.3f} (k={len(bg_rs)} pairs)")
    
    # ── 7. Save report ────────────────────────────────────────────────────────
    report_path = RESULTS / "unidimensional_validation_report.md"
    with open(report_path, "w") as f:
        f.write("# Unidimensionality Validation Report\n\n")
        f.write(f"Generated: {Path(__file__).name}\n")
        f.write(f"Outlet count: {len(outlets)}\n")
        f.write(f"Family count: {len(DIRECT_FAMILIES)}\n\n")
        
        f.write("## 1. Pairwise Family Correlations\n\n")
        f.write("| Family pair | Pearson r | n |\n")
        f.write("|------------|-----------|----|\n")
        for (fa, fb), (r, n) in sorted(r_table.items(), key=lambda x: -abs(x[1][0] or 0)):
            r_str = f"{r:.3f}" if r is not None else "NA"
            f.write(f"| {fa} vs {fb} | {r_str} | {n} |\n")
        
        f.write(f"\nMean r (all pairs): {mean_r:.3f}\n")
        f.write(f"Min r: {min_r:.3f}, Max r: {max_r:.3f}\n\n")
        
        f.write("## 2. PCA on High-Coverage Families\n\n")
        f.write(f"Families: {HIGH_COV}\n")
        f.write(f"Complete-case outlets: {len(complete_outlets)} — {', '.join(complete_outlets)}\n\n")
        
        f.write("| Component | Eigenvalue | Variance % | Cumulative % |\n")
        f.write("|-----------|-----------|-----------|-------------|\n")
        for j, (ev, vr, cv) in enumerate(zip(
            pca_result["eigenvalues"], pca_result["var_explained"], pca_result["cum_var"]
        )):
            f.write(f"| PC{j+1} | {ev:.4f} | {vr:.1%} | {cv:.1%} |\n")
        
        f.write("\n### PC1 Loadings\n\n")
        for fam, loading in sorted(pca_result["loadings"]["PC1"].items(), key=lambda x: -abs(x[1])):
            f.write(f"- **{fam}**: {loading:+.4f}\n")
        
        f.write("\n### PC2 Loadings\n\n")
        for fam, loading in sorted(pca_result["loadings"]["PC2"].items(), key=lambda x: -abs(x[1])):
            f.write(f"- **{fam}**: {loading:+.4f}\n")
        
        f.write(f"\nSpearman ρ(PC1, final FrIdéo score): {rho_pc1_final:.4f}\n\n")
        
        f.write("## 3. PCA on Core Families (D0, D3, D6b, D7)\n\n")
        f.write(f"Complete-case outlets: {len(core_outlets)}\n\n")
        j = 0
        for ev, vr, cv in zip(
            core_pca["eigenvalues"], core_pca["var_explained"], core_pca["cum_var"]
        ):
            j += 1
            f.write(f"- PC{j}: λ={ev:.4f}, var={vr:.1%}, cum={cv:.1%}\n")
        
        f.write("\n### PC1 Loadings\n\n")
        for fam, loading in sorted(core_pca["loadings"]["PC1"].items(), key=lambda x: -abs(x[1])):
            f.write(f"- **{fam}**: {loading:+.4f}\n")
        
        f.write("\n### PC2 Loadings\n\n")
        for fam, loading in sorted(core_pca["loadings"]["PC2"].items(), key=lambda x: -abs(x[1])):
            f.write(f"- **{fam}**: {loading:+.4f}\n")
        
        f.write("\n### PC1 vs PC2 Projections\n\n")
        f.write("| Outlet | PC1 | PC2 | Final score |\n")
        f.write("|--------|-----|-----|-------------|\n")
        for i, name in enumerate(core_outlets):
            pc1 = core_pca["projections"][i, 0]
            pc2 = core_pca["projections"][i, 1]
            fnl = scored[name]["final"]
            f.write(f"| {name} | {pc1:+.3f} | {pc2:+.3f} | {fnl:+.3f} |\n")
        
        f.write("\n## 4. Economic vs Cultural Axis Test\n\n")
        
        f.write("\n### Target outlets in PC1-PC2 space\n\n")
        f.write("| Outlet | PC1 | PC2 | Final | D0 | D3 | D6b | D7 |\n")
        f.write("|--------|-----|-----|-------|----|----|-----|-----|\n")
        for name in outlet_names:
            if name in core_outlets:
                idx = core_outlets.index(name)
                pc1 = core_pca["projections"][idx, 0]
                pc2 = core_pca["projections"][idx, 1]
                fnl = scored[name]["final"]
                fam_zs = {f: z_matrix[f].get(name) for f in PCA_CORE}
                d0s = f"{fam_zs['D0']:+.2f}" if fam_zs['D0'] is not None else "NA"
                d3s = f"{fam_zs['D3']:+.2f}" if fam_zs['D3'] is not None else "NA"
                d6bs = f"{fam_zs['D6b']:+.2f}" if fam_zs['D6b'] is not None else "NA"
                d7s = f"{fam_zs['D7']:+.2f}" if fam_zs['D7'] is not None else "NA"
                f.write(f"| {name} | {pc1:+.3f} | {pc2:+.3f} | {fnl:+.3f} | {d0s} | {d3s} | {d6bs} | {d7s} |\n")
        
        f.write("\n### PC2 loadings interpretation\n\n")
        f.write(f"- D0 (ownership/economic) loading: {pc2_load.get('D0', 0):+.4f}\n")
        f.write(f"- D6b (third-party/cultural) loading: {pc2_load.get('D6b', 0):+.4f}\n")
        f.write(f"- D7 (content/lexical) loading: {pc2_load.get('D7', 0):+.4f}\n")
        f.write(f"- D3 (network) loading: {pc2_load.get('D3', 0):+.4f}\n\n")
        
        f.write("## 5. Second-Dimension Impact Assessment\n\n")
        f.write(f"- PC1 variance explained: {pc1_var:.1%}\n")
        f.write(f"- PC2 variance explained: {pc2_var:.1%}\n")
        f.write(f"- PC1/PC2 ratio: {ratio:.1f}x\n\n")
        f.write("### Verdict\n\n")
        if pc2_var < 0.10:
            f.write("PC2 explains < 10% of variance — second dimension is negligible.\n")
            f.write("**Conclusion: Strongly supports unidimensionality.**\n")
        elif pc2_var < 0.20:
            f.write("PC2 explains 10-20% of variance — weak secondary signal.\n")
            f.write("**Conclusion: Supports essentially unidimensional structure with minor residual variation.**\n")
        else:
            f.write("PC2 explains > 20% — warrants investigation.\n")
            f.write("**Conclusion: May benefit from a two-dimensional treatment.**\n")
        
        f.write("\n## 6. Within-domain vs Between-domain Agreement\n\n")
        f.write("- Mean within-group |r|: varies by group (see console)\n")
        f.write(f"- Mean between-group |r|: {mean_bgr:.3f}\n\n")
        
        if mean_bgr > 0.5:
            f.write("Between-group correlations are strong — different methodological families converge on the same latent dimension.\n")
        else:
            f.write("Between-group correlations are moderate — some methodological divergence remains.\n")
    
    print(f"\n  Report saved: {report_path}")

    # ── 7. Generate plots ────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        
        # Scree plot (core PCA)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        eigvals = core_pca["eigenvalues"]
        var_exp = core_pca["var_explained"]
        
        # Scree
        ax1.bar(range(1, len(eigvals)+1), eigvals, color="#4477AA", alpha=0.7)
        ax1.plot(range(1, len(eigvals)+1), eigvals, 'o-', color="#CC0000", lw=2)
        ax1.axhline(1.0, color="#888", ls="--", lw=1, label="λ=1 (Kaiser criterion)")
        ax1.set_xlabel("Principal Component", fontsize=11)
        ax1.set_ylabel("Eigenvalue", fontsize=11)
        ax1.set_title("Scree Plot (D0, D3, D6b, D7)", fontsize=12)
        ax1.legend(fontsize=9)
        
        # Variance explained
        ax2.bar(range(1, len(var_exp)+1), [v*100 for v in var_exp], color="#4477AA", alpha=0.7, label="Individual")
        ax2.plot(range(1, len(var_exp)+1), [v*100 for v in var_exp], 'o-', color="#CC0000", lw=2)
        ax2.plot(range(1, len(var_exp)+1), [v*100 for v in core_pca["cum_var"]], 's--', 
                 color="#228B22", lw=1.5, label="Cumulative")
        ax2.set_xlabel("Principal Component", fontsize=11)
        ax2.set_ylabel("Variance Explained (%)", fontsize=11)
        ax2.set_title("Variance Explained (D0, D3, D6b, D7)", fontsize=12)
        ax2.legend(fontsize=9)
        
        plt.tight_layout()
        scree_path = PLOTS_DIR / "pca_scree.png"
        fig.savefig(scree_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Scree plot saved: {scree_path}")
        
        # PC1 vs PC2 scatter (core PCA)
        fig, ax = plt.subplots(figsize=(12, 9))
        
        pc1s = core_pca["projections"][:, 0]
        pc2s = core_pca["projections"][:, 1]
        
        # Color by ideology label
        from analysis_v2 import compute_labels
        # Quick label assignment for coloring
        _, labels, _ = compute_labels(scored)
        
        label_colors = {
            "far-left": "#8B0000", "left": "#CC3333", "center-left": "#DD7766",
            "center": "#888888", "center-right": "#6699CC",
            "right": "#3355AA", "far-right": "#1a1a6b"
        }
        
        for i, name in enumerate(core_outlets):
            lbl = labels.get(name, "center")
            color = label_colors.get(lbl, "#888888")
            ax.scatter(pc1s[i], pc2s[i], c=color, s=100, alpha=0.8, edgecolors="#333", linewidths=0.8, zorder=5)
            ax.annotate(name, (pc1s[i], pc2s[i]), fontsize=8, alpha=0.9,
                       ha="left" if pc1s[i] > 0 else "right", va="bottom",
                       xytext=(3, 3), textcoords="offset points")
        
        # Add loading vectors
        for fam, loading_vec in core_pca["loadings"].items():
            if fam == "PC1":
                for f, l in loading_vec.items():
                    # Scale loadings for visibility
                    ax.arrow(0, 0, l * 3, 0, head_width=0.3, head_length=0.3, 
                            fc="#CC0000", ec="#CC0000", alpha=0.6)
        # PC2 loadings as arrows
        pc2_load_map = core_pca["loadings"]["PC2"]
        # For PC2, show the loading direction
        for f, l in pc2_load_map.items():
            ax.arrow(0, 0, 0, l * 3, head_width=0.3, head_length=0.3,
                    fc="#2255AA", ec="#2255AA", alpha=0.6)
        
        # Labels for loadings
        for f, l in pc2_load_map.items():
            y_offset = l * 3
            ax.text(0.2, y_offset + 0.2 if y_offset >= 0 else y_offset - 0.3, f,
                   fontsize=10, color="#2255AA", fontweight="bold", alpha=0.8)
        
        ax.axhline(0, color="#888", lw=0.8, ls="--", alpha=0.5)
        ax.axvline(0, color="#888", lw=0.8, ls="--", alpha=0.5)
        
        # Calculate equal aspect ratio
        max_range = max(abs(pc1s).max(), abs(pc2s).max()) * 1.15
        ax.set_xlim(-max_range, max_range)
        ax.set_ylim(-max_range, max_range)
        ax.set_aspect('equal')
        
        ax.set_xlabel(f"PC1 ({core_pca['var_explained'][0]:.1%} variance)", fontsize=11)
        ax.set_ylabel(f"PC2 ({core_pca['var_explained'][1]:.1%} variance)", fontsize=11)
        ax.set_title("PCA Biplot: PC1 vs PC2 (D0, D3, D6b, D7)", fontsize=12)
        
        plt.tight_layout()
        biplot_path = PLOTS_DIR / "pca_biplot.png"
        fig.savefig(biplot_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Biplot saved: {biplot_path}")
        
    except ImportError as e:
        print(f"  (matplotlib import error: {e}; skipping plots)")
    
    print("\n" + "=" * 80)
    print("  DONE")
    print("=" * 80)


if __name__ == "__main__":
    main()
