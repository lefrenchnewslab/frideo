"""Quick verification of key paper numbers against output files.

Run from the `replication/` directory, or via `make check`:
    cd replication && python3 scripts/pipeline_check.py
"""
import json, csv, sys
from pathlib import Path

if not Path("results/scores_v2.csv").exists():
    sys.exit("Run this from the 'replication/' directory (or use 'make check'):\n"
             "    cd replication && python3 scripts/pipeline_check.py")

def ok(cond, msg):
    status = "OK  " if cond else "FAIL"
    print(f"  {status}  {msg}")
    return cond

def cohen_kappa(a, b):
    n = len(a)
    labels = sorted(set(a) | set(b))
    from collections import Counter as C
    cm = C(zip(a, b))
    po = sum(cm[(l, l)] for l in labels) / n
    pa = {l: a.count(l)/n for l in labels}
    pb = {l: b.count(l)/n for l in labels}
    pe = sum(pa[l] * pb[l] for l in labels)
    return (po - pe) / (1 - pe)

def norm_label(v):
    v = v.strip().upper()
    if v in ('PLAIN', 'ENDORSES'): return 'PLAIN'
    if v in ('QUALIFIED', 'REPORTS_OR_CRITIQUES', 'DISTANCED'): return 'QUALIFIED'
    return v

scores = {r['outlet']: r for r in csv.DictReader(open('results/scores_v2.csv'))}
boot   = json.load(open('results/bootstrap_stats.json'))
loo    = {r['family_dropped']: r for r in csv.DictReader(open('results/loo_absolute_shifts.csv'))}
mbfc   = json.load(open('results/mbfc_validation.json'))
sig    = json.load(open('results/family_sigma.json'))
exp_a  = json.load(open('results/exp_a/exp_a_summary.json'))
# No-prior refit (Appendix E) — guards the anti-circularity claim: removing the
# structural prior must leave the three prior-dependent sparse outlets' labels
# intact, and must move only L'Express and Causeur panel-wide.
try:
    noprior = json.load(open('results/no_prior_refit.json'))
except FileNotFoundError:
    noprior = None
# JDD Bolloré trajectory (Table tab:jdd).
jdd    = json.load(open('results/jdd_bollore_trajectory.json'))['periods']
jdd_pre  = jdd['PRE']['d7_raw']
jdd_h2   = jdd['2023-H2 (Aug–Dec)']['d7_raw']
jdd_h1   = jdd['2024-H1 (Jan–Jun)']['d7_raw']
# λ (shrinkage) sensitivity (§6.3) — guards the robustness claim.
lam      = json.load(open('results/lambda_sensitivity.json'))
lam_shift_max = max(lam['max_abs_shift'].values())
lam_chg_1 = lam['n_label_changes']['1']
lam_chg_3 = lam['n_label_changes']['3']
lam_chg_3_who = [c['outlet'] for c in lam['label_changes']['3']]
lam_chg_1_who = [c['outlet'] for c in lam['label_changes']['1']]
lam_dist_ok = (lam['label_distribution']['2'] == [11, 8, 11]
               and lam['label_distribution']['3'] == [11, 8, 11]
               and lam['label_distribution']['1'] == [11, 7, 12])  # sole λ=1 deviation = L'Express, asserted below
# D3 provenance (Table families): D3 is OUR dual-PPR score over Cointet's web-link
# network for 28 outlets; 2 (Blast, Franceinfo, absent from the 2019 crawl) keep a
# categorical fallback. Guards the paper's "30/30 (28 PPR + 2 categorical fallback)"
# against silent drift in the PPR coverage.
d3_ppr_rows  = list(csv.DictReader(open('results/cointet_d3_continuous.csv')))
d3_ppr_n     = sum(1 for r in d3_ppr_rows if r['ppr_z_panel'].strip())
d3_fallback  = sorted(r['outlet'] for r in d3_ppr_rows if not r['ppr_z_panel'].strip())
d3_loo_n     = int(loo['D3']['n_outlets_with_family'])

gold_rows = list(csv.DictReader(open('results/exp_a/exp_a_gold_430.csv')))
d7_labels   = [norm_label(r['d7_label'])   for r in gold_rows]
llm_labels  = [norm_label(r['llm_label'])  for r in gold_rows]
gold_labels = [norm_label(r['gold_label']) for r in gold_rows]
kappa_d7_gold  = cohen_kappa(d7_labels, gold_labels)
kappa_llm_gold = cohen_kappa(llm_labels, gold_labels)
kappa_d7_llm   = cohen_kappa(d7_labels, llm_labels)
# Human-adjudicated rows only. On auto rows the gold IS D7's output, so
# agreement there is definitional; this is the figure the paper calls honest.
_hum = [i for i, r in enumerate(gold_rows) if r['gold_source'].strip().startswith('human')]
kappa_d7_gold_human = cohen_kappa([d7_labels[i] for i in _hum],
                                  [gold_labels[i] for i in _hum])
