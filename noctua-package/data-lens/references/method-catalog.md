# data-lens method catalog

The routing table for the automatic pass and for every dialogue turn: the **question** an analyst asks, the **method** that answers it, the **assumptions** the method makes, the **check** that tests them (what `analysis.py` / a cell runs), the **effect size** that must accompany the result, and the **robust alternative** the script switches to when the check fails. A method not in this table may be used in a turn, with the same six columns filled in the turn's `method` block.

Conventions: α = 0.05 on the *adjusted* p-value; the family for correction is the set of tests run to answer one question (all group comparisons of one module, all pairwise contrasts of one omnibus test); Benjamini–Hochberg across exploratory families, Holm within a pre-declared one; confidence intervals at 95%, bootstrap (BCa, 2000 resamples, seeded) when no closed form is trusted; n < 30 per group makes every parametric result `low` confidence regardless of p.

## Quality

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Is missingness in X related to other columns? | chi-square of the missing indicator against each nominal; Mann–Whitney of each numeric by missingness | expected counts ≥ 5 | expected-count table | Cramér's V; rank-biserial r | Fisher exact for small tables |
| Are these rows duplicates? | exact match on all columns; near-match on the basis with per-column tolerances | — | — | share of rows | — |
| Is this column what its type says? | parse rate under the declared type; pattern census | — | — | share unparsable | — |
| Are values within plausible ranges? | range and unit checks from meaning (negative counts, percentages > 100, dates in the future) | — | — | share out of range | — |

## Distributions

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Is X normal? | Shapiro–Wilk (n ≤ 5000), D'Agostino K² otherwise | i.i.d. sample | — | skew, excess kurtosis | QQ reading; never a p alone |
| Does X have outliers? | IQR fence, MAD (3.5), isolation forest (contamination auto) — agreement count | continuous X | modality check first (bimodal X fools the fences) | share flagged, max |z| | per-group fences when a nominal explains the modes |
| Is X multimodal? | KDE peak count with bandwidth scan | continuous X | — | number of modes, separation | — |
| Should X be transformed? | skew and heteroscedasticity vs the label; Box-Cox λ estimate | X > 0 for Box-Cox | sign check | skew before/after | Yeo–Johnson for non-positive X |

## Relations

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Are X and Y monotonically related? | Spearman ρ, Kendall τ | paired observations | — | ρ, τ with CI | — |
| Is X related to Y controlling for Z? | partial Spearman | linearity of the rank relation | residual plot reading | partial ρ | conditional mutual information |
| Is there redundancy among features? | VIF on the basis numerics | linear model | — | VIF | condition number from the geometry layer (already there — cite it) |
| Do X and Z interact on the label? | screen: label ~ X + Z + X·Z, likelihood-ratio test | model family fits | residual check | ΔR² or Δdeviance | tree-based interaction strength (H-statistic) |

## Inference — group comparisons

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Does numeric Y differ across two groups? | Welch t | approximate normality within groups, or n ≥ 30 per group | Shapiro per group; QQ | Cohen's d (Hedges g for small n) with CI | Mann–Whitney, rank-biserial r; permutation test |
| … across k > 2 groups? | Welch ANOVA | as above | Shapiro per group; Levene | ω² | Kruskal–Wallis, ε²; then pairwise Dunn with Holm |
| Which groups differ? | Games–Howell pairwise (after Welch ANOVA) | as above | — | pairwise d | Dunn with Holm |
| Are nominal X and Y associated? | chi-square | expected counts ≥ 5 | expected-count table | Cramér's V (bias-corrected) | Fisher exact (2×2), Monte-Carlo chi-square |
| Do proportions differ? | two-proportion z, or chi-square | n·p ≥ 5 | — | risk difference, odds ratio with CI | Fisher exact |
| Is the label imbalanced enough to matter? | class shares; expected baseline accuracy | — | — | minority share | stratified split candidate for the shaper |
| Paired before/after? | paired t | normality of differences | Shapiro on differences | d_z | Wilcoxon signed-rank |

## Segments

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Are there natural groups in the basis? | k-means k = 2..8 on standardized basis numerics; agglomerative (Ward) as cross-check | numeric basis, scale-comparable | silhouette across k; stability under 20 bootstrap resamples (ARI) | silhouette, ARI | Gower distance + PAM when nominals are in the basis |
| What is a segment, in the data's own terms? | per-segment profile: medians, dominant categories, label rate | — | — | standardized differences from the whole | — |

## Importance (on the chosen partition only)

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Is the task learnable from the basis? | stratified 5-fold CV of a regularized linear model and a gradient-boosting model | features = partition's `features` minus the leakage set | leakage probe: importance collapse when the label's derivation columns are removed; near-perfect CV score is itself a warning | CV score with CI vs the baseline (majority / mean) | time-based folds when a datetime orders the rows |
| Which features carry it? | permutation importance (10 repeats) on the held-out folds | as above | — | mean decrease with CI | SHAP when installed, else grouped permutation for correlated features |
| More data or better features? | learning curve at 10–100 % of train | as above | — | slope at the last point | — |

## Time series (only with a datetime column)

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Is the series regular? | gap census on the sorted index | — | — | share of gaps, largest gap | resample to the modal interval, count imputed points |
| Is there a trend? | Theil–Sen slope with CI; Mann–Kendall | monotone trend | — | slope per unit time | — |
| Is there seasonality? | STL at the detected period (ACF peak) | regular series | period stability across halves | seasonal strength (Hyndman) | — |
| Is it stationary? | ADF and KPSS together | — | — | — | the four-way reading (both / neither / one of the two) is the answer, not a p |
| Where does it change? | PELT change points (penalty BIC) | — | — | number of segments, mean shift | — |
| What does this mean for splitting? | — | — | — | — | time-based split candidate for the shaper; lag features from the ACF |

## Spatial (only with a coordinate pair or geometry)

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Are the coordinates sane? | range check in the declared CRS; axis-order check (lat/lon swapped) | a CRS | — | share out of bounds | `crs: unknown` → only the range check |
| Does location carry signal? | Moran's I of each numeric basis member on a k-NN weight matrix (k = 8) | projected coordinates (metres) | — | I with pseudo-p (999 permutations) | Geary's C |
| Are there spatial clusters? | DBSCAN in metres (eps from the k-distance knee) | metric CRS | — | number of clusters, share of noise | HDBSCAN when installed |
| Are points duplicated in space? | exact and within-r duplicate locations | — | — | share | — |

## Drift (only with a split)

| question | method | assumptions | check | effect size | robust alternative |
|---|---|---|---|---|---|
| Does numeric X drift between parts? | KS two-sample; PSI (10 quantile bins) | — | — | KS D; PSI (0.1 / 0.25 thresholds) | Wasserstein distance |
| Does nominal X drift? | chi-square on the part × category table | expected counts ≥ 5 | — | Cramér's V; PSI | Fisher / Monte-Carlo |
| Does the label rate drift? | two-proportion z | — | — | risk difference with CI | — |

## What is not answered here

Causal effects on observational data (only associations, with the caveat written), forecasts (a trend reading is not a forecast), and anything about the ontology's rules and classes — that is `/model-chat`, which runs the engines.
