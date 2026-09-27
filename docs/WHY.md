# Why factorlab exists

The statistical controls that keep backtests honest are published but hard to obtain. Purged and
embargoed cross-validation comes from López de Prado (2018), the deflated Sharpe ratio from Bailey and
López de Prado (2014), and false-discovery-rate control from Benjamini and Hochberg (1995). The
reference implementation, MlFinLab, is all rights reserved: commercial use requires a paid licence at
£100 per month per user, the source may not be redistributed, and published derivatives are
prohibited. The free alternatives, the Quantopian stack (alphalens, pyfolio, empyrical), have no
commits on their default branches since 2020 and never contained any of these methods.

factorlab reimplements a narrow slice of that literature from first principles under MIT: a purged
walk-forward splitter with an explicit embargo, Benjamini-Hochberg and Bonferroni correction across a
screened family, a Wilson lower-bound hit-rate test, a deflated Sharpe ratio, and a promotion gate that
returns reject when any single criterion fails. The statistics are written without scipy so every
formula can be read and checked.

It deliberately does not do bar construction, triple-barrier labelling, meta-labeling, feature
engineering, model training, portfolio construction, or execution. It ships 13 factors, reads CSV or
generates a synthetic panel, and makes no claim to be a research platform. Its thresholds are
documented defaults, not calibrated market truths.