# Gold-count reconciliation (§5 + Appendix H): the gold standard is
# 312 auto + 118 adjudicated = 430; the probe runs on all 430 (all embeddable).
gold_n      = len(gold_rows)
gold_agree  = sum(1 for r in gold_rows if r['gold_source'].strip() == 'auto')
gold_adj    = sum(1 for r in gold_rows if r['gold_source'].strip().startswith('human'))
gold_d7llm_dis = sum(1 for a, b in zip(d7_labels, llm_labels) if a != b)
# Period stability (§6.3 / tab:period): D7 2024 vs 2025 rank correlation.
period_rho  = json.load(open('results/d7_period_stability_summary.json'))['rho_2024_vs_2025']
# All-cat vs politique agreement (Appendix D7): rank correlation across outlets
# scorable under both windows.
def _spearman(a, b):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i]); r = [0]*len(v)
        for k, i in enumerate(s): r[i] = k
        return r
    ra, rb = rank(a), rank(b); n = len(a)
    ma = sum(ra)/n; mb = sum(rb)/n
    num = sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    den = (sum((x-ma)**2 for x in ra)*sum((x-mb)**2 for x in rb))**0.5
    return num/den if den else 0.0
_ac  = {r['outlet_json_name']: float(r['d5_raw']) for r in csv.DictReader(open('results/d5_score_d5_allcat_2024-2025_endorsed.csv'))}
_pol = {r['outlet_json_name']: float(r['d5_raw']) for r in csv.DictReader(open('results/d5_score_d5_politique_pooled_all_current_endorsed.csv'))}
_common = sorted(set(_ac) & set(_pol))
allcat_pol_rho = _spearman([_ac[o] for o in _common], [_pol[o] for o in _common])
allcat_pol_n = len(_common)

hum = float(scores["L'Humanité"]['final_score_z'])
va  = float(scores['Valeurs actuelles']['final_score_z'])
loo_min_rho   = min(float(r['spearman_rho']) for r in loo.values())
loo_max_shift = max(float(r['max_abs_shift_all']) for r in loo.values())
rho_mbfc = mbfc.get('no_d4_vs_mbfc_rho', 0)
labels = [r['label'] for r in scores.values()]
n_cl = sum(1 for l in labels if l in ('far-left','left','center-left'))
n_cr = sum(1 for l in labels if l in ('far-right','right','center-right'))
n_c  = sum(1 for l in labels if l == 'center')
# D7 null set — every outlet must carry a D7 score on the all-category window.
# A non-empty list here means the D7 corpus no longer covers the full panel.
d7_null = sorted(o for o, r in scores.items() if not r['D7_z'].strip())

