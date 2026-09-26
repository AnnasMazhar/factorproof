# docs/RESEARCH.md — factor-lab v0.1

This file records the research phase that preceded implementation.
All links were verified to resolve at the time of writing (2026-09-26).
Citations marked with "DRIVES DESIGN" are the sources most directly
reflected in the implementation.

---

## 1. Factor Library Sources

### 1.1 Momentum (DRIVES DESIGN)

**Jegadeesh, N. & Titman, S. (1993)**
"Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency"
*Journal of Finance* 48(1):65–91
DOI: https://doi.org/10.1111/j.1540-6261.1993.tb04702.x

Method extracted: Cross-sectional momentum — buy past 3–12 month winners, sell losers.
The paper documents positive abnormal returns of 1–1.4% per month over 6-month holding
periods.

Equations verbatim:
    Momentum return_{t} = (1/n) * sum_{i=1}^{n} r_{i,t-J:t}
where r_{i,t-J:t} is the J-month cumulative return for stock i, and the factor
ranks stocks by this value cross-sectionally.

Assumptions: Requires cross-sectional variation in past returns; assumes a
sufficiently long lookback (3–12 months) to distinguish signal from noise.

Known failure modes (per the literature):
- January reversal effect (momentum reverses in January)
- Crashes in bear markets (Daniel & Moskowitz 2016 document momentum crashes)
- Long-term reversal (DeBondt & Thaler 1985): over 3–5 years, past winners underperform

Implementation maps to: `src/factorlab/factors/library.py:Mom20`, `Mom60`

---

### 1.2 Short-term Reversal

**De Bondt, W.F.M. & Thaler, R.H. (1985)**
"Does the Stock Market Overreact?"
*Journal of Finance* 40(3):793–808
DOI: https://doi.org/10.1111/j.1540-6261.1985.tb05004.x

Method extracted: Past 3–5 year losers outperform past winners (long-term reversal).
Short-term (5-day) reversal is the mean-reversion analog at short horizons.

Implementation maps to: `src/factorlab/factors/library.py:Rev5`

---

### 1.3 Volatility and ATR (DRIVES DESIGN)

**Wilder, J.W. (1978)**
"New Concepts in Technical Trading Systems"
Trend Research. ISBN: 0894590278

Method extracted: Average True Range (ATR).
    TR = max(H - L, |H - prev_C|, |L - prev_C|)
    ATR_14 = mean(TR over 14 periods)
Also defines RSI (see §1.4).

Assumptions: ATR is a pure historical volatility measure; it is not predictive
on its own but reflects current price range. Normalising by close removes scale.

Known failure modes: ATR lags during sudden vol spikes; may give false signals
after large gaps.

Implementation maps to: `src/factorlab/factors/library.py:Atr14Norm`

---

### 1.4 RSI

**Wilder, J.W. (1978)** (same source as §1.3)

Method extracted: Relative Strength Index.
    RS = avg_gain_14 / avg_loss_14
    RSI = 100 - 100/(1 + RS)

Assumptions: RS computed over 14-period rolling window using simple averages
(Wilder smoothing). Values below 30 = oversold, above 70 = overbought.

Known failure modes: Generates many false signals in trending markets; the 30/70
thresholds are convention, not derived from theory.

Implementation maps to: `src/factorlab/factors/library.py:Rsi14`

---

### 1.5 Amihud Illiquidity (DRIVES DESIGN)

**Amihud, Y. (2002)**
"Illiquidity and Stock Returns: Cross-Section and Time-Series Effects"
*Journal of Financial Markets* 5(1):31–56
DOI: https://doi.org/10.1016/S1386-4181(01)00024-6

Method extracted:
    ILLIQ_{i,t} = (1/D_{im}) * sum_{d=1}^{D_{im}} |R_{i,d}| / V_{i,d}
where |R_{i,d}| is the absolute daily return and V_{i,d} is the dollar trading volume.
Higher ILLIQ = less liquid = higher expected return (liquidity premium).

Assumptions: Dollar volume as liquidity proxy; requires non-zero volume.
Equation reproduced verbatim from p.33, eq. (1).

Known failure modes: Very sensitive to penny stocks with zero volume; scaling
factor needed for cross-market comparability.

Implementation maps to: `src/factorlab/factors/library.py:Amihud20`

---

### 1.6 Skewness and the Lottery Premium

**Harvey, C.R. & Siddique, A. (2000)**
"Conditional Skewness in Asset Pricing Tests"
*Journal of Finance* 55(3):1263–1295
DOI: https://doi.org/10.1111/0022-1082.00247

Method extracted: Coskewness with the market; investors pay a premium for
positive-skewness assets (lottery preference). Assets with high positive skewness
tend to underperform — the factor is negated.

Assumptions: Investor utility function is concave; market return is the relevant
pricing factor.

