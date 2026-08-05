# Unidimensionality Validation Report

Generated: unidimensional_validation.py
Outlet count: 30
Family count: 9

## 1. Pairwise Family Correlations

| Family pair | Pearson r | n |
|------------|-----------|----|
| D0 vs D1 | 0.983 | 3 |
| D1 vs D7 | 0.960 | 3 |
| D2 vs D6b | 0.953 | 6 |
| D6b vs D8 | 0.949 | 7 |
| D0 vs D6b | 0.944 | 25 |
| D6b vs D7 | 0.924 | 27 |
| D2 vs D6a | 0.908 | 3 |
| D0 vs D7 | 0.901 | 28 |
| D0 vs D8 | 0.895 | 9 |
| D4 vs D7 | 0.884 | 15 |
| D2 vs D7 | 0.880 | 8 |
| D6a vs D6b | 0.875 | 18 |
| D4 vs D6b | 0.871 | 14 |
| D0 vs D6a | 0.870 | 16 |
| D0 vs D4 | 0.859 | 14 |
| D3 vs D6a | 0.843 | 18 |
| D1 vs D3 | 0.840 | 3 |
| D4 vs D6a | 0.827 | 9 |
| D6a vs D7 | 0.809 | 18 |
| D7 vs D8 | 0.801 | 9 |
| D3 vs D6b | 0.798 | 27 |
| D2 vs D8 | 0.791 | 5 |
| D0 vs D2 | 0.777 | 8 |
| D3 vs D7 | 0.771 | 30 |
| D4 vs D8 | 0.767 | 7 |
| D2 vs D4 | 0.763 | 5 |
| D0 vs D3 | 0.746 | 28 |
| D2 vs D3 | 0.732 | 8 |
| D3 vs D4 | 0.713 | 15 |
| D3 vs D8 | 0.577 | 9 |
| D1 vs D2 | NA | 2 |
| D1 vs D4 | NA | 1 |
| D1 vs D6a | NA | 1 |
| D1 vs D6b | NA | 2 |
| D1 vs D8 | NA | 1 |
| D6a vs D8 | NA | 4 |

Mean r (all pairs): 0.840
Min r: 0.577, Max r: 0.983

## 2. PCA on High-Coverage Families

Families: ['D0', 'D3', 'D4', 'D6a', 'D6b', 'D7']
Complete-case outlets: 8 — 20 Minutes, France 24, Franceinfo, Le Parisien, Marianne, Mediapart, RFI, Valeurs actuelles

| Component | Eigenvalue | Variance % | Cumulative % |
|-----------|-----------|-----------|-------------|
| PC1 | 4.9177 | 88.9% | 88.9% |
| PC2 | 0.2728 | 4.9% | 93.9% |
| PC3 | 0.2544 | 4.6% | 98.5% |
| PC4 | 0.0619 | 1.1% | 99.6% |
| PC5 | 0.0230 | 0.4% | 100.0% |
| PC6 | 0.0004 | 0.0% | 100.0% |

### PC1 Loadings

- **D3**: -1.0553
- **D7**: -1.0250
- **D0**: -0.9703
- **D6a**: -0.8260
- **D6b**: -0.8098
- **D4**: -0.6885

### PC2 Loadings

- **D4**: -0.4470
- **D6b**: +0.1811
- **D6a**: +0.1625
- **D0**: +0.1050
- **D7**: -0.0463
- **D3**: -0.0261

Spearman ρ(PC1, final FrIdéo score): -0.9762

## 3. PCA on Core Families (D0, D3, D6b, D7)

Complete-case outlets: 25

- PC1: λ=3.5989, var=88.5%, cum=88.5%
- PC2: λ=0.3026, var=7.4%, cum=95.9%
- PC3: λ=0.1095, var=2.7%, cum=98.6%
- PC4: λ=0.0555, var=1.4%, cum=100.0%

### PC1 Loadings

- **D0**: -1.0214
- **D6b**: -0.9653
- **D7**: -0.9494
- **D3**: -0.8499

### PC2 Loadings

- **D3**: -0.4917
- **D7**: +0.1454
- **D0**: +0.1431
- **D6b**: +0.1384

### PC1 vs PC2 Projections

