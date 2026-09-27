# CHANGELOG.md

## [0.1.0] — 2026-09-26

### Added

- `src/factorlab/data.py`: OHLCV data loading, synthetic data generation with
  planted signal (AR(1) rho=0.15) and planted noise modes, `assert_no_lookahead` guard.
- `src/factorlab/factors/`: 13 factors across momentum, reversal, volatility,
  oscillator, volume, liquidity, distributional, and microstructure categories.
  Two deliberate controls: `noise_control` (pure random) and `lookahead_control`
  (structural future-data contamination).
- `src/factorlab/evaluate.py`: IC (Pearson and Spearman), IC-IR, IC decay,
  quantile spread, hit rate with Wilson lower bound, turnover, coverage.
  All statistics from first principles (no scipy).
- `src/factorlab/cv.py`: Purged walk-forward cross-validation with configurable
  embargo. Lookahead detection via `uses_future_data` flag.
- `src/factorlab/significance.py`: Benjamini-Hochberg FDR, Bonferroni,
  Deflated Sharpe Ratio, percentile bootstrap CI, min sample size helper.
  Normal CDF via Abramowitz & Stegun (1964) 26.2.17.
- `src/factorlab/promote.py`: Evidence gate with 10 criteria (all must pass).
  No `--force` flag. Configurable via `PromotionConfig`.
- `src/factorlab/report.py`: Markdown table, IC decay PNG, quantile returns PNG,
  self-contained HTML with inline base64 images.
- `src/factorlab/cli.py`: `factor-lab screen`, `promote`, `report`, `list`, `explain`.
- `tests/`: 85 tests — KAT, hypothesis property-based, adversarial edge cases.
  Mutation score 98.4% (253/257 killed on significance.py).
- `docs/RESEARCH.md`: 15 verified citations with method extractions.
- `docs/IMPLEMENTATION-NOTES.md`: equation-to-code traceability for all algorithms.
- `docs/DESIGN.md`: purge/embargo timeline, gate rationale.
- `docs/ADVERSARIAL-REVIEW.md`: independent falsification pass; 1 major finding (M01).
- `EVIDENCE.md`: verbatim terminal output from all verification commands.
- `examples/run_demo.sh`: full offline pipeline demo.
- `.github/workflows/ci.yml`: Python 3.11 + 3.12, ruff + pytest.
- `Makefile`: install, test, lint, format, demo targets.