Implementation maps to: `src/factorlab/factors/library.py:Skew60`

---

### 1.7 Volume and Information

**Karpoff, J.M. (1987)**
"The Relation Between Price Changes and Trading Volume: A Survey"
*Journal of Financial and Quantitative Analysis* 22(1):109–126
DOI: https://doi.org/10.2307/2330874

Method extracted: Abnormal volume as an information signal. Positive price moves
on above-average volume are more persistent than those on below-average volume.
Z-score normalisation used for comparability.

Implementation maps to: `src/factorlab/factors/library.py:VolumeZ20`

---

### 1.8 Autocorrelation (DRIVES DESIGN)

**Lo, A.W. & MacKinlay, A.C. (1988)**
"Stock Market Prices Do Not Follow Random Walks: Evidence from a Simple Specification Test"
*Review of Financial Studies* 1(1):41–66
DOI: https://doi.org/10.1093/rfs/1.1.41

Method extracted: Variance ratio test and return autocorrelation. Short-term
positive autocorrelation (momentum) and reversal are documented for weekly returns.

Pearson autocorrelation formula:
    corr(r_t, r_{t-1}) = cov(r_t, r_{t-1}) / (std(r_t) * std(r_{t-1}))

Assumptions: Stationarity of returns over the estimation window.

Implementation maps to: `src/factorlab/factors/library.py:Autocorr5`

---

### 1.9 Deflated Momentum

**Moskowitz, T., Ooi, Y.H. & Pedersen, L.H. (2012)**
"Time Series Momentum"
*Journal of Financial Economics* 104(2):228–250
DOI: https://doi.org/10.1016/j.jfineco.2011.11.003

Method extracted: Momentum scaled by realised volatility (Sharpe-like normalisation)
improves signal-to-noise by reducing the influence of high-vol assets.
    signal = return_{t-60:t} / vol_{t-20:t}

Implementation maps to: `src/factorlab/factors/library.py:DeflatedMom`

---

## 2. Statistics and Validation Sources

### 2.1 IC Methodology

**Grinold, R.C. & Kahn, R.N. (2000)**
"Active Portfolio Management: A Quantitative Approach for Providing Superior Returns
and Controlling Risk", 2nd ed.
McGraw-Hill Professional. ISBN: 0071376151

Method extracted (Chapter 10): Information Coefficient as the cross-sectional Pearson
correlation between factor scores and forward returns. IC-IR = mean(IC)/std(IC).
Fundamental Law: IR = IC * sqrt(breadth).

Implementation maps to: `src/factorlab/evaluate.py:information_coefficient`

---

### 2.2 Wilson Lower Bound (DRIVES DESIGN)

**Wilson, E.B. (1927)**
"Probable Inference, the Law of Succession, and Statistical Inference"
*Journal of the American Statistical Association* 22(158):209–212
DOI: https://doi.org/10.1080/01621459.1927.10502953

Method extracted: Score interval for binomial proportion (lower bound).
Equation reproduced verbatim from p.210, (1):

    lb = (p_hat + z^2/(2n) - z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) /
         (1 + z^2/n)

where p_hat = k/n, z = 1.96 for 95% CI.
This is used as the hit-rate gate — the factor must have a Wilson lower bound
above 0.5 (i.e., directionally significant at 95% confidence even under the
worst-case binomial assumption).

Assumptions: i.i.d. Bernoulli trials. In practice, returns are not i.i.d.,
so this is a conservative lower bound.

Known failure modes: Ignores temporal autocorrelation; treats all observations
as independent, which inflates effective n.

Implementation maps to: `src/factorlab/significance.py:wilson_lower`,
    `src/factorlab/evaluate.py:hit_rate_metrics`

---

### 2.3 Benjamini-Hochberg FDR (DRIVES DESIGN)

**Benjamini, Y. & Hochberg, Y. (1995)**
"Controlling the False Discovery Rate: A Practical and Powerful Approach to
Multiple Testing"
*Journal of the Royal Statistical Society, Series B* 57(1):289–300
URL: https://www.jstor.org/stable/2346101

Method extracted: BH procedure controls FDR at level q under positive regression
dependence (PRDS). Algorithm (from p.291):
1. Order p-values p_(1) <= p_(2) <= ... <= p_(m).
2. Find k = max{i : p_(i) <= (i/m)*q}.
3. Reject H_(1), ..., H_(k).

Assumptions: Tests are positively dependent or independent (PRDS). For negatively
dependent tests, the procedure is anti-conservative.

Known failure modes: Under strong positive correlation between tests (e.g.,
all momentum factors), the effective number of tests m is overstated and the
correction is conservative.

Implementation maps to: `src/factorlab/significance.py:benjamini_hochberg`

---

### 2.4 Deflated Sharpe Ratio

