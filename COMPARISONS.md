# Comparisons

Factual comparison against the three tools people actually ask about. Every cell was checked against
source or official pages fetched on **2026-09-26** (sources at the bottom). Cells that could not be
verified say `unverified`. Star counts are GitHub API values on that date.

| | Licence | Maintained? | Purged/embargoed CV | Multiple-testing correction | Deflated Sharpe | Promotion gate that rejects | Runnable offline |
|---|---|---|---|---|---|---|---|
| **MlFinLab** (Hudson & Thames) | All rights reserved, not open source. Commercial use needs a paid licence; Business tier is **£100 (+VAT) per month, per user** | Commercial product; public repo last pushed **2023-10-02** (4,933 stars) | **Yes** — purged K-fold and combinatorial purged CV (AFML ch. 7) | **Yes** — Bonferroni, Holm and BHY adjustments in the Sharpe-haircut and profit-hurdle algorithms | **Yes** | **No** — threshold helpers (profit hurdles, minimum track record), but no accept/reject verdict API in the public source; the current paid package was not inspected (`unverified`) | **Yes**, local install |
| **Quantopian stack** (alphalens / pyfolio / empyrical) | Apache-2.0 (all three) | **No** — last commits on the default branch: alphalens 2020-04-27, pyfolio 2020-02-28, empyrical 2020-10-14. Not archived | **No** — no purged or embargo code | **No** — no Benjamini-Hochberg, Bonferroni or FDR code | **No** | **No** — metrics and tear sheets only | **Yes** |
| **qlib** (Microsoft) | MIT | **Yes** — 48,876 stars, last push **2026-09-22** | **No** — no purged/embargo/walk-forward code or docs | **No** | **No** — plain Sharpe ratios only | **No** — experiment tracking and metrics, no accept/reject gate | Only after downloading its dataset (`scripts/get_data.py`); then yes |
| **purgedcv** (eslazarev) | MIT | **Yes** — v0.0.2, PyPI 2025-04-16; 35 stars, JOSS paper submitted | **Yes** — `PurgedKFold`, `WalkForwardSplit`, `CombinatorialPurgedCV` with full embargo support | **No** — no BH/Bonferroni across a factor family; only single-strategy DSR/PSR | **Yes** — `deflated_sharpe_ratio` and `probabilistic_sharpe_ratio` fully implemented | **No** — a CV/statistics library only; no factor computation, no IC, no quantile spread, no accept/reject gate | **Yes** — offline, pure time-series inputs |
| **ml4t-diagnostic** (ml4t org) | MIT | **Yes** — active 2026, 32 stars, part of a 7-library ML4T ecosystem | **Yes** — `WalkForwardCV`, `CombinatorialCV`, purge + embargo + CPCV | **Yes** — FDR control, White's Reality Check, DSR, PBO | **Yes** | **No** — metrics and tearsheets; no standalone accept/reject gate | **Partial** — requires Polars; optional Numba/LightGBM/SHAP extras; 7-library ecosystem is a hard dependency chain |
| **pyanomaly** (chulwoohan) | MIT | **Partial** — v1.01 2024-03-13, 132 stars; no commits since | **No** — no purged or embargo CV | **No** | **No** | **No** — quantile portfolios and factor regression; no promotion verdict | **No** — requires a WRDS subscription for all data; no offline synthetic path |
| **factorproof** (this repo) | MIT | Yes — v0.1.0, active development | **Yes** — `PurgedWalkForward`: label-overlap purge plus an explicit embargo | **Yes** — Benjamini-Hochberg (primary) and Bonferroni, applied inside the gate across the screened family | **Yes** — implemented and property-tested; *not* wired into the default gate | **Yes** — 10 checks, all must pass, exit code 1 on reject, no `--force` | **Yes** — synthetic OHLCV built in, CSV loader, no network calls |

## Where MlFinLab wins

MlFinLab is more complete than this repository, and by a wide margin. It ships data structures
(tick/volume/dollar bars), labelling (triple-barrier, meta-labeling), filters and feature
engineering (fractional differentiation), sample weighting, bet sizing, feature importance,
ensembles, clustering (ONC), codependence measures, networks, synthetic data generation, and a
backtest-overfitting module that adds probability-of-backtest-overfitting analysis, profit hurdles,
haircut Sharpe and minimum track record length on top of the deflated Sharpe. It is documented per
function with example notebooks and lecture videos, and it has been used in production by paying
customers. It also has a real Sharpe-ratio haircut; this repo computes a deflated Sharpe but does not
haircut Sharpe ratios or compute PBO. If you can pay and you need breadth, MlFinLab is the better
tool. The point of this repository is narrower: the four controls in the table above, under a licence
you can actually read, fork and ship.

