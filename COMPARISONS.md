# Comparisons

Factual comparison against the tools people actually ask about. Every cell was checked against
source or official pages. Cells that could not be verified say `unverified`. Star counts are GitHub
API values on **2026-10-29** (latest re-verification; prior runs: 2026-09-26, 2026-09-27, 2026-10-12, 2026-10-13T11:00 UTC, 2026-10-13T13:00 UTC, 2026-10-14 ~10:30 UTC, 2026-10-27).

| | Licence | Maintained? | Purged/embargoed CV | Multiple-testing correction | Deflated Sharpe | Promotion gate that rejects | Runnable offline |
|---|---|---|---|---|---|---|---|
| **MlFinLab** (Hudson & Thames) | All rights reserved, not open source. Commercial use needs a paid licence; Business tier is **£100 (+VAT) per month, per user** | Commercial product; public repo last pushed **2023-10-02** (**4,959** stars as of 2026-10-29; no code push since 2023-10-02) | **Yes** — purged K-fold and combinatorial purged CV (AFML ch. 7) | **Yes** — Bonferroni, Holm and BHY adjustments in the Sharpe-haircut and profit-hurdle algorithms | **Yes** | **No** — threshold helpers (profit hurdles, minimum track record), but no accept/reject verdict API in the public source; the current paid package was not inspected (`unverified`) | **Yes**, local install |
| **Quantopian stack** (alphalens / pyfolio / empyrical) | Apache-2.0 (all three) | **No** — last releases 2019–2020 (alphalens **v0.4.0** 2020-04-30, pyfolio **0.9.2** 2019-04-15, empyrical **0.5.5** 2020-10-13); branch-tip pushes 2023–2024 are churn, not development. Not archived | **No** — no purged or embargo code | **No** — no Benjamini-Hochberg, Bonferroni or FDR code | **No** | **No** — metrics and tear sheets only | **Yes** |
| **qlib** (Microsoft) | MIT | **Yes** — **49,796** stars, **v0.9.8** released **2026-10-08**, last push **2026-10-22** (as of 2026-10-29; platform release, no overfitting-statistics module) | **No** — no purged/embargo/walk-forward code or docs | **No** | **No** — plain Sharpe ratios only | **No** — experiment tracking and metrics, no accept/reject gate | Only after downloading its dataset (`scripts/get_data.py`); then yes |
| **purgedcv** (eslazarev) | MIT | **Yes** — **v0.1.11** (PyPI, released 2026-10-16); **59** stars as of 2026-10-29 (first release 2026-05-16, 24 releases); JOSS paper | **Yes** — `PurgedKFold`, `WalkForwardSplit`, `CombinatorialPurgedCV` with full embargo support | **No** — no BH/Bonferroni/BY across a factor family (README grep at 0.1.11: 0 hits); its DSR is single-search only | **Yes** — `deflated_sharpe_ratio`, `deflated_sharpe_ratio_full`, PBO and minimum backtest length (0.1.11) | **No** — a CV/statistics library only; no factor computation, no IC, no verdict API (README grep: 0 hits) | **Yes** — offline, pure time-series inputs |
| **ml4t-diagnostic** (ml4t org) | MIT | **Yes** — **39** stars, **v0.2.0** (2026-10-27), last push **2026-10-27** (as of 2026-10-29) | **Yes** — `WalkForwardCV`, `CombinatorialCV`, purge + embargo + CPCV | **Yes** — HAC-adjusted IC t-stat, FDR control, White's Reality Check, DSR, PBO | **Yes** | **No** — `analyze_signal` returns a result object with IC/FDR metrics; no binary accept/reject gate, no exit code (README grep at 0.2.0: 0 hits) | **Partial** — Polars is a required input (not optional); optional Numba/LightGBM/SHAP extras; 7-library ecosystem |
| **pyanomaly** (chulwoohan) | MIT | **Partial** — **132** stars as of 2026-10-29; last push 2024-03-13; no commits since | **No** — no purged or embargo CV | **No** | **No** | **No** — quantile portfolios and factor regression; no promotion verdict | **No** — requires a WRDS subscription for all data; no offline synthetic path |
| **vectorbt** (polakowo) | Commons Clause v1.0 (not standard OSS — the licence does not grant the right to Sell) | **Yes** — **9,582** stars, **v1.2.0** (PyPI, 2026-10-19), last push **2026-10-28** (as of 2026-10-29) | **No** — README grep: 0 hits for purge/embargo | **No** — 0 hits for Benjamini/FDR | **No** — 0 hits for deflated | **No** — a backtesting/parameter-sweep engine; no factor verdict | **Yes** |
| **quantstats** (ranaroussi) | Apache-2.0 | **Yes** — **7,762** stars, **v0.0.86** (PyPI, 2026-09-27), last push **2026-09-27** (as of 2026-10-29) | **No** — README grep: 0 hits for purge/embargo | **No** — 0 hits for Benjamini/FDR | **No** — 0 hits for deflated | **No** — reporting tear sheets only; no validation of any kind | **Yes** |
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
**681** stars; `pyfolio-reloaded`, **619**; `empyrical-reloaded`, **131**, all pushed **2026-10-26**) keep them
installable on modern Python. Source re-check 2026-10-13 (after all three moved that morning) confirms the forks add none of the four features
either.