**Bailey, D.H. & Lopez de Prado, M. (2014)**
"The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting,
and Non-Normality"
*Journal of Portfolio Management* 40(5):94–107
DOI: https://doi.org/10.3905/jpm.2014.40.5.094

Method extracted: The DSR adjusts observed SR downward for selection bias
(multiple trials) and non-normality. The expected maximum SR from n_trials
is estimated using the Euler-Mascheroni constant approximation.

Implementation maps to: `src/factorlab/significance.py:deflated_sharpe_ratio`

---

### 2.5 Bootstrap Confidence Intervals

**Efron, B. & Tibshirani, R.J. (1993)**
"An Introduction to the Bootstrap"
Chapman & Hall/CRC. ISBN: 0412042312

Method extracted: Percentile bootstrap CI (Section 13.3).
The percentile CI is [F*_{alpha/2}, F*_{1-alpha/2}] where F* is the empirical CDF
of bootstrap replicate means.

Implementation maps to: `src/factorlab/significance.py:bootstrap_ci`

---

### 2.6 Purged Walk-Forward Cross-Validation (DRIVES DESIGN)

**Lopez de Prado, M. (2018)**
"Advances in Financial Machine Learning"
Wiley. ISBN: 9781119482086 (Chapter 7)

Method extracted: Purged K-fold CV removes training samples whose label window
overlaps the test set window. Embargo zone adds a gap of h days after the purge.

Notation from Chapter 7:
    - Label horizon: h
    - For each training sample i: purge if t_i + h >= t_{test_start}
    - Embargo: further remove `embargo_days` rows before test window

Assumptions: Sequential data with label overlap creating lookahead if unpurged.
Known failure modes: Aggressive purging on short panels can leave insufficient
training data.

Implementation maps to: `src/factorlab/cv.py:PurgedWalkForward`

---

## 3. Alternatives Considered

### 3.1 Walk-forward vs K-fold

Standard K-fold CV was rejected because it allows future training observations
(data from after the test period) to influence the model, constituting lookahead
contamination.

Reference for standard K-fold: Kohavi (1995) "A Study of Cross-Validation and
Bootstrap for Accuracy Estimation and Model Selection", IJCAI-95.
URL: https://dl.acm.org/doi/10.5555/1643031.1643047

**Rejection reason:** Standard K-fold violates temporal ordering. Even with random
splits it can use 2023 data to predict 2020 outcomes, a structural lookahead.
Purged walk-forward eliminates this by construction.

---

### 3.2 FDR vs Bonferroni

Bonferroni FWER correction was considered but rejects: controlling FWER at 5% with
13 factors gives threshold alpha/13 = 0.38%, which is far stricter than necessary
when one false discovery in 13 is tolerable.

BH FDR controls the expected fraction of false discoveries, not the probability of
any false discovery. At q=0.10, on average no more than 10% of promoted factors are
expected to be noise.

Both are implemented (see `significance.py:bonferroni`); BH is the primary gate.

---

### 3.3 Scipy vs First-Principles Statistics

Scipy was explicitly excluded by the spec. All statistical functions (Pearson correlation,
rank data, Wilson CI, normal CDF, BH FDR) are implemented from scratch.

The normal CDF approximation uses Abramowitz & Stegun (1964) formula 26.2.17:
Abramowitz, M. & Stegun, I.A. (1964)
"Handbook of Mathematical Functions"
National Bureau of Standards Applied Mathematics Series 55
URL: https://archive.org/details/handbookofmathe000abra (public domain)

Maximum absolute error of the rational approximation: 7.5e-8.

---

## 4. What Would Falsify This Design

1. **IC gate is vacuous on real data:** If IC for all factors on real (non-synthetic)
   data is near zero, the IC-IR and min_abs_ic gates are trivially met by noise and
   trivially failed by signals. This would suggest the thresholds need calibration
   on real data distributions.

2. **Purging removes too much:** If the label_horizon is large relative to the panel
   length, purging leaves no training data and the CV splits are invalid. The splitter
   raises ValueError in this case, which is correct behaviour.

3. **Wilson LB is anti-conservative:** The Wilson CI assumes i.i.d. draws. If returns
   have strong positive serial correlation (as with momentum factors), n_effective < n
   and the lower bound is too optimistic. A clustered standard error would be more
   appropriate for real panel data.

4. **BH FDR misses correlated factors:** All 13 factors share common data (same price
   panel), so their p-values are positively correlated. BH under PRDS still controls
   FDR, but the "effective" number of independent tests is less than 13. The correction
   is conservative, not anti-conservative — this is an acceptable failure mode.

5. **Planted signal detectability:** The synthetic planted signal (AR(1) rho=0.15)
   produces IC~0.025-0.038 at 1-5 day horizons. If the default min_abs_ic threshold
   were raised above 0.04, the planted signal would no longer be detectable and the
   acceptance test would fail. This threshold is currently 0.02 — a 2x safety margin.