print("\n=== Key paper numbers ===")
results = [
    # Targets are the published 30-outlet, all-category 2024–2025 values.
    ok(abs(hum - (-2.410)) < 0.005,  f"L'Humanité score:     {hum:+.3f}   (paper: -2.41)"),
    ok(abs(va  -   1.870)  < 0.005,  f"Valeurs actuelles:    {va:+.3f}   (paper: +1.87)"),
    ok(abs(boot['rho_mean'] - 0.9962) < 0.0015, f"Bootstrap rho mean:   {boot['rho_mean']:.4f}  (paper: 0.996)"),
    ok(abs(boot['rho_min']  - 0.9884) < 0.004,  f"Bootstrap rho min:    {boot['rho_min']:.4f}  (paper: 0.988)"),
    ok(abs(loo_min_rho   - 0.992) < 0.0015,    f"Min LOO rho:          {loo_min_rho:.4f}  (paper: 0.992)"),
    ok(abs(loo_max_shift - 0.270) < 0.005,     f"Max LOO shift:        {loo_max_shift:.4f}  (paper: 0.27σ)"),
    ok(abs(rho_mbfc - 0.9182) < 0.0015,        f"MBFC rho (no-D4):     {rho_mbfc:.4f}  (paper: 0.918)"),
    ok(mbfc['exact_match'] == 6,                f"MBFC exact match:     {mbfc['exact_match']}/15   (paper: 6/15)"),
    ok(abs(sig['D7'] - 0.42) < 0.01,           f"D7 sigma_k:           {sig['D7']:.4f}  (paper: 0.42)"),
    ok(n_cl==11 and n_c==8 and n_cr==11,        f"Label distribution:   {n_cl}/{n_c}/{n_cr}   (paper: 11/8/11)"),
    ok(d7_null == [],                           f"D7 null set:          {d7_null}   (paper: none — 30/30 scored, all-cat)"),
    ok(abs(kappa_d7_llm - 0.4267) < 0.005,
                                                f"Exp A κ (D7 vs LLM):  {kappa_d7_llm:.4f}  (paper: 0.43)"),
    ok(abs(kappa_d7_gold  - 0.9377) < 0.005,   f"D7 vs gold κ:         {kappa_d7_gold:.4f}  (paper: 0.938)"),
    ok(abs(kappa_d7_gold_human - 0.7758) < 0.005,
                                                f"D7 vs gold κ (human): {kappa_d7_gold_human:.4f}  (paper: 0.78)"),
    ok(abs(kappa_llm_gold - 0.4851) < 0.005,   f"LLM vs gold κ:        {kappa_llm_gold:.4f}  (paper: 0.49)"),
    # JDD all-category trajectory (Table tab:jdd): pre-overhaul net-left, sharp
    # rightward shift at the June 2023 Bolloré takeover.
    ok(abs(jdd_pre - (-0.160)) < 0.005,        f"JDD pre-overhaul:     {jdd_pre:+.3f}  (paper: -0.160)"),
    ok(abs(jdd_h2  -   0.298)  < 0.005,        f"JDD 2023-H2:          {jdd_h2:+.3f}  (paper: +0.298)"),
    ok(abs(jdd_h1  -   0.573)  < 0.005,        f"JDD 2024-H1:          {jdd_h1:+.3f}  (paper: +0.573)"),
    # λ sensitivity (§6.3): scores barely move; 3-way split invariant; only L'Express
    # crosses a band boundary at λ=1 (it is 'center' at the adopted λ=2).
    ok(lam_shift_max < 0.08,                    f"λ max |Δ score|:      {lam_shift_max:.4f}σ  (paper: <0.08σ)"),
    ok(lam_dist_ok,                             "λ split:              11/8/11 at λ=2,3; 11/7/12 at λ=1 (L'Express)  (paper: §6.3)"),
    ok(lam_chg_3 == 0 and lam_chg_1 == 1 and lam_chg_1_who == ["L'Express"],
                                                f"λ label changes:      λ1={lam_chg_1}, λ3={lam_chg_3} {lam_chg_1_who}  (paper: only L'Express@λ1)"),
    # D3 provenance: 28 PPR-derived + 2 categorical fallback (Blast, Franceinfo); populated 30/30.
    ok(d3_ppr_n == 28 and d3_fallback == ['Blast', 'Franceinfo'],
                                                f"D3 PPR coverage:      {d3_ppr_n}/30 PPR, fallback {d3_fallback}  (paper: 28 PPR + 2 fallback)"),
    ok(d3_loo_n == 30,                          f"D3 populated (LOO n): {d3_loo_n}/30   (paper: 30/30)"),
    # Gold counts (§5 / Appendix H): 312 auto + 118 adjudicated = 430; probe on all 430.
    ok(gold_n == 430 and gold_agree == 312 and gold_adj == 118,
                                                f"Gold standard:        {gold_agree}+{gold_adj}={gold_n}  (paper: 312+118=430)"),
    ok(gold_d7llm_dis == 118,                   f"D7-LLM disagreements: {gold_d7llm_dis}/430   (paper: 118/430)"),
    # Period stability (§6.3 / tab:period): 2024 vs 2025.
    ok(abs(period_rho - 0.9524) < 0.002,        f"D7 period rho:        {period_rho:.4f}  (paper: 0.95)"),
    # All-cat vs politique agreement (Appendix D7).
    ok(abs(allcat_pol_rho - 0.89) < 0.01 and allcat_pol_n == 25,
                                                f"all-cat vs politique: rho={allcat_pol_rho:.3f} n={allcat_pol_n}  (paper: 0.89, 25)"),
    # No-prior refit (Appendix E): the sparse outlets keep their labels without
    # the prior, so the face-validity agreement is not circular.
    ok(noprior is not None and noprior['all_prior_dependent_sparse_labels_held'],
                                                "No-prior refit:       Blast/HuffPost/Atlantico labels held  (paper: App. E)"
                                                if noprior else
                                                "No-prior refit:       results/no_prior_refit.json missing — run `make all`"),
    ok(noprior is not None
       and sorted(c['outlet'] for c in noprior['label_changes']) == ["Causeur", "L'Express"],
                                                f"No-prior label chgs:  {sorted(c['outlet'] for c in noprior['label_changes']) if noprior else '—'}  (paper: only L'Express, Causeur)"),
]
print()
n_fail = results.count(False)
if n_fail:
    print(f"  {n_fail} FAILURE(S)")
    sys.exit(1)
else:
    print("  All numeric checks passed.")
