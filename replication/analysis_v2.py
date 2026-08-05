"""
Latent ideology scoring for 30 French news outlets.

  1. Z-score each direct family across outlets with data
  2. Average standardised families per outlet (missing = skip)
  3. Structural prior from founding tradition (S2)
  4. Shrink toward the prior, empirical-Bayes style
  5. Z-standardise blended scores to mean 0, SD 1
  6. Label via KDE valley detection, falling back to GMM then sigma bands
  7. Sigma from bootstrap of family weights
  8. Sensitivity: leave-one-family-out, weight perturbation

Scores are in SD units of the 30-outlet panel: they measure position within
this panel, not absolute ideology.

Direct families:
  D0   Ownership ideology, from S1_owner_category via OWNER_STRUCTURAL
  D1   Cage et al. (2022) - guest radical-right deviation vs the France 2 benchmark
  D2   Pew Research Center (2018) - perceived ideology (0-6, 3 = centre)
  D3   Cointet et al. (2021) - dual personalised PageRank on a 421-node,
       20,992-edge hyperlink network; log(ppr_right / ppr_left), panel-z-scored.
       Outlets absent from the 2019 crawl (Blast, Franceinfo) keep the JSON
       categorical fallback.
  D4   Media Bias/Fact Check - categorical label mapped to numeric
  D6a  Self-declared editorial orientation (charter, statutes, editor statements)
  D6b  Third-party profiling (encyclopedic entries, press typology)
  D7   Distancing-aware lexical score
  D8   Ad Fontes Media rating

S2 (founding tradition) is the shrinkage target, not a direct family.
"""

import json
import math
import random
import csv
import statistics
from pathlib import Path
from collections import defaultdict

# ── paths ──────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
DATA_FILE = BASE / "data" / "outlets_evidence_v2.json"
RESULTS_DIR = BASE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── config ────────────────────────────────────────────────────────────────────
DIRECT_FAMILIES = ["D0", "D1", "D2", "D3", "D4", "D6a", "D6b", "D7", "D8"]

# Shrinkage: lambda controls blend between direct and structural.
# z_final = (n/(n+lambda)) * z_direct + (lambda/(n+lambda)) * z_structural
# lambda=2: outlet with 2 direct indicators = 50/50 blend; 4 indicators = 67% direct
SHRINKAGE_LAMBDA = 2.0

# Bootstrap parameters
N_BOOTSTRAP = 10_000
RANDOM_SEED = 42

# Seven ideology labels mapping to French political convention.
# Cut-points are computed empirically from KDE valley detection — not hand-set.
# Fallback uses nested sigma-band cuts: ±1.5σ / ±0.75σ / ±0.25σ
# (see _equal_sd_cutoffs for derivation).
IDEOLOGY_LABELS    = ["far-left", "left", "center-left", "center", "center-right", "right", "far-right"]
IDEOLOGY_LABELS_FR = ["extr. gauche", "gauche", "centre-gauche", "centre", "centre-droite", "droite", "extr. droite"]
N_LABEL_CUTS = len(IDEOLOGY_LABELS) - 1  # = 6 cut-points for 7 bins

# Source-family consistency parameters (σ_k): lower = closer agreement with the
# remaining evidence pool. Estimated empirically via leave-one-family-out
# residual variance:
#   σ_k^2 = variance(z_ik - z_i^(-k)) across outlets with data in family k.
# Computed by scripts/estimate_sigma_empirical.py.
_FAMILY_SIGMA_FILE = BASE / "results" / "family_sigma.json"


def _load_family_sigma() -> dict:
    """Load sigma_k from results/family_sigma.json.

    estimate_sigma_empirical.py imports this module to generate that file, so
    it sets IDEOLOGY_SIGMA_BOOTSTRAP=1 to get {} instead of FileNotFoundError.
    """
    import json as _json, os as _os
    if not _FAMILY_SIGMA_FILE.exists():
        if _os.environ.get("IDEOLOGY_SIGMA_BOOTSTRAP") == "1":
            return {}
        raise FileNotFoundError(
            f"{_FAMILY_SIGMA_FILE} not found. "
            "Run scripts/estimate_sigma_empirical.py first."
        )
    with open(_FAMILY_SIGMA_FILE) as _f:
        return _json.load(_f)


FAMILY_SIGMA = _load_family_sigma()


# ── data loading ──────────────────────────────────────────────────────────────
def load_v2_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def inject_d0(outlets: list) -> None:
    """
    Inject D0 (ownership ideology) into each outlet's direct indicator dict.

    D0 raw value = OWNER_STRUCTURAL[S1_owner_category], which encodes the
    political orientation of the controlling owner on a monotone scale
    (party_communist=-2.0 … bollore_vivendi=+1.5 … safa_privinvest=+2.0).
    Coverage is universal (every outlet has a documented owner category).

    Raw values are z-scored by standardize_family, so only the ordinal
    ranking matters.

    Categories absent from OWNER_STRUCTURAL (→ null D0, no imputation):
      "contested"  — ownership genuinely unknown (no basis for ideology mapping)
      "anonymous"  — Fdesouche; operator unknown (behavioral signals suffice)
    """
    for outlet in outlets:
        cat = outlet["structural"]["S1_owner_category"]
        outlet["direct"]["D0"] = OWNER_STRUCTURAL.get(cat, None)


D3_PPR_CSV    = BASE / "results" / "cointet_d3_continuous.csv"
# D7 window: all-category corpus pooled over 2024-2025. All-category rather than
# 'politique'-tagged avoids outlet-dependent tagging bias; the lexicon selects
# political signal-bearing articles.
D7_SCORES_CSV = BASE / "results" / "d5_score_d5_allcat_2024-2025_endorsed.csv"
D8_AF_JSON    = BASE / "gn" / "gn_bias_ratings.json"