| Outlet | PC1 | PC2 | Final score |
|--------|-----|-----|-------------|
| 20 Minutes | +0.367 | -0.447 | -0.314 |
| Blast | +2.901 | +0.470 | -1.647 |
| CNews | -2.208 | +0.701 | +0.957 |
| Causeur | -2.969 | -0.473 | +1.531 |
| Challenges | +0.080 | -0.172 | -0.105 |
| France 24 | -0.215 | -0.348 | -0.026 |
| Franceinfo | +0.277 | -0.393 | -0.411 |
| JDD | -2.628 | +1.263 | +0.955 |
| L'Express | -0.697 | -0.015 | +0.178 |
| L'Humanité | +4.460 | +0.783 | -2.412 |
| L'Opinion | -1.073 | +0.087 | +0.599 |
| La Croix | -0.038 | -0.100 | +0.125 |
| Le Figaro | -1.680 | +0.422 | +1.024 |
| Le Monde | +1.078 | -0.514 | -0.707 |
| Le Nouvel Obs | +1.284 | -0.793 | -0.894 |
| Le Parisien | -0.288 | -0.071 | +0.103 |
| Le Point | -0.949 | +0.015 | +0.563 |
| Les Echos | -0.630 | +0.251 | +0.429 |
| Libération | +1.318 | -0.794 | -1.080 |
| Marianne | +0.834 | +1.069 | -0.651 |
| Mediapart | +3.276 | +0.354 | -1.634 |
| Ouest-France | +0.136 | -0.312 | -0.162 |
| RFI | +0.054 | -0.092 | -0.108 |
| Slate.fr | +1.078 | -0.613 | -0.529 |
| Valeurs actuelles | -3.769 | -0.275 | +1.872 |

## 4. Economic vs Cultural Axis Test


### Target outlets in PC1-PC2 space

| Outlet | PC1 | PC2 | Final | D0 | D3 | D6b | D7 |
|--------|-----|-----|-------|----|----|-----|-----|
| L'Humanité | +4.460 | +0.783 | -2.412 | -2.42 | -2.86 | -2.11 | -1.89 |
| Mediapart | +3.276 | +0.354 | -1.634 | -1.51 | -1.95 | -1.67 | -1.76 |
| Blast | +2.901 | +0.470 | -1.647 | -1.51 | -1.88 | -1.67 | -1.08 |
| Libération | +1.318 | -0.794 | -1.080 | -0.49 | -0.05 | -1.23 | -1.10 |
| Le Monde | +1.078 | -0.514 | -0.707 | -1.06 | -0.18 | -0.78 | -0.34 |
| Le Nouvel Obs | +1.284 | -0.793 | -0.894 | -1.06 | -0.03 | -0.78 | -0.89 |
| Slate.fr | +1.078 | -0.613 | -0.529 | -0.49 | -0.10 | -0.78 | -1.02 |
| Franceinfo | +0.277 | -0.393 | -0.411 | -0.15 | +0.06 | -0.34 | -0.39 |
| 20 Minutes | +0.367 | -0.447 | -0.314 | -0.15 | +0.07 | -0.34 | -0.57 |
| Le Parisien | -0.288 | -0.071 | +0.103 | +0.54 | +0.03 | -0.34 | +0.04 |
| Ouest-France | +0.136 | -0.312 | -0.162 | -0.15 | +0.05 | +0.10 | -0.54 |
| La Croix | -0.038 | -0.100 | +0.125 | +0.20 | -0.06 | +0.10 | -0.46 |
| L'Express | -0.697 | -0.015 | +0.178 | +0.42 | +0.17 | +0.10 | +0.41 |
| Les Echos | -0.630 | +0.251 | +0.429 | +0.54 | -0.11 | +0.54 | -0.05 |
| Le Point | -0.949 | +0.015 | +0.563 | +0.65 | +0.25 | +0.54 | +0.15 |
| Marianne | +0.834 | +1.069 | -0.651 | +0.20 | -1.50 | -0.34 | -0.47 |
| JDD | -2.628 | +1.263 | +0.955 | +1.56 | -0.11 | +1.42 | +1.94 |
| Le Figaro | -1.680 | +0.422 | +1.024 | +0.99 | +0.21 | +0.98 | +0.82 |
| CNews | -2.208 | +0.701 | +0.957 | +1.56 | +0.19 | +1.42 | +0.83 |
| Causeur | -2.969 | -0.473 | +1.531 | +1.22 | +1.60 | +1.42 | +1.46 |
| Valeurs actuelles | -3.769 | -0.275 | +1.872 | +2.13 | +1.77 | +1.42 | +1.92 |
| RFI | +0.054 | -0.092 | -0.108 | -0.15 | -0.10 | -0.34 | +0.20 |
| France 24 | -0.215 | -0.348 | -0.026 | -0.15 | +0.25 | -0.34 | +0.43 |
| Challenges | +0.080 | -0.172 | -0.105 | -0.49 | -0.04 | +0.10 | +0.02 |
| L'Opinion | -1.073 | +0.087 | +0.599 | +0.42 | +0.24 | +0.54 | +0.64 |

### PC2 loadings interpretation

- D0 (ownership/economic) loading: +0.1431
- D6b (third-party/cultural) loading: +0.1384
- D7 (content/lexical) loading: +0.1454
- D3 (network) loading: -0.4917

## 5. Second-Dimension Impact Assessment

- PC1 variance explained: 88.5%
- PC2 variance explained: 7.4%
- PC1/PC2 ratio: 11.9x

### Verdict

PC2 explains < 10% of variance — second dimension is negligible.
**Conclusion: Strongly supports unidimensionality.**

## 6. Within-domain vs Between-domain Agreement

- Mean within-group |r|: varies by group (see console)
- Mean between-group |r|: 0.837

Between-group correlations are strong — different methodological families converge on the same latent dimension.