vectorbt and quantstats win on volume (9,582 and 7,762 stars) — the backtesting-engine and
reporting tiers respectively. Neither ships purge/embargo, FDR or a deflated Sharpe (README
greps at their current releases, 2026-10-29: all zero), and vectorbt's Commons Clause licence
forbids commercial redistribution.

## Where this repo loses

- 13 factors and one CSV/synthetic data path. No bars, no labelling, no ML models, no portfolio
  construction, no live or paper trading.
- No haircut Sharpe, no probability of backtest overfitting, no minimum track record length.
- The deflated Sharpe exists as a tested function but is not part of the promotion verdict; the gate
  uses IC, Wilson lower bound, walk-forward sign consistency, turnover and FDR.
- Thresholds are documented defaults, not calibrated on live market data.
- No production history. MlFinLab has paying users; this has a test suite.

## Sources (fetched 2026-09-26; star counts and last-push dates re-verified 2026-10-29)

- MlFinLab licence: https://github.com/hudson-and-thames/mlfinlab/blob/master/LICENSE.txt (clauses 6.6, 6.7, 14.3–14.5)
- MlFinLab "NOT open-source" statement: https://github.com/hudson-and-thames/mlfinlab/blob/master/docs/source/index.rst
- MlFinLab pricing and module list: https://hudsonthames.org/mlfinlab/ (Business tier £100 +VAT per month per user)
- MlFinLab repo metadata and source (purged CV, BHY, haircut, deflated Sharpe): GitHub API + `master` tarball
- alphalens / pyfolio / empyrical metadata, licences, last default-branch commits, release tags (v0.4.0 / 0.9.2 / 0.5.5): GitHub API and releases API
- qlib metadata: https://api.github.com/repos/microsoft/qlib ; feature search: `master` checkout, no matches for purged/embargo/deflated/Benjamini/"false discovery"/walk-forward
- purgedcv repo: https://github.com/eslazarev/purged-cross-validation (59 stars, MIT, JOSS paper, v0.1.11 PyPI 2026-10-16); feature list verified against README and API summary table; 0.1.11 README grepped 2026-10-29 for verdict/accept-reject/exit/FDR terms (all zero)
- ml4t-diagnostic repo: https://github.com/ml4t/diagnostic (39 stars, MIT, v0.2.0 PyPI 2026-10-27); README greped at 0.2.0 for gate/verdict/exit-code/promotion terms (all zero); release notes read (annualization/snapshot/calibration fixes)
- pyanomaly repo: https://github.com/chulwoohan/pyanomaly (132 stars, MIT, v1.01 2024-03-13); WRDS requirement from README installation instructions; feature gaps confirmed by source search for "purge", "embargo", "false discovery", "Wilson"
- vectorbt repo/licence: https://github.com/polakowo/vectorbt (9,582 stars; Commons Clause v1.0 via GitHub /license API); PyPI v1.2.0 uploaded 2026-10-19; README greped 2026-10-29 (purge/embargo, FDR, deflated all zero)
- quantstats repo: https://github.com/ranaroussi/quantstats (7,762 stars, Apache-2.0); PyPI v0.0.86 uploaded 2026-09-27; README greped 2026-10-29 (same three classes all zero)
- PyPI release histories: https://pypi.org/pypi/<pkg>/json for purgedcv, ml4t-diagnostic, vectorbt, quantstats (first/latest upload dates and release counts)
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
- **vectorbt** — you need fast vectorized backtesting and parameter sweeps, and you accept a
  Commons Clause licence; statistical overfitting controls are handled elsewhere.
- **quantstats** — you want presentation-grade performance tear sheets for a returns series.
  Reporting only; it validates nothing.
- **factorproof** — you want purged walk-forward CV, multiple-testing correction, a deflated Sharpe
  and a gate that says no, under MIT, offline, inspectable, with no subscription.