qlib wins on everything this repo does not attempt: a full research platform, data ingestion for
Chinese equities, model zoos, experiment management and a large contributor base. It simply does not
implement overfitting-control statistics.

The Quantopian stack wins on ecosystem familiarity and history — alphalens' tear sheets are still the
mental model most people have for factor analysis. Community forks (`stefan-jansen/alphalens-reloaded`,
657 stars; `pyfolio-reloaded`, 616; `empyrical-reloaded`, 122, all pushed December 2025) keep them
installable on modern Python, and a source check confirms the forks add none of the four features
either.

## Where this repo loses

- 13 factors and one CSV/synthetic data path. No bars, no labelling, no ML models, no portfolio
  construction, no live or paper trading.
- No haircut Sharpe, no probability of backtest overfitting, no minimum track record length.
- The deflated Sharpe exists as a tested function but is not part of the promotion verdict; the gate
  uses IC, Wilson lower bound, walk-forward sign consistency, turnover and FDR.
- Thresholds are documented defaults, not calibrated on live market data.
- No production history. MlFinLab has paying users; this has a test suite.

## Sources (fetched 2026-09-26)

- MlFinLab licence: https://github.com/hudson-and-thames/mlfinlab/blob/master/LICENSE.txt (clauses 6.6, 6.7, 14.3–14.5)
- MlFinLab "NOT open-source" statement: https://github.com/hudson-and-thames/mlfinlab/blob/master/docs/source/index.rst
- MlFinLab pricing and module list: https://hudsonthames.org/mlfinlab/ (Business tier £100 +VAT per month per user)
- MlFinLab repo metadata and source (purged CV, BHY, haircut, deflated Sharpe): GitHub API + `master` tarball
- alphalens / pyfolio / empyrical metadata, licences, last default-branch commits: GitHub API and commits API
- qlib metadata: https://api.github.com/repos/microsoft/qlib ; feature search: `master` checkout, no matches for purged/embargo/deflated/Benjamini/"false discovery"/walk-forward
- purgedcv repo: https://github.com/eslazarev/purged-cross-validation (35 stars, MIT, JOSS paper, v0.0.2 PyPI 2025-04-16); feature list verified against README and API summary table
- ml4t-diagnostic repo: https://github.com/ml4t/diagnostic (32 stars, MIT, active 2026); feature list from README capability table and ecosystem description
- pyanomaly repo: https://github.com/chulwoohan/pyanomaly (132 stars, MIT, v1.01 2024-03-13); WRDS requirement from README installation instructions; feature gaps confirmed by source search for "purge", "embargo", "false discovery", "Wilson"
- Topic sizes (GitHub search API, same date) used for `launch/topics.txt`

## Choose this when…

- **MlFinLab** — you need a broad, documented financial-ML library, you have budget, and a
  non-redistributable licence with no published derivatives is acceptable for your organisation.
- **Quantopian stack** — you want a tear-sheet for factor or portfolio analysis and none of the
  overfitting controls, and you are willing to live with 2020-era code or a community fork.
- **qlib** — you want an end-to-end ML research platform with data pipelines and experiment
  tracking, and overfitting statistics are handled elsewhere.
- **purgedcv** — you are building a sklearn-compatible ML pipeline and want correct time-series
  CV splits with CPCV and PBO baked in. You do not need IC measurement or a factor gate.
- **ml4t-diagnostic** — you have already committed to the ML4T seven-library ecosystem, use Polars,
  and want tearsheets alongside validation. The ecosystem overhead is acceptable.
- **pyanomaly** — you have a WRDS subscription and want to replicate academic equity anomalies
  against CRSP/Compustat firm characteristics. Real data, academic scope, no overfitting controls.
- **factorproof** — you want purged walk-forward CV, multiple-testing correction, a deflated Sharpe
  and a gate that says no, under MIT, offline, inspectable, with no subscription.