def inject_d7(outlets: list) -> None:
    """
    Set each outlet's D7 from D7_SCORES_CSV, which is authoritative: an outlet
    with no valid d5_raw there (no row, or below the 10-signal-article
    threshold) gets D7 = None regardless of the JSON. Over the 2024-2025
    window all 30 outlets clear the threshold.

    Column used: d5_raw.
    """
    if not D7_SCORES_CSV.exists():
        print(f"  [inject_d7] D7 scores CSV not found: {D7_SCORES_CSV} — D7 unchanged")
        return

    d7_scores = {}
    with open(D7_SCORES_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            val = row.get("d5_raw", "").strip()
            if val:
                d7_scores[row["outlet_json_name"]] = float(val)

    replaced = 0
    nulled = 0
    for outlet in outlets:
        name = outlet["name"]
        if name in d7_scores:
            outlet["direct"]["D7"] = d7_scores[name]
            replaced += 1
        else:
            if outlet["direct"].get("D7") is not None:
                nulled += 1
            outlet["direct"]["D7"] = None

    print(f"  [inject_d7] Updated D7 for {replaced}/{len(outlets)} outlets from CSV "
          f"({len(outlets) - replaced} nulled — below min-signal threshold; "
          f"{nulled} stale JSON value(s) overridden to null)")


def inject_d8_af(outlets: list) -> None:
    """
    Inject D8 (Ad Fontes Media bias ratings) from the Ground News scrape.

    Reads gn/gn_bias_ratings.json and sets each outlet's direct.D8 value
    using the ad_fontes rater entry. Outlets without an AF rating on GN,
    or whose GN slug is a non-French parent brand (Slate.fr), are left null.

    Numeric scale matches D4 (MBFC):
      left=-2.0  leanLeft=-1.0  center=0.0  leanRight=+1.0  right=+2.0

    Clean coverage (7 outlets, all verified French pages):
      Libération, Le Monde, BFMTV, TF1 INFO, 20 Minutes, Le Parisien, Le Figaro
    """
    if not D8_AF_JSON.exists():
        print(f"  [inject_d8_af] GN bias JSON not found: {D8_AF_JSON} — D8 skipped")
        return

    label_to_num = {
        "left": -2.0, "leanLeft": -1.0, "center": 0.0,
        "leanRight": 1.0, "right": 2.0, "farLeft": -2.0, "farRight": 2.0,
    }
    # Slate.fr GN page is the US parent brand — exclude from D8
    EXCLUDE = {"Slate.fr"}

    with open(D8_AF_JSON) as f:
        gn_data = json.load(f)

    injected = 0
    for outlet in outlets:
        name = outlet["name"]
        if name in EXCLUDE:
            outlet["direct"]["D8"] = None
            continue
        entry = gn_data.get(name, {})
        bias = entry.get("bias") or {}
        ratings = bias.get("ratings", {})
        af_label = ratings.get("ad_fontes", {}).get("bias")
        val = label_to_num.get(af_label) if af_label else None
        outlet["direct"]["D8"] = val
        if val is not None:
            injected += 1

    print(f"  [inject_d8_af] Injected D8 (Ad Fontes Media) for {injected}/{len(outlets)} outlets "
          f"({len(outlets) - injected} null — not rated by AF on GN)")


def inject_d3_ppr(outlets: list) -> None:
    """
    Replace categorical D3 values with continuous PPR-derived positions from
    the Cointet 2021 web-link network (HAL halshs-03299024).

    For each outlet that has a PPR score in cointet_d3_continuous.csv, the
    existing JSON D3 value (5-point categorical) is overwritten with the
    panel-z-standardised PPR score — a continuous position derived from
    dual Personalised PageRank on the 421-node hyperlink network.

    Outlets absent from the 2019 crawl (Blast, Franceinfo) have an empty
    ppr_z_panel and are left unchanged, keeping their JSON fallback value.

    The raw values are re-z-scored by standardize_family() together with all
    other outlets, so the input scale only needs to preserve relative spacing.
    ppr_z_panel is used directly.
    """
    if not D3_PPR_CSV.exists():
        print(f"  [inject_d3_ppr] PPR CSV not found: {D3_PPR_CSV} — D3 unchanged")
        return

    ppr_scores = {}
    with open(D3_PPR_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            val = row.get("ppr_z_panel", "").strip()
            if val:
                ppr_scores[row["outlet"]] = float(val)

    replaced = 0
    for outlet in outlets:
        name = outlet["name"]
        if name in ppr_scores:
            outlet["direct"]["D3"] = ppr_scores[name]
            replaced += 1

    print(f"  [inject_d3_ppr] Replaced D3 with continuous PPR for {replaced}/{len(outlets)} outlets "
          f"({len(outlets) - replaced} kept categorical fallback)")


# ── family standardization ────────────────────────────────────────────────────
def standardize_family(outlets: list, family: str, ref_mean: float = None, ref_std: float = None) -> dict:
    """Z-score a direct indicator family across outlets with available data.

    ref_mean / ref_std: if supplied, use these as the normalisation constants
    instead of computing them from the family's own covered outlets. Used for
    D8 so its narrow 7-outlet panel does not inflate z-scores relative to D4,
    which uses the same ordinal scale over a wider panel.
    """
    values = {
        o["name"]: o["direct"][family]
        for o in outlets
        if o["direct"].get(family) is not None
    }
    if len(values) < 2:
        return {k: 0.0 for k in values}

    if ref_mean is not None and ref_std is not None:
        mean_k, std_k = ref_mean, ref_std
    else:
        vals = list(values.values())
        mean_k = sum(vals) / len(vals)
        std_k = statistics.pstdev(vals)

    if std_k < 1e-9:
        return {k: 0.0 for k in values}
    return {k: (v - mean_k) / std_k for k, v in values.items()}


def build_standardized_matrix(outlets: list, families: list = None) -> dict:
    """Return {family: {outlet_name: z_score}} for all direct families.

    D8 is normalised against D4's distribution: both use the same ordinal
    scale, but D4 spans the full spectrum while D8 covers only the centrist
    mainstream, which would otherwise inflate its z-scores.
    """
    if families is None:
        families = DIRECT_FAMILIES

    # Compute D4 reference stats once (used to normalise D8)
    d4_ref_mean = d4_ref_std = None
    if "D4" in families and "D8" in families:
        d4_vals = [
            o["direct"]["D4"]
            for o in outlets
            if o["direct"].get("D4") is not None
        ]
        if len(d4_vals) >= 2:
            d4_ref_mean = sum(d4_vals) / len(d4_vals)
            d4_ref_std  = statistics.pstdev(d4_vals)

    matrix = {}
    for fam in families:
        if fam == "D8" and d4_ref_mean is not None:
            matrix[fam] = standardize_family(outlets, fam, ref_mean=d4_ref_mean, ref_std=d4_ref_std)
        else:
            matrix[fam] = standardize_family(outlets, fam)
    return matrix


# ── structural prior ──────────────────────────────────────────────────────────
OWNER_STRUCTURAL = {
    # ── left ──────────────────────────────────────────────────────────────────
    "party_communist":    -2.0,  # PCF (L'Humanité)
    "independent_left":   -1.2,  # Mediapart, Blast — explicitly left cooperative
    "niel_group":         -0.8,  # Le Monde, Le Nouvel Obs, Le HuffPost (Niel/Pigasse/Kretinsky)
    "perdriel":           -0.3,  # Challenges — Claude Perdriel (centre-left magnate, founder of Le Nouvel Obs)
    "independent_neutral": -0.3, # Libération — non-profit fonds de dotation, no owner ideology
    # ── center ────────────────────────────────────────────────────────────────
    "public":              0.0,  # Franceinfo — state broadcaster, legally neutral
    "cooperative":         0.0,  # Ouest-France — SPDH non-profit association
    "rossel_sipa":         0.0,  # 20 Minutes — Rossel (Belgian commercial) + SIPA (Hutin family)
    # "contested" deliberately absent → null D0 (no known owner ideology to map)
    # "anonymous" deliberately absent → null D0 (Fdesouche; no owner-ideology basis)
    # ── center-right ──────────────────────────────────────────────────────────
    "bouygues":            0.3,  # TF1 — Famille Bouygues (conservative, pro-business)
    "catholic_institutional": 0.3, # La Croix — Assomptionists (Catholic, socially conservative)
    "kretinsky":           0.3,  # Marianne — Daniel Kretinsky (Czech; centrist-right investor)
    "saade_cmacgm":        0.3,  # BFMTV — Rodolphe Saadé/CMA CGM (shipping magnate, centrist)
    "drahi_altice":        0.5,  # L'Express — Patrick Drahi (Altice; pro-market liberal-right)
    "beytout_liberal":     0.5,  # L'Opinion — Bettencourt/Beytout/Fisher (pro-market liberal-right)
    "lvmh_arnault":        0.6,  # Le Parisien, Les Echos — Bernard Arnault (LVMH; liberal-right)
    "pinault":             0.7,  # Le Point — François Pinault/Artémis (liberal-right)
    # ── right ─────────────────────────────────────────────────────────────────
    "dassault":            1.0,  # Le Figaro — Famille Dassault (Gaullist conservative)
    "founder_right":       1.2,  # Causeur — Élisabeth Lévy (self-identified right-wing founder)
    "bollore_vivendi":     1.5,  # CNews, JDD — Vincent Bolloré (hard-right editorial control)
    "safa_privinvest":     2.0,  # Valeurs actuelles — Iskandar Safa (far-right aligned)
}

TRADITION_SCALE = 1.5
# S1 (ownership) is D0, a direct family — see inject_d0(). S3 (sanctions) is
# unused: sanctions span the spectrum and carry no directional signal.


def structural_prior(outlet: dict) -> float:
    """
    Tradition-only structural prior (S2). Ownership is D0, a direct family.
    """
    return outlet["structural"]["S2_tradition"] * TRADITION_SCALE


# ── latent score computation ──────────────────────────────────────────────────
def compute_latent_scores(
    outlets: list,
    z_matrix: dict,
    shrinkage_lambda: float = SHRINKAGE_LAMBDA,
    families: list = None,
) -> dict:
    """
    Compute per-outlet latent ideology scores (pre-standardization).
    Returns {outlet_name: {z_direct, z_structural, z_blended, n_direct, evidence_profile}}.
    """
    if families is None:
        families = DIRECT_FAMILIES
    results = {}
    for outlet in outlets:
        name = outlet["name"]

        available_z = []
        evidence_profile = {}
        for fam in families:
            z_val = z_matrix[fam].get(name)
            if z_val is not None:
                available_z.append(z_val)
                evidence_profile[fam] = round(z_val, 4)
            else:
                evidence_profile[fam] = None

        n_direct = len(available_z)
        z_direct = sum(available_z) / n_direct if n_direct > 0 else None
        z_struct = structural_prior(outlet)

        if n_direct == 0:
            z_blended = z_struct
        else:
            alpha = n_direct / (n_direct + shrinkage_lambda)
            z_blended = alpha * z_direct + (1 - alpha) * z_struct

        results[name] = {
            "z_direct": z_direct,
            "z_structural": z_struct,
            "z_blended": z_blended,
            "n_direct": n_direct,
            "evidence_profile": evidence_profile,
        }
    return results


# ── final standardization (replaces anchor transform) ─────────────────────────
def standardize_final(latent: dict) -> tuple:
    """
    Z-standardize blended scores to mean=0, SD=1 across all outlets.

    Returns (scored_dict, mean_z, std_z, scale_factor) where
    scale_factor = 1/std_z is used for uncertainty propagation.
    """
    vals = [v["z_blended"] for v in latent.values()]
    mean_z = sum(vals) / len(vals)
    std_z = statistics.pstdev(vals)

    if std_z < 1e-9:
        scored = {name: {**v, "final": 0.0} for name, v in latent.items()}
        return scored, mean_z, std_z, 1.0

    scale_factor = 1.0 / std_z
    scored = {
        name: {**v, "final": (v["z_blended"] - mean_z) * scale_factor}
        for name, v in latent.items()
    }
    return scored, mean_z, std_z, scale_factor


# ── KDE + label assignment ─────────────────────────────────────────────────────
_SQRT_2PI = math.sqrt(2 * math.pi)


def _kde_density(values: list, x_grid: list, bandwidth: float) -> list:
    n = len(values)
    return [
        sum(math.exp(-0.5 * ((xi - v) / bandwidth) ** 2)
            for v in values) / (n * bandwidth * _SQRT_2PI)
        for xi in x_grid
    ]


def _silverman_bw(values: list) -> float:
    # 1.5× Silverman to smooth over micro-bumps and reveal macro cluster gaps.
    # With n=30 and many center-left outlets, standard Silverman over-resolves
    # the dense center region, producing spurious micro-valleys as cut-points.
    n = len(values)
    std = statistics.pstdev(values)
    return max(0.1, 1.5 * 0.9 * std * n ** (-0.2))


def _find_valleys(x_grid: list, density: list, order: int = 25) -> list:
    """
    Local minima in KDE density with minimum separation = order grid steps.
    Valleys mark natural gaps between ideology clusters.
    """
    n = len(density)
    raw_valleys = []
    for i in range(order, n - order):
        window_lo = density[i - order: i]
        window_hi = density[i + 1: i + order + 1]
        if density[i] <= min(window_lo) and density[i] <= min(window_hi):
            if density[i] < density[i - 1] or density[i] < density[i + 1]:
                raw_valleys.append((x_grid[i], density[i]))

    # Merge valleys closer than 0.2 SD: keep the deeper one
    merged = []
    for x_v, d_v in raw_valleys:
        if merged and abs(x_v - merged[-1][0]) < 0.2:
            if d_v < merged[-1][1]:
                merged[-1] = (x_v, d_v)
        else:
            merged.append((x_v, d_v))

    return [x_v for x_v, _ in merged]


def _equal_sd_cutoffs(values: list, n_cuts: int) -> list:
    """
    Fallback partition using nested sigma-band cuts centred at the mean.

    5 labels (n_cuts=4): ±1.5σ / ±0.5σ  — 1-SD-wide bins
      far-left | left | center | right | far-right

    7 labels (n_cuts=6): ±1.5σ / ±0.75σ / ±0.25σ  — nested bands
      far-left | left | center-left | center | center-right | right | far-right
      Outer labels (left/right):           0.75σ wide
      Inner labels (center-left/c-right):  0.50σ wide
      Center:                              0.50σ wide
      Rationale: with n=30, equal-0.5σ spacing (cuts at ±1.5/±1.0/±0.5/0.0)
      leaves 'center' with only 1 outlet (Ouest-France). The nested-band
      scheme matches the natural cluster structure of French media: a dense
      center-left bloc, a narrow true center, and a compact center-right bloc.

    Other n_cuts: equal-step spacing as before.
    """
    mean_v = sum(values) / len(values)
    std_v = statistics.pstdev(values) or 1.0
    if n_cuts == 4:
        offsets = [-1.5, -0.5, 0.5, 1.5]
    elif n_cuts == 6:
        offsets = [-1.5, -0.75, -0.25, 0.25, 0.75, 1.5]
    else:
        half_span = (n_cuts - 1) / 2.0
        offsets = [i - half_span for i in range(n_cuts)]
    return sorted(mean_v + o * std_v for o in offsets)


def _try_gmm_cutoffs(values: list, n_components_target: int):
    """
    Fit GMMs for k=2..n_components_target+1, pick BIC-optimal k,
    return sorted midpoints between component means as cut-points.
    Returns None if sklearn unavailable or fit fails.
    """
    try:
        from sklearn.mixture import GaussianMixture
        import numpy as np
        X = np.array(values).reshape(-1, 1)
        best_bic = float("inf")
        best_cuts = None
        for k in range(2, n_components_target + 2):
            gm = GaussianMixture(n_components=k, n_init=20, random_state=42)
            gm.fit(X)
            bic = gm.bic(X)
            if bic < best_bic:
                best_bic = bic
                means = sorted(gm.means_.flatten().tolist())
                best_cuts = [(means[i] + means[i + 1]) / 2 for i in range(len(means) - 1)]
        return best_cuts
    except Exception:
        return None


def compute_labels(scored: dict, n_grid: int = 500) -> tuple:
    """
    Assign ideology labels using KDE valley detection on z-standardized scores.

    Strategy:
      1. Estimate density via Gaussian KDE (Silverman bandwidth)
      2. Detect local minima (valleys) = natural category boundaries
      3. If 4 valleys found: use them directly (5 bins)
      4. If >4 valleys: keep the 4 deepest
      5. If <4 valleys: try sklearn GMM+BIC; fall back to equal-SD partition

    Returns:
      cutoffs       — sorted list of 4 cut-points on the z-score scale
      assignments   — {outlet_name: label_string}
      kde_data      — (x_grid, density, bandwidth) for plotting
    """
    scores = {name: v["final"] for name, v in scored.items()}
    vals = list(scores.values())

    bw = _silverman_bw(vals)
    margin = max(1.0, 2 * bw)
    x_min = min(vals) - margin
    x_max = max(vals) + margin
    step = (x_max - x_min) / (n_grid - 1)
    x_grid = [x_min + step * i for i in range(n_grid)]

    density = _kde_density(vals, x_grid, bw)
    order = max(10, n_grid // 20)
    valleys = _find_valleys(x_grid, density, order=order)

    if len(valleys) > N_LABEL_CUTS:
        # Keep the N_LABEL_CUTS deepest valleys
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
    for name, score in scores.items():
        idx = sum(1 for cut in cutoffs if score > cut)
        assignments[name] = IDEOLOGY_LABELS[min(idx, len(IDEOLOGY_LABELS) - 1)]

    return cutoffs, assignments, (x_grid, density, bw)


# ── uncertainty ────────────────────────────────────────────────────────────────
def compute_uncertainty(outlets: list, scored: dict, scale_factor: float, families: list = None) -> dict:
    """
    Per-outlet posterior uncertainty on the z-standardized scale.
    σ_i = scale_factor * sqrt(sum(σ_k²)) / n_direct * (1 + sparsity_penalty).
    """
    if families is None:
        families = DIRECT_FAMILIES
    sigma = {}
    for outlet in outlets:
        name = outlet["name"]
        n = scored[name]["n_direct"]
        if n == 0:
            sigma[name] = scale_factor * 1.5
        else:
            profile = scored[name]["evidence_profile"]
            variance = sum(
                FAMILY_SIGMA[fam] ** 2
                for fam in families
                if profile.get(fam) is not None
            )
            base_sigma = scale_factor * math.sqrt(variance) / n
            sparsity = SHRINKAGE_LAMBDA / (n + SHRINKAGE_LAMBDA)
            sigma[name] = base_sigma * (1 + sparsity)
    return sigma


# ── anchor validation (post-hoc only) ─────────────────────────────────────────
def validate_anchors(outlets: list, scored: dict) -> dict:
    """
    Confirm that the empirical extremes match expected anchors.
    This is a sanity check, NOT a calibration step.
    Returns {anchor_name: {"expected_extreme": str, "actual_rank": int, "final": float}}.
    """
    # Anchors are identified by their model score extremes, not human labels
    anchor_outlets = [o for o in outlets if o.get("is_anchor")]
    if len(anchor_outlets) >= 2:
        anchor_scores = {o["name"]: scored[o["name"]]["final"] for o in anchor_outlets}
        floor_name = min(anchor_scores, key=anchor_scores.get)
        ceil_name  = max(anchor_scores, key=anchor_scores.get)
    elif len(anchor_outlets) == 1:
        floor_name = anchor_outlets[0]["name"]
        ceil_name  = None
    else:
        floor_name = ceil_name = None

    all_sorted = sorted(scored.items(), key=lambda x: x[1]["final"])
    ranks = {name: i + 1 for i, (name, _) in enumerate(all_sorted)}
    n = len(all_sorted)

    result = {}
    if floor_name:
        result[floor_name] = {
            "expected_extreme": "most-negative",
            "actual_rank": ranks.get(floor_name),
            "final": scored.get(floor_name, {}).get("final"),
            "ok": ranks.get(floor_name) == 1,
        }
    if ceil_name:
        result[ceil_name] = {
            "expected_extreme": "most-positive",
            "actual_rank": ranks.get(ceil_name),
            "final": scored.get(ceil_name, {}).get("final"),
            "ok": ranks.get(ceil_name) == n,
        }
    return result


# ── sensitivity: leave-one-family-out ─────────────────────────────────────────
def leave_one_out_sensitivity(outlets: list, families: list = None) -> dict:
    """
    Recompute scores dropping one family at a time.
    Both full and LOO models use z-standardization (no anchor dependency).
    Returns Spearman ρ between full-model and LOO model ranks for each family dropped.
    """
    if families is None:
        families = DIRECT_FAMILIES
    z_full = build_standardized_matrix(outlets, families=families)
    lat_full = compute_latent_scores(outlets, z_full, families=families)
    scored_full, _, _, _ = standardize_final(lat_full)
    names = [o["name"] for o in outlets]
    full_scores = [scored_full[n]["final"] for n in names]

    loo_results = {}
    for drop_fam in families:
        z_loo = {fam: standardize_family(outlets, fam) for fam in families if fam != drop_fam}
        z_loo[drop_fam] = {}

        lat_loo = compute_latent_scores(outlets, z_loo, families=families)
        scored_loo, _, _, _ = standardize_final(lat_loo)
        loo_scores = [scored_loo[n]["final"] for n in names]
        rho = spearman_rho(full_scores, loo_scores)
        loo_results[f"drop_{drop_fam}"] = {
            "rho": rho,
            "n_outlets_affected": len(z_full[drop_fam]),
        }

    return loo_results


def spearman_rho(x: list, y: list) -> float:
    def rank(lst):
        # Average-rank tie handling: tied values share the mean of the ranks
        # they would occupy, so the result is independent of input order.
        sorted_lst = sorted(enumerate(lst), key=lambda t: t[1])
        ranks = [0.0] * len(lst)
        i = 0
        while i < len(sorted_lst):
            j = i
            while j < len(sorted_lst) - 1 and sorted_lst[j + 1][1] == sorted_lst[j][1]:
                j += 1
            avg = (i + j) / 2.0 + 1  # 1-based average rank for the tied group
            for k in range(i, j + 1):
                ranks[sorted_lst[k][0]] = avg
            i = j + 1
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


# ── sensitivity: weight perturbation bootstrap ────────────────────────────────
def perturb_shrinkage_bootstrap(outlets: list, n: int = N_BOOTSTRAP, families: list = None) -> dict:
    """Bootstrap by perturbing shrinkage lambda ±50% and family weights."""
    if families is None:
        families = DIRECT_FAMILIES
    rng = random.Random(RANDOM_SEED)
    z_matrix = build_standardized_matrix(outlets, families=families)
    distributions = defaultdict(list)

    for _ in range(n):
        lam = max(0.1, SHRINKAGE_LAMBDA * (1 + rng.uniform(-0.5, 0.5)))
        perturbed_z = {
            fam: {
                name: z + rng.gauss(0, FAMILY_SIGMA[fam] * 0.3)
                for name, z in z_matrix[fam].items()
            }
            for fam in families
        }
        lat = compute_latent_scores(outlets, perturbed_z, shrinkage_lambda=lam, families=families)
        scored_p, _, _, _ = standardize_final(lat)
        for name, vals in scored_p.items():
            distributions[name].append(vals["final"])

    stats = {}
    for name, boot_scores in distributions.items():
        if boot_scores:
            ss = sorted(boot_scores)
            ns = len(ss)
            stats[name] = {
                "mean": sum(ss) / ns,
                "std": statistics.pstdev(ss),
                "ci_low": ss[int(0.025 * ns)],
                "ci_high": ss[int(0.975 * ns)],
            }
    return stats


# ── output ────────────────────────────────────────────────────────────────────
def print_main_table(outlets: list, scored: dict, sigma: dict, labels: dict, scale_info: tuple):
    mean_z, std_z = scale_info
    print(f"\n{'='*120}")
    print(f"  V2 IDEOLOGY SCORES — z-standardized (mean=0, SD=1 across {len(outlets)} outlets)")
    print(f"  Sample mean of blended scores: {mean_z:+.4f}  |  Sample SD: {std_z:.4f}")
    print("  Scale: 1 unit = 1 SD of the outlet distribution")
    print(f"{'='*120}")
    hdr = (f"{'Outlet':<22} {'z_dir':>7} {'z_str':>7} {'z_bld':>7} {'Final':>7} "
           f"{'σ':>6}  {'95% CI':>16}  {'n_D':>4}  {'Label':<12}  Direct families")
    print(hdr)
    print("-" * 112)

    for outlet in sorted(outlets, key=lambda o: scored[o["name"]]["final"]):
        name = outlet["name"]
        s = scored[name]
        final = s["final"]
        z_d = s["z_direct"]
        z_st = s["z_structural"]
        z_b = s["z_blended"]
        sig = sigma[name]
        n_d = s["n_direct"]
        prof = s["evidence_profile"]
        lbl = labels.get(name, "?")

        anchor_m = "*" if outlet.get("is_anchor") else " "
        axis_m = "~" if outlet.get("axis_crossing") else " "
        flag_m = "!" if outlet.get("data_quality_flag") else " "

        ci_lo = final - 1.96 * sig
        ci_hi = final + 1.96 * sig

        fam_str = " ".join(
            f"{fam}:{prof[fam]:+.2f}" if prof.get(fam) is not None else f"{fam}:NA"
            for fam in DIRECT_FAMILIES
        )

        z_d_str = f"{z_d:+.3f}" if z_d is not None else "    NA"
        print(
            f"{anchor_m}{axis_m}{flag_m}{name:<20} {z_d_str:>7} {z_st:>+7.3f} "
            f"{z_b:>+7.3f} {final:>+7.3f} {sig:>6.3f}  [{ci_lo:+.2f},{ci_hi:+.2f}]  "
            f"{n_d:>4}  {lbl:<12}  {fam_str}"
        )
    print("\n  * = anchor (post-hoc validation only), ~ = axis-crossing, ! = data quality flag")


def print_label_summary(labels: dict, cutoffs: list):
    print("\n  LABEL ASSIGNMENTS (KDE valley detection)")
    print(f"  Cut-points (z-score scale): {', '.join(f'{c:+.3f}' for c in cutoffs)}")
    print(f"  {'Label':<14} {'FR':<14}  Outlets")
    print(f"  {'-'*80}")
    for lbl, lbl_fr in zip(IDEOLOGY_LABELS, IDEOLOGY_LABELS_FR):
        outlets_in = sorted(name for name, l in labels.items() if l == lbl)
        print(f"  {lbl:<14} {lbl_fr:<14}  {', '.join(outlets_in) if outlets_in else '(none)'}")


def compute_wiki_scores(outlets: list) -> dict:
    """
    Extract Wikipedia-coded orientations (d6b_source.wiki_coded) and
    z-standardize them across outlets that have a value.
    Returns {outlet_name: {"raw": float, "z": float, "label": str, "quote": str}}
    for covered outlets; missing outlets are absent from the dict.

    Labels use the same ±0.25σ / ±0.75σ / ±1.5σ nested cuts as the model
    fallback, so the two labels are directly comparable.
    """
    raw = {}
    quotes = {}
    for o in outlets:
        val = o.get("d6b_source", {}).get("wiki_coded")
        if val is not None:
            raw[o["name"]] = val
            quotes[o["name"]] = o.get("d6b_source", {}).get("wiki_quote", "")[:70]

    if len(raw) < 2:
        return {}

    vals = list(raw.values())
    mean_w = sum(vals) / len(vals)
    std_w = statistics.pstdev(vals) or 1.0

    # Same nested sigma-band cuts as the main model 7-label fallback
    cuts = [-1.5, -0.75, -0.25, 0.25, 0.75, 1.5]

    def assign_label(z):
        for i, cut in enumerate(cuts):
            if z < cut:
                return IDEOLOGY_LABELS[i]
        return IDEOLOGY_LABELS[-1]

    result = {}
    for name, r in raw.items():
        z = (r - mean_w) / std_w
        result[name] = {
            "raw":   r,
            "z":     round(z, 3),
            "label": assign_label(z),
            "quote": quotes.get(name, ""),
        }
    return result


def print_wiki_comparison(outlets: list, scored: dict, model_labels: dict,
                           cutoffs: list, wiki_scores: dict):
    """
    Side-by-side: V2 model score+label vs Wikipedia score+label.

    Both use ±0.25σ / ±0.75σ / ±1.5σ nested cuts on their respective
    z-standardised scores.
    'AGREE' = both assign the same label.
    'ADJ'   = labels are adjacent (e.g. left vs center) — within-1-category disagreement.
    'DIFF'  = labels differ by ≥2 categories.
    """
    label_idx = {lbl: i for i, lbl in enumerate(IDEOLOGY_LABELS)}

    print(f"\n{'='*115}")
    print("  WIKIPEDIA vs V2 MODEL — Label & Score Comparison")
    print("  Label methodology: both use ±0.25σ / ±0.75σ / ±1.5σ nested sigma-band cuts")
    print(f"  V2 cut-points: {', '.join(f'{c:+.3f}' for c in cutoffs)}")
    print("  Wiki cut-points: −1.500 / −0.750 / −0.250 / +0.250 / +0.750 / +1.500 (fixed)")
    print(f"{'='*115}")
    print(f"  {'Outlet':<22} {'V2(z)':>7} {'V2 label':<12} {'Wiki(z)':>7} {'Wiki label':<12} {'Match':>6}  Wikipedia quote")
    print(f"  {'-'*112}")

    agree = adj = diff = skipped = 0
    for outlet in sorted(outlets, key=lambda o: scored[o["name"]]["final"]):
        name = outlet["name"]
        v2z = scored[name]["final"]
        v2lbl = model_labels.get(name, "?")

        if name not in wiki_scores:
            print(f"  {name:<22} {v2z:>+7.3f} {v2lbl:<12} {'—':>7} {'(no wiki)':<12} {'—':>6}")
            skipped += 1
            continue

        w = wiki_scores[name]
        wz = w["z"]
        wlbl = w["label"]
        quote = w["quote"]

        gap = abs(label_idx.get(v2lbl, 2) - label_idx.get(wlbl, 2))
        if gap == 0:
            match_str = "AGREE"
            agree += 1
        elif gap == 1:
            match_str = "adj"
            adj += 1
        else:
            match_str = f"DIFF({gap})"
            diff += 1

        print(f"  {name:<22} {v2z:>+7.3f} {v2lbl:<12} {wz:>+7.3f} {wlbl:<12} {match_str:>6}  {quote}")

    n_compared = agree + adj + diff
    print(f"\n  AGREE: {agree}/{n_compared} ({100*agree/n_compared:.0f}%)  "
          f"ADJ (±1 cat): {adj}/{n_compared}  "
          f"DIFF (≥2 cat): {diff}/{n_compared}  "
          f"No wiki: {skipped}")


def print_borderline_cases(outlets: list, scored: dict, labels: dict, cutoffs: list):
    """
    Outlets within 0.1σ of any label boundary — label is a precision artifact, not a strong claim.
    Also surfaces outlets with data_quality_flag=True and their label_note.
    """
    flagged_notes = [(o["name"], o.get("label_note", "")) for o in outlets if o.get("data_quality_flag") and o.get("label_note")]
    borderline = []
    for name, s in scored.items():
        f = s["final"]
        min_gap = min(abs(f - cut) for cut in cutoffs)
        if min_gap < 0.1:
            nearest_cut = min(cutoffs, key=lambda c: abs(f - c))
            left_lbl = IDEOLOGY_LABELS[cutoffs.index(nearest_cut)]
            right_lbl = IDEOLOGY_LABELS[cutoffs.index(nearest_cut) + 1]
            borderline.append((name, f, min_gap, left_lbl, right_lbl, labels.get(name)))

    if not borderline and not flagged_notes:
        return

    print("\n  BORDERLINE CASES & DATA QUALITY FLAGS")
    print("  ─────────────────────────────────────────────────────────────────")
    if borderline:
        print("  Within 0.1σ of a label boundary (label is a precision artifact):")
        for name, f, gap, l_lbl, r_lbl, assigned in sorted(borderline, key=lambda x: x[2]):
            print(f"    {name:<22} z={f:+.3f}  gap={gap:.3f}σ  assigned={assigned}  boundary={l_lbl}|{r_lbl}")
    if flagged_notes:
        print("\n  Data quality flags (! outlets):")
        for name, note in flagged_notes:
            print(f"    {name:<22} {note[:95]}")


def print_sensitivity(loo: dict, rho_bootstrap: float):
    print("\n  SENSITIVITY ANALYSIS")
    print("  ──────────────────────────────────────────────────")
    print("  Leave-one-family-out Spearman ρ (vs full model):")
    for key, v in loo.items():
        rho = v.get("rho")
        n_aff = v.get("n_outlets_affected", "?")
        rho_str = f"{rho:.4f}" if rho is not None else "FAILED"
        flag = " ✓" if (rho is not None and rho >= 0.90) else " ✗"
        print(f"    {key:<15}: ρ = {rho_str}{flag}  (affects {n_aff} outlets)")
    print(f"  Bootstrap weight-perturbation rank stability ρ: {rho_bootstrap:.4f}")


def write_results_csv(outlets: list, scored: dict, sigma: dict, bootstrap_stats: dict, labels: dict, cutoffs: list):
    path = RESULTS_DIR / "scores_v2.csv"
    cutoff_str = "|".join(f"{c:.4f}" for c in cutoffs)
    fam_cols = [f"{f}_z" for f in DIRECT_FAMILIES]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "outlet",
            "z_direct", "z_structural", "z_blended", "n_direct",
            "final_score_z", "sigma", "ci_low_95", "ci_high_95",
            "bootstrap_mean", "bootstrap_std", "bootstrap_ci_low", "bootstrap_ci_high",
            "label", "label_cutoffs",
        ] + fam_cols + ["axis_crossing", "data_quality_flag"])
        for outlet in sorted(outlets, key=lambda o: scored[o["name"]]["final"]):
            name = outlet["name"]
            s = scored[name]
            sig = sigma[name]
            final = s["final"]
            bs = bootstrap_stats.get(name, {})
            prof = s["evidence_profile"]
            fam_vals = [round(prof.get(f), 4) if prof.get(f) is not None else "" for f in DIRECT_FAMILIES]
            w.writerow([
                name,
                round(s["z_direct"], 4) if s["z_direct"] is not None else "",
                round(s["z_structural"], 4),
                round(s["z_blended"], 4),
                s["n_direct"],
                round(final, 4),
                round(sig, 4),
                round(final - 1.96 * sig, 4),
                round(final + 1.96 * sig, 4),
                round(bs.get("mean", final), 4),
                round(bs.get("std", 0), 4),
                round(bs.get("ci_low", final - 1.96 * sig), 4),
                round(bs.get("ci_high", final + 1.96 * sig), 4),
                labels.get(name, ""),
                cutoff_str,
            ] + fam_vals + [
                outlet.get("axis_crossing", False),
                bool(outlet.get("data_quality_flag")),
            ])
    return path


def try_plot(outlets, scored, sigma, bootstrap_stats, loo_results, labels, cutoffs, kde_data):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("  (matplotlib not installed; skipping plots)")
        return

    plots_dir = RESULTS_DIR / "plots"
    plots_dir.mkdir(exist_ok=True)

    outlets_sorted = sorted(outlets, key=lambda o: scored[o["name"]]["final"])
    names = [o["name"] for o in outlets_sorted]
    final = [scored[n]["final"] for n in names]
    sigs = [sigma[n] for n in names]
    bs = bootstrap_stats

    # Label → color
    label_colors = {
        "far-left":  "#1a3a6b",
        "left":      "#1a6bb0",
        "center":    "#888888",
        "right":     "#b01a1a",
        "far-right": "#6b0000",
    }

    # ── Plot 1: V2 ideology scores (z-standardized) ────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 10))
    y_pos = range(len(names))

    # Draw label bands as background
    x_min_plot = min(final) - 1.5
    x_max_plot = max(final) + 1.5
    band_cuts = [x_min_plot] + cutoffs + [x_max_plot]
    band_alphas = [0.06, 0.05, 0.03, 0.03, 0.04, 0.05, 0.06]
    band_facecolors = ["#1a3a6b", "#1a6bb0", "#888888", "#aaaaaa", "#b01a1a", "#8b0000", "#6b0000"]
    for i, (lbl, fa, fc) in enumerate(zip(IDEOLOGY_LABELS, band_alphas, band_facecolors)):
        ax.axvspan(band_cuts[i], band_cuts[i + 1], alpha=fa, color=fc, zorder=0)
        mid = (band_cuts[i] + band_cuts[i + 1]) / 2
        ax.text(mid, len(names) + 0.3, lbl, ha="center", va="bottom", fontsize=8,
                color=fc, fontweight="bold", alpha=0.7)

    bar_colors = [label_colors.get(labels.get(n, "center"), "#888") for n in names]
    ax.barh(list(y_pos), final, color=bar_colors, alpha=0.65, height=0.55)

    for i, (n, f, sig) in enumerate(zip(names, final, sigs)):
        b_stat = bs.get(n, {})
        ci_lo = b_stat.get("ci_low", f - 1.96 * sig)
        ci_hi = b_stat.get("ci_high", f + 1.96 * sig)
        ax.plot([ci_lo, ci_hi], [i, i], color="#333", lw=1.8, zorder=5)
        ax.scatter(0, i, marker="|", color="#aaa", s=40, zorder=4, alpha=0.5)

        n_d = scored[n]["n_direct"]
        ax.text(
            f + 0.05 if f >= 0 else f - 0.05, i,
            f"n={n_d}",
            va="center", ha="left" if f >= 0 else "right",
            fontsize=7, color="#666",
        )

    for cut in cutoffs:
        ax.axvline(cut, color="#aaa", lw=0.8, ls="--", zorder=1)

    ax.axvline(0, color="#666", lw=1.0, ls="--", zorder=2)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel(f"Ideology Score (SD units, mean=0 across {len(names)} outlets)", fontsize=10)
    ax.set_title(
        "V2 Latent Ideology Scores — bars=final (z-std), lines=95% bootstrap CI",
        fontsize=11,
    )
    ax.set_xlim(x_min_plot, x_max_plot)

    legend_elements = [
        mpatches.Patch(color="#1a3a6b", label="far-left"),
        mpatches.Patch(color="#1a6bb0", label="left"),
        mpatches.Patch(color="#888888", label="center"),
        mpatches.Patch(color="#b01a1a", label="right"),
        mpatches.Patch(color="#6b0000", label="far-right"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
    plt.tight_layout()
    fig.savefig(plots_dir / "ideology_scores_v2.png", dpi=150, bbox_inches="tight")
    fig.savefig(plots_dir / "ideology_scores_v2.pdf", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {plots_dir / 'ideology_scores_v2.png'}")

    # ── Plot 2: Evidence coverage heatmap ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 10))
    cmap = {
        None: "#eeeeee",
        "D0": "#FF5722", "D1": "#2196F3", "D2": "#4CAF50", "D3": "#FF9800",
        "D4": "#9C27B0", "D6a": "#795548", "D6b": "#607D8B",
        "D7": "#009688", "D8": "#F06292",
    }
    for i, outlet in enumerate(outlets_sorted):
        name = outlet["name"]
        prof = scored[name]["evidence_profile"]
        for j, fam in enumerate(DIRECT_FAMILIES):
            val = prof.get(fam)
            color = cmap[fam] if val is not None else "#eeeeee"
            ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color, alpha=0.8))
            if val is not None:
                ax.text(j + 0.5, i + 0.5, f"{val:+.1f}",
                        ha="center", va="center", fontsize=7, color="white", fontweight="bold")

    ax.set_xlim(0, len(DIRECT_FAMILIES))
    ax.set_ylim(0, len(names))
    ax.set_xticks([j + 0.5 for j in range(len(DIRECT_FAMILIES))])
    ax.set_xticklabels([
        "D0\nOwner\n(struct)", "D1\nGuest\n(Cagé)", "D2\nSurvey\n(Pew)",
        "D3\nNetwork\n(Cointet)", "D4\nMBFC",
        "D6a\nSelf-\ndecl.", "D6b\n3rd\nparty", "D7\nContent\n(ours)",
        "D8\nAF\n(AdFontes)",
    ])
    ax.set_yticks([i + 0.5 for i in range(len(names))])
    ax.set_yticklabels(names, fontsize=8)
    ax.set_title("Evidence Coverage Matrix (z-scores; grey=NA)", fontsize=10)
    plt.tight_layout()
    fig.savefig(plots_dir / "evidence_coverage_v2.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {plots_dir / 'evidence_coverage_v2.png'}")

    # ── Plot 4: KDE density with label cut-points ──────────────────────────────
    x_grid, density, bw = kde_data
    fig, ax = plt.subplots(figsize=(10, 4))

    # Label background bands
    x_arr = x_grid
    dens_arr = density
    band_cuts_kde = [x_arr[0]] + list(cutoffs) + [x_arr[-1]]
    for i, (lbl, fa, fc) in enumerate(zip(IDEOLOGY_LABELS, band_alphas, band_facecolors)):
        ax.axvspan(band_cuts_kde[i], band_cuts_kde[i + 1], alpha=fa * 1.5, color=fc, zorder=0)

    ax.plot(x_arr, dens_arr, color="#333", lw=2.0, zorder=3)
    ax.fill_between(x_arr, dens_arr, alpha=0.12, color="#555", zorder=2)

    for cut in cutoffs:
        ax.axvline(cut, color="#888", lw=1.2, ls="--", zorder=4)

    # Rug plot of individual outlet scores
    for name, s in scored.items():
        f = s["final"]
        lbl = labels.get(name, "center")
        ax.plot(f, 0, "|", color=label_colors.get(lbl, "#888"), ms=12, mew=1.5, zorder=5)

    # Label annotations at top
    for i, lbl in enumerate(IDEOLOGY_LABELS):
        mid = (band_cuts_kde[i] + band_cuts_kde[i + 1]) / 2
        ax.text(mid, max(dens_arr) * 0.95, lbl, ha="center", va="top",
                fontsize=9, color=band_facecolors[i], fontweight="bold", alpha=0.8)

    ax.set_xlabel("Ideology Score (SD units, mean=0)", fontsize=10)
    ax.set_ylabel(f"KDE density (bw={bw:.3f})", fontsize=9)
    ax.set_title("Outlet Ideology Distribution — KDE with label cut-points", fontsize=10)
    ax.set_xlim(x_arr[0], x_arr[-1])
    plt.tight_layout()
    fig.savefig(plots_dir / "kde_label_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {plots_dir / 'kde_label_distribution.png'}")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading v2 data...")
    data = load_v2_data()
    outlets = data["outlets"]
    print(f"Loaded {len(outlets)} outlets.")

    # Inject D0 (ownership ideology) into each outlet's direct dict
    inject_d0(outlets)

    # Inject D3 continuous PPR positions (overrides JSON categorical values)
    inject_d3_ppr(outlets)

    # Inject D7 endorsed lexical scores from CSV (overrides JSON D7 values)
    inject_d7(outlets)

    # Inject D8 Ad Fontes Media ratings from GN scrape
    inject_d8_af(outlets)

    # Coverage report
    print("\n  Evidence coverage:")
    for fam in DIRECT_FAMILIES:
        n_covered = sum(1 for o in outlets if o["direct"].get(fam) is not None)
        print(f"    {fam}: {n_covered}/{len(outlets)} outlets")

    # Steps 1-4: standardize families → compute latent scores (z_blended per outlet)
    z_matrix = build_standardized_matrix(outlets)
    latent = compute_latent_scores(outlets, z_matrix)

    # Step 5: z-standardize to mean=0, SD=1 (no anchor forcing)
    scored, mean_z, std_z, scale_factor = standardize_final(latent)
    sigma = compute_uncertainty(outlets, scored, scale_factor)

    # Step 6: KDE label assignment
    cutoffs, labels, kde_data = compute_labels(scored)

    print_main_table(outlets, scored, sigma, labels, (mean_z, std_z))
    print_label_summary(labels, cutoffs)

    # Wikipedia comparison (inline)
    wiki_scores = compute_wiki_scores(outlets)
    print_wiki_comparison(outlets, scored, labels, cutoffs, wiki_scores)

    # Borderline cases + quality flags
    print_borderline_cases(outlets, scored, labels, cutoffs)

    # Anchor post-hoc validation
    print("\n  ANCHOR VALIDATION (post-hoc, not calibration):")
    anchor_check = validate_anchors(outlets, scored)
    for name, info in anchor_check.items():
        status = "✓" if info["ok"] else "⚠"
        print(f"    {status} {name}: expected {info['expected_extreme']}, "
              f"rank={info['actual_rank']}, score={info['final']:+.3f}")

    # Bootstrap
    print(f"\n  Running bootstrap (n={N_BOOTSTRAP})...")
    bootstrap_stats = perturb_shrinkage_bootstrap(outlets, N_BOOTSTRAP)

    # Rank stability from bootstrap
    base_scores = [scored[o["name"]]["final"] for o in outlets]
    rho_bootstrap_vals = []
    rng = random.Random(RANDOM_SEED + 1)
    for _ in range(N_BOOTSTRAP):
        lam = max(0.1, SHRINKAGE_LAMBDA * (1 + rng.uniform(-0.5, 0.5)))
        z_p = {
            fam: {n: z + rng.gauss(0, FAMILY_SIGMA[fam] * 0.3) for n, z in z_matrix[fam].items()}
            for fam in DIRECT_FAMILIES
        }
        lat_p = compute_latent_scores(outlets, z_p, shrinkage_lambda=lam)
        sc_p, _, _, _ = standardize_final(lat_p)
        pert_scores = [sc_p[o["name"]]["final"] for o in outlets]
        rho_bootstrap_vals.append(spearman_rho(base_scores, pert_scores))

    rho_bootstrap = sum(rho_bootstrap_vals) / len(rho_bootstrap_vals) if rho_bootstrap_vals else float("nan")
    rho_bootstrap_min = min(rho_bootstrap_vals) if rho_bootstrap_vals else float("nan")
    pct_above_95 = sum(1 for r in rho_bootstrap_vals if r >= 0.95) / len(rho_bootstrap_vals) if rho_bootstrap_vals else float("nan")

    # Leave-one-out sensitivity
    print("  Running leave-one-family-out sensitivity...")
    loo = leave_one_out_sensitivity(outlets)
    print_sensitivity(loo, rho_bootstrap)

    # Write bootstrap stats to file for manuscript verification
    import json as _json
    bootstrap_out = {
        "rho_mean": round(rho_bootstrap, 4),
        "rho_min": round(rho_bootstrap_min, 4),
        "pct_above_0_95": round(pct_above_95, 4),
        "n_iterations": len(rho_bootstrap_vals),
    }
    bootstrap_out_path = RESULTS_DIR / "bootstrap_stats.json"
    with open(bootstrap_out_path, "w") as _f:
        _json.dump(bootstrap_out, _f, indent=2)
    print(f"  Saved bootstrap stats: {bootstrap_out_path}")

    # Conflict flags
    print("\n  CONFLICT FLAGS:")
    conflict_pairs = [
        ("Marianne", "D3=−2.0 from 2018-19 network data; post-2020 sovereignist shift not captured"),
        ("Le Parisien", "LVMH ownership (D0 +0.47z) vs commercial-centrist content (D3, D4, D6a/b all near 0)"),
        ("Libération", "D3=0 (Hyper-centre network block) vs D4=−1 (MBFC Left-Center)"),
    ]
    for outlet_name, msg in conflict_pairs:
        v2f = scored[outlet_name]["final"]
        lbl = labels.get(outlet_name, "?")
        print(f"    {outlet_name}: V2={v2f:+.3f}SD, label={lbl} — {msg}")

    # Write outputs
    csv_path = write_results_csv(outlets, scored, sigma, bootstrap_stats, labels, cutoffs)
    print(f"\n  Saved: {csv_path}")

    print("\n  Generating plots...")
    try_plot(outlets, scored, sigma, bootstrap_stats, loo, labels, cutoffs, kde_data)

    # Final paper table
    print(f"\n{'='*90}")
    print("  PAPER TABLE — V2 Results (z-standardized scale, mean=0, SD=1)")
    print(f"{'='*90}")
    print(f"  {'Outlet':<22} {'Score (z)':>9} {'95% CI':>20}  {'n_D':>4}  {'Label':<12}  Support")
    print("-" * 90)
    for o in sorted(outlets, key=lambda x: scored[x["name"]]["final"]):
        name = o["name"]
        s = scored[name]
        f = s["final"]
        sig = sigma[name]
        bs_s = bootstrap_stats.get(name, {})
        ci_lo = bs_s.get("ci_low", f - 1.96 * sig)
        ci_hi = bs_s.get("ci_high", f + 1.96 * sig)
        n_d = s["n_direct"]
        prof = s["evidence_profile"]
        direct_used = [fam for fam in DIRECT_FAMILIES if prof.get(fam) is not None]
        direct_str = ", ".join(direct_used) if direct_used else "none"
        lbl = labels.get(name, "?")
        print(f"  {name:<22} {f:>+9.3f}  [{ci_lo:+.3f}, {ci_hi:+.3f}]  {n_d:>4}  {lbl:<12}  {direct_str}")

    print(f"\n  Scale: mean={mean_z:+.4f}, SD={std_z:.4f} (of blended scores pre-standardization)")
    print(f"  Labels: KDE valley cut-points at {', '.join(f'{c:+.3f}' for c in cutoffs)}")

    # ── D0 ablation: compare with-D0 vs without-D0 ────────────────────────────
    print(f"\n{'='*100}")
    print("  D0 ABLATION — WITH D0 (ownership as direct indicator) vs WITHOUT D0 (prior-only)")
    print(f"{'='*100}")
    families_no_d0 = [f for f in DIRECT_FAMILIES if f != "D0"]
    z_no_d0 = build_standardized_matrix(outlets, families=families_no_d0)
    lat_no_d0 = compute_latent_scores(outlets, z_no_d0, families=families_no_d0)
    scored_no_d0, _, _, _ = standardize_final(lat_no_d0)
    cutoffs_no_d0, labels_no_d0, _ = compute_labels(scored_no_d0)

    names_sorted = sorted(outlets, key=lambda o: scored[o["name"]]["final"])
    with_scores  = [scored[o["name"]]["final"] for o in names_sorted]
    without_scores = [scored_no_d0[o["name"]]["final"] for o in names_sorted]
    rho_d0 = spearman_rho(with_scores, without_scores)

    # Build rank dicts for shift computation
    rank_with    = {o["name"]: i + 1 for i, o in enumerate(names_sorted)}
    names_no_d0  = sorted(outlets, key=lambda o: scored_no_d0[o["name"]]["final"])
    rank_without = {o["name"]: i + 1 for i, o in enumerate(names_no_d0)}

    print(f"  Spearman ρ (with D0 vs without D0): {rho_d0:.4f}")
    print(f"  {'Outlet':<22} {'WithD0':>8} {'WithoutD0':>10}  {'Δscore':>8}  {'ΔRank':>6}  {'LabelShift'}")
    print(f"  {'-'*85}")
    for o in names_sorted:
        name = o["name"]
        s_with    = scored[name]["final"]
        s_without = scored_no_d0[name]["final"]
        delta     = s_with - s_without
        rank_delta = rank_with[name] - rank_without[name]
        lbl_with    = labels.get(name, "?")
        lbl_without = labels_no_d0.get(name, "?")
        shift_str   = f"{lbl_without} → {lbl_with}" if lbl_with != lbl_without else "—"
        print(f"  {name:<22} {s_with:>+8.3f} {s_without:>+10.3f}  {delta:>+8.3f}  {rank_delta:>+6}  {shift_str}")

    print(f"\n  Done. Results in: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
