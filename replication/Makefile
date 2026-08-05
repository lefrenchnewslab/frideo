# FrIdéo pipeline
#
#   make scores   rebuild results/scores_v2.csv from the evidence inputs
#   make all      scores + every sensitivity and validation run
#   make check    verify the paper's headline numbers against the outputs
#   make clean    delete regenerated outputs (shipped inputs are untouched)
#
# Timestamp-based: each target re-runs only when something upstream changed.

# Do not litter the release tree with __pycache__/*.pyc. Running `make check` or
# `make all` from a shipped copy otherwise leaves compiled bytecode behind, which
# then travels in any re-packaged archive.
export PYTHONDONTWRITEBYTECODE := 1

PYTHON := python3

# ── Shipped inputs — never generated here ───────────────────────────────────
EVIDENCE   := data/outlets_evidence_v2.json
D3         := results/cointet_d3_continuous.csv
GN         := gn/gn_bias_ratings.json
D7         := results/d5_score_d5_allcat_2024-2025_endorsed.csv
D7_PERIOD  := results/d7_period_stability.csv
INPUTS     := $(EVIDENCE) $(D3) $(GN) $(D7)

# ── Generated outputs ────────────────────────────────────────────────────────
SIGMA      := results/family_sigma.json
SCORES     := results/scores_v2.csv
LOO        := results/loo_absolute_shifts.csv
MBFC       := results/mbfc_validation.json
MBFC_IND   := results/mbfc_independent_validation.json
D4_ABL     := results/d4_ablation.json
KNOWNGRP   := results/known_groups_validation.json
COV        := results/covariance_sensitivity.csv
LAMBDA     := results/lambda_sensitivity.json
XFAM       := results/cross_family_corr.csv
UNI        := results/unidimensional_validation_report.md
KDE        := results/kde_bandwidth_sensitivity.json
SHARES     := results/family_contribution_shares.csv
PERIOD_PM  := results/d7_period_vs_fullmodel.csv
NOPRIOR    := results/no_prior_refit.json

.PHONY: all scores check clean

all: $(LOO) $(MBFC) $(MBFC_IND) $(D4_ABL) $(KNOWNGRP) $(COV) $(LAMBDA) \
     $(XFAM) $(UNI) $(KDE) $(SHARES) $(PERIOD_PM) $(NOPRIOR)
	@echo
	@echo "Pipeline complete. Run 'make check' to verify the paper's numbers."

# Always re-runs. `results/scores_v2.csv` ships up-to-date, so a plain
# file-dependency here would report "Nothing to be done" on a fresh clone —
# which is not what the README promises. `all` still uses the file target
# below, so the dependency graph is unaffected.
scores: $(SIGMA)
	$(PYTHON) analysis_v2.py

# ── Per-family measurement error, from leave-one-out residual variance ───────
$(SIGMA): $(INPUTS) scripts/estimate_sigma_empirical.py
	$(PYTHON) scripts/estimate_sigma_empirical.py

# ── Core pipeline: fuse families, shrink, bootstrap, label ──────────────────
# Also writes bootstrap_stats.json and results/plots/*.
$(SCORES): $(INPUTS) $(SIGMA) analysis_v2.py
	$(PYTHON) analysis_v2.py

$(LOO):      $(SCORES) scripts/loo_absolute_shifts.py
	$(PYTHON) scripts/loo_absolute_shifts.py

$(MBFC):     $(SCORES) scripts/validate_mbfc.py
	$(PYTHON) scripts/validate_mbfc.py

$(MBFC_IND): $(SCORES) scripts/validate_mbfc_independent.py
	$(PYTHON) scripts/validate_mbfc_independent.py

$(D4_ABL):   $(SCORES) scripts/ablate_mbfc.py
	$(PYTHON) scripts/ablate_mbfc.py

$(KNOWNGRP): $(D4_ABL) scripts/known_groups_validation.py
	$(PYTHON) scripts/known_groups_validation.py

$(COV):      $(SCORES) $(SIGMA) scripts/covariance_sensitivity.py
	$(PYTHON) scripts/covariance_sensitivity.py

$(LAMBDA):   $(SCORES) scripts/lambda_sensitivity.py
	$(PYTHON) scripts/lambda_sensitivity.py

$(XFAM):     $(SCORES) scripts/cross_family_convergence.py
	$(PYTHON) scripts/cross_family_convergence.py

$(UNI):      $(SCORES) $(XFAM) scripts/unidimensional_validation.py
	$(PYTHON) scripts/unidimensional_validation.py

$(KDE):      $(SCORES) scripts/kde_bandwidth_sensitivity.py
	$(PYTHON) scripts/kde_bandwidth_sensitivity.py

$(SHARES):   $(SCORES) scripts/compute_family_shares.py
	$(PYTHON) scripts/compute_family_shares.py

$(PERIOD_PM): $(SCORES) $(D7_PERIOD) scripts/d7_period_vs_fullmodel_stability.py
	$(PYTHON) scripts/d7_period_vs_fullmodel_stability.py

# Appendix E: refit with the structural prior removed, to test whether the
# sparse outlets' label agreement is circular.
$(NOPRIOR):  $(SCORES) scripts/no_prior_refit.py
	$(PYTHON) scripts/no_prior_refit.py

check:
	@$(PYTHON) scripts/pipeline_check.py

# Removes only what `make all` regenerates. The shipped inputs listed at the top
# of this file — including the D7 scores, which cannot be rebuilt without the
# article corpus — are never touched.
clean:
	rm -f $(SIGMA) $(SCORES) results/bootstrap_stats.json $(LOO) $(MBFC) \
	      $(MBFC_IND) $(D4_ABL) $(KNOWNGRP) $(COV) $(LAMBDA) \
	      results/lambda_sensitivity.csv $(XFAM) results/cross_family_pca.json \
	      $(UNI) $(KDE) results/kde_bandwidth_sensitivity.csv \
	      $(SHARES) results/family_shares_long.csv $(PERIOD_PM) $(NOPRIOR) \
	      results/plots/*.png results/plots/*.pdf
	@echo "Removed regenerated outputs. Run 'make all' to rebuild."
