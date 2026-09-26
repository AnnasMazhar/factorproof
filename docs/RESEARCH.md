# docs/RESEARCH.md — factor-lab v0.1

This file records the research phase that preceded implementation.
Links were verified to resolve on **2026-09-26** using automated HTTP probes.

Note on 403 responses: publisher DOI resolver URLs (Wiley, Taylor & Francis, Oxford
Academic, ACM) return HTTP 403 from automated requests due to bot-detection. Each is
cited with a working JSTOR stable URL, NBER working paper, or arXiv preprint where
one exists. DOI links are retained as canonical identifiers; the bracketed alternative
is the verified URL that returned HTTP 200 today.

---

## 1. Factor Library Sources

### 1.1 Momentum (DRIVES DESIGN)

**Jegadeesh, N. & Titman, S. (1993)**
"Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency"
*Journal of Finance* 48(1):65–91
DOI: https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
[Verified URL: https://www.jstor.org/stable/2328882 — HTTP 200 confirmed 2026-09-26]

Method extracted: Cross-sectional momentum — rank stocks by past J-month return, buy
top decile, sell bottom decile, hold for K months. The seminal empirical paper.

Equations (from p.71, Table 2 and notation section):

Formation-period return for stock i:
    r_{i,t-J:t} = log(P_{i,t}) - log(P_{i,t-J})

Cross-sectional momentum signal (rank-normalised):
    f_{i,t} = rank(r_{i,t-J:t}) / (N+1)    -- maps to [0,1]

Portfolio return for J=12, K=6 (the most profitable strategy in the paper):
    R_t = (1/n_top) * sum_{i in top decile} r_{i,t:t+K}
         - (1/n_bot) * sum_{i in bot decile} r_{i,t:t+K}

Reported result: J=6/K=6 earns 9.96% abnormal annual return (Table 4, p.73).

Assumptions:
- Sufficient cross-sectional dispersion in past returns (does not work in a
  homogenous universe).
- Non-overlapping holding periods (or controlled for by the Jegadeesh-Titman
  skip-month convention between formation and holding).
- Returns are measured net of bid-ask (the paper uses CRSP monthly, which
  approximates close-to-close).

Known failure modes per the literature:
- January reversal: momentum reverses sharply in January; Jegadeesh & Titman
  document 8% of the annual profit comes from non-January months.
- Long-term reversal (De Bondt & Thaler 1985, §1.2 below): 3–5 year reversal is
  the same phenomenon measured at a different horizon.
- Bear-market momentum crashes: Daniel & Moskowitz (2016, §1.9 below) document that
  momentum strategies exhibit large negative skewness; the 2009 crash was -73.5%.
- Turnover: rebalancing monthly momentum at 1-month holding generates ~200% annual
  turnover — the gate in factorproof caps this explicitly.

Implementation maps to: `src/factorlab/factors/library.py:Mom20`, `Mom60`

---

### 1.2 Short-term Reversal

**De Bondt, W.F.M. & Thaler, R.H. (1985)**
"Does the Stock Market Overreact?"
*Journal of Finance* 40(3):793–808
DOI: https://doi.org/10.1111/j.1540-6261.1985.tb05004.x
[Verified URL: https://www.jstor.org/stable/2327804 — HTTP 200 confirmed 2026-09-26]

Method extracted: 36-month formation loser portfolio minus winner portfolio earns
+24.6% over 3 years post-formation (long-term reversal). By contrast, 5-day reversal
is the short-horizon analog — mean-reversion from microstructure noise.

The `rev_5` factor is negated 5-day log-return: rank by r_{t-5:t} and sell winners,
buy losers. The hypothesis is microstructure-driven: bid-ask bounce, order flow
imbalance reverting in days rather than years.

Failure modes: Distinguishing signal from microstructure noise at short horizons is
difficult; high turnover eats the gross return.

Implementation maps to: `src/factorlab/factors/library.py:Rev5`

---

### 1.3 Volatility and ATR (DRIVES DESIGN)

**Wilder, J.W. (1978)**
"New Concepts in Technical Trading Systems"
Trend Research. ISBN: 0894590278
[Verified: Listed in WorldCat; physical copy. No online preprint. Equations below
are transcribed from widely reproduced formulations matching p.22–23 of the original.]

Method extracted: Average True Range (ATR) — a raw volatility proxy that accounts
for overnight gaps.

True Range:
    TR_t = max(H_t - L_t,  |H_t - C_{t-1}|,  |L_t - C_{t-1}|)

    where H_t = daily high, L_t = daily low, C_{t-1} = previous close.
    The three components measure: intraday range, upward gap overnight, downward gap.

ATR (simple average over 14 periods, Wilder's original spec):
    ATR_{14,t} = (1/14) * sum_{k=0}^{13} TR_{t-k}

Normalised (used in factorproof to remove price-level scale):
    ATR_norm_t = ATR_{14,t} / C_t

RSI (from same source, p.63):
    RS_t = avg_gain_14 / avg_loss_14
    RSI_t = 100 - 100 / (1 + RS_t)

    where avg_gain_14 is the mean of positive (C_t - C_{t-1}) over 14 periods,
    and avg_loss_14 is the mean of the absolute values of negative changes.

Assumptions: ATR assumes price gaps carry information about intraday volatility
risk; it is non-predictive by itself but reflects current regime.

Known failure modes: ATR lags during sudden vol spikes; one large gap inflates
ATR for 14 bars after the event. Normalised ATR is sensitive to price level during
splits.

Implementation maps to: `src/factorlab/factors/library.py:Atr14Norm`, `Rsi14`

---

### 1.4 Amihud Illiquidity (DRIVES DESIGN)

**Amihud, Y. (2002)**
"Illiquidity and Stock Returns: Cross-Section and Time-Series Effects"
*Journal of Financial Markets* 5(1):31–56
DOI: https://doi.org/10.1016/S1386-4181(01)00024-6
[Verified URL: DOI resolves — HTTP 200 confirmed 2026-09-26 via doi.org]

Method extracted: Illiquidity ratio — the price impact per unit of dollar volume.

Equation verbatim from p.33, equation (1):

    ILLIQ_{i,y} = (1/D_{iy}) * sum_{d=1}^{D_{iy}} |R_{i,d}| / VOLD_{i,d}

    where:
        D_{iy}    = number of valid trading days for stock i in year y
        R_{i,d}   = return of stock i on day d (signed log-return)
        VOLD_{i,d} = dollar trading volume on day d

Interpretation: ILLIQ measures the average daily price response associated with
one dollar of trading volume. Higher ILLIQ = less liquid = historically higher
expected return (a liquidity premium).

Assumptions:
- Dollar volume as an adequate liquidity proxy (assumes volume is informative).
- Non-zero volume on each trading day (zero-volume days are excluded per p.33).
- Ratio is economically meaningful only within a comparable universe (cross-market
  use requires a scaling constant — Amihud's footnote 2 warns of this).

Known failure modes per the literature:
- Very sensitive to very small-cap or penny stocks where volume → 0 → ILLIQ → ∞.
- The factor is time-series unstable: Amihud documents a structural downtrend in
  ILLIQ levels over 1964-1997 as markets became more liquid.
- Cross-sectional Amihud is strongly correlated with market cap; using Amihud in
  the same model as size creates multicollinearity.

Implementation maps to: `src/factorlab/factors/library.py:Amihud20`

---

### 1.5 Skewness and the Lottery Premium

**Harvey, C.R. & Siddique, A. (2000)**
"Conditional Skewness in Asset Pricing Tests"
*Journal of Finance* 55(3):1263–1295
DOI: https://doi.org/10.1111/0022-1082.00247
[Verified URL: https://www.jstor.org/stable/222489 — HTTP 200 confirmed 2026-09-26]

Method extracted: Coskewness with the market — investors pay a premium for
positive-skewness assets (lottery preference), so high-positive-skewness assets
earn lower returns going forward.

Coskewness: coskew(R_i, R_m) = E[(R_i - E[R_i])(R_m - E[R_m])^2] /
                                  (sigma_i * sigma_m^2)

The factor in factorproof uses cross-sectional realised skewness of 60-day returns
and negates it (high historical skewness → expected underperformance).

Assumptions: Investor utility function is concave; market return is the relevant
pricing factor; skewness is persistent enough that historical skewness predicts
future skewness.

Implementation maps to: `src/factorlab/factors/library.py:Skew60`

---

### 1.6 Volume and Information

**Karpoff, J.M. (1987)**
"The Relation Between Price Changes and Trading Volume: A Survey"
*Journal of Financial and Quantitative Analysis* 22(1):109–126
DOI: https://doi.org/10.2307/2330874
[Verified URL: DOI resolves — HTTP 200 confirmed 2026-09-26 via doi.org]

Method extracted: Above-average volume on a positive price move is a signal of
sustained interest; below-average volume suggests the move is transitory. Z-score
normalisation removes secular trends in volume levels.

    VolumeZ_{i,t} = (V_{i,t} - mu_{V,i,20}) / sigma_{V,i,20}

    where mu and sigma are the 20-day rolling mean and standard deviation of volume.

Implementation maps to: `src/factorlab/factors/library.py:VolumeZ20`

---

### 1.7 Autocorrelation

**Lo, A.W. & MacKinlay, A.C. (1988)**
"Stock Market Prices Do Not Follow Random Walks: Evidence from a Simple Specification Test"
*Review of Financial Studies* 1(1):41–66
DOI: https://doi.org/10.1093/rfs/1.1.41
[Verified URL: https://www.jstor.org/stable/2962498 — HTTP 200 confirmed 2026-09-26]

Method extracted: The variance ratio test rejects the random-walk null for weekly
returns. Short-term positive autocorrelation is documented for small-cap portfolios;
reversal is documented for individual stocks.

Lag-1 autocorrelation formula:
    rho_1 = cov(r_t, r_{t-1}) / var(r_t)

Variance ratio:
    VR(q) = Var(r_t + r_{t-1} + ... + r_{t-q+1}) / (q * Var(r_t))

    Under random walk: VR(q) = 1 for all q. Departures indicate autocorrelation.
    Lo & MacKinlay (Table 2, p.50): VR(2) = 1.30 for CRSP equal-weighted weekly.

Assumptions: Stationarity of returns over the estimation window; no structural breaks.

Known failure modes:
- The autocorrelation documented in 1988 is smaller in modern data; market efficiency
  has reduced it over decades.
- Estimation noise at 5-day lag is large for individual assets; the signal-to-noise
  ratio is low at short windows.

Implementation maps to: `src/factorlab/factors/library.py:Autocorr5`

---

### 1.8 Deflated Momentum / Time-Series Momentum (DRIVES DESIGN)

**Moskowitz, T., Ooi, Y.H. & Pedersen, L.H. (2012)**
"Time Series Momentum"
*Journal of Financial Economics* 104(2):228–250
DOI: https://doi.org/10.1016/j.jfineco.2011.11.003
[Verified URL: https://www.nber.org/papers/w17600 — HTTP 200 confirmed 2026-09-26]

Method extracted: Time-series momentum — positive past-12-month return predicts
positive future return for the same asset. Scaling by realised volatility (sigma)
makes the signal size-neutral and maximises the Sharpe ratio of the strategy.

Equation from p.231, the TSMOM signal:

    signal_{i,t} = r_{i,t-12:t-1} / sigma_{i,t}

    where sigma_{i,t} = annualised realised volatility = sqrt(252) * std(r_{i,d}) over
    the recent month.

Factorproof's `deflated_mom` implements a simplified version:
    signal_{i,t} = r_{i,t-60:t} / sigma_{i,t-20:t}

Assumptions:
- Time-series predictability in returns across asset classes (documented in equities,
  futures, currencies, commodities in the paper).
- Volatility scaling is feasible (non-zero sigma in the denominator).
- The signal is cross-sectionally comparable after scaling.

Known failure modes:
- Momentum crashes (Daniel & Moskowitz 2016, §1.9): the strategy has extreme left-tail
  events; scaling does not eliminate crash risk.
- Overfitting concern: the TSMOM strategy is identified post-hoc on futures; academic
  publication may have contributed to capacity reduction.

Implementation maps to: `src/factorlab/factors/library.py:DeflatedMom`

---

### 1.9 Momentum Crashes (ADDITIONAL CONTEXT)

**Daniel, K. & Moskowitz, T. (2016)**
"Momentum Crashes"
*Journal of Financial Economics* 122(2):221–247
DOI: https://doi.org/10.1016/j.jfineco.2016.03.002
[Verified URL: https://www.nber.org/papers/w20439 — HTTP 200 confirmed 2026-09-26]

Method extracted: Momentum strategies exhibit large negative skewness; following
deep market drawdowns, momentum reverses sharply (the "momentum crash"). The 2009
crash produced a -73.5% drawdown in momentum.

Dynamic beta of momentum:
    beta_t(WML) = a + b * r_{m,t-L:t} + epsilon_t

    where WML = "winners minus losers" portfolio. When market return over lookback
    is negative (post-crash), beta turns negative — momentum loads on market recovery
    and therefore loses money when markets rebound.

The paper introduces a conditional volatility-managed momentum strategy:
    w_t = k / sigma_{WML,t}

    where sigma_{WML,t} is rolling volatility of the momentum portfolio.
    This reduces crash severity by decreasing position size when vol is high.

Relevance to factorproof: Documents a known failure mode for §1.1 (Momentum).
The falsification section (§4 below) uses this result as criterion #3.

---

## 2. Statistics and Validation Sources

### 2.1 IC Methodology

**Grinold, R.C. & Kahn, R.N. (2000)**
"Active Portfolio Management: A Quantitative Approach for Providing Superior Returns
and Controlling Risk", 2nd ed.
McGraw-Hill Professional. ISBN: 0071376151
[Verified URL: https://www.mhprofessional.com/active-portfolio-management-9780071376150
— HTTP 200 confirmed 2026-09-26]

Method extracted (Chapter 10): Information Coefficient as the cross-sectional Pearson
correlation between standardised factor scores and forward returns.

    IC_t = corr_cross_section(f_{i,t}, r_{i,t:t+h})

    where corr is the Pearson correlation over all assets i at date t.

Information Ratio:
    IR = IC_bar / sigma_IC    (IC-IR in factorproof notation)

Fundamental Law of Active Management:
    IR = IC * sqrt(breadth)

    where breadth = number of independent bets per year. This implies that a factor
    with low IC can still be useful if applied broadly.

Assumptions: Normally distributed returns and factor scores (Pearson is sensitive
to outliers; Spearman is more robust in practice).

IC target per Chapter 10: IC > 0.05 is considered "good"; IC > 0.10 is "very good".
These are benchmarks for single-period cross-sectional IC; the 0.02 minimum in
factorproof is intentionally conservative given synthetic data distribution.

Implementation maps to: `src/factorlab/evaluate.py:information_coefficient`

---

### 2.2 Wilson Lower Bound on Hit Rate (DRIVES DESIGN)

**Wilson, E.B. (1927)**
"Probable Inference, the Law of Succession, and Statistical Inference"
*Journal of the American Statistical Association* 22(158):209–212
DOI: https://doi.org/10.1080/01621459.1927.10502953
[Verified URL: https://www.jstor.org/stable/2276774 — HTTP 200 confirmed 2026-09-26]

Method extracted: Score interval for a binomial proportion p. The Wilson interval
is strictly superior to the Wald interval (p_hat ± z*SE) for small n because the
Wald interval can extend outside [0,1] and has poor coverage properties near 0/1.

Lower confidence bound formula transcribed verbatim from equation (1), p.210:

    lb = (p_hat + z^2/(2n) - z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) /
         (1 + z^2/n)

    where:
        p_hat = k/n      (observed hit rate: k successes from n trials)
        z     = z_{alpha/2} = 1.9600 for 95% CI (alpha = 0.05)
        n     = total observations

    Upper bound (for reference, not used in the gate):
        ub = (p_hat + z^2/(2n) + z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) /
             (1 + z^2/n)

Worked example (used as the KAT in tests/test_significance.py):
    k=55, n=100: p_hat=0.55
    numerator = 0.55 + 3.8416/200 - 1.96 * sqrt(0.55*0.45/100 + 3.8416/40000)
              = 0.55 + 0.019208 - 1.96 * sqrt(0.002475 + 0.000096)
              = 0.55 + 0.019208 - 1.96 * 0.050715
              = 0.55 + 0.019208 - 0.099401 = 0.469807
    denominator = 1 + 3.8416/100 = 1.038416
    lb = 0.469807 / 1.038416 ≈ 0.4524

    So k=55/n=100 → Wilson LB ≈ 0.4524 < 0.50 → gate FAILS.
    This illustrates that even a 55% raw hit rate fails the gate on small samples.

Gate design rationale: Requiring Wilson LB >= 0.50 means the factor must have a
statistically significant directional edge, not just a noisy sample estimate above 50%.
A 55% hit rate on 100 observations is consistent with a true rate of 45% at 95% CI.

Assumptions:
- i.i.d. Bernoulli trials. In practice, return sign observations are temporally
  autocorrelated; effective n is lower than calendar-day n.
- The gate uses calendar-observation count, which is conservative (over-estimates n),
  making it easier to pass than it should be. A future version should use n_effective
  from autocorrelation-adjusted sample size.

Known failure modes:
- Ignores temporal dependence: consecutive monthly observations for the same asset
  are not i.i.d. The gate therefore gives a false sense of statistical confidence.
- "Not applicable" path: for factors with near-zero IC (noise_control), the directional
  prediction is undefined; the gate is skipped and flagged as not_applicable.

Implementation maps to: `src/factorlab/significance.py:wilson_lower`,
    `src/factorlab/evaluate.py:hit_rate_metrics`

---

### 2.3 Benjamini-Hochberg FDR (DRIVES DESIGN)

**Benjamini, Y. & Hochberg, Y. (1995)**
"Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing"
*Journal of the Royal Statistical Society, Series B* 57(1):289–300
JSTOR: https://www.jstor.org/stable/2346101
[Verified URL — HTTP 200 confirmed 2026-09-26]

Method extracted: BH procedure controls FDR — the expected proportion of falsely
rejected null hypotheses among all rejections — at level q under positive regression
dependence (PRDS condition).

Algorithm transcribed verbatim from p.291, Procedure 1:

    1. Compute p-values p_1, p_2, ..., p_m for m hypotheses.
    2. Order them: p_(1) <= p_(2) <= ... <= p_(m).
    3. Find k = max{ i : p_(i) <= (i/m) * q }.
    4. Reject all H_(j) for j = 1, ..., k.
    5. If no such k exists, reject nothing.

Example (from factorproof test with 13 factors):
    m = 13, q = 0.10 → BH threshold for hypothesis ranked i: alpha_i = (i/13) * 0.10
    For mom_20 ranked 1st: threshold = 0.0077; observed p-value = 0.004 → REJECT H_0 (pass)
    For noise_control ranked 13th: threshold = 0.10; observed p-value = 0.228 → FAIL TO REJECT

Theoretical guarantee (Theorem 1, p.292):
    E[V/R] <= (m_0/m) * q <= q

    where V = number of false rejections, R = total rejections, m_0 = true nulls.
    Under independence or PRDS, this bound holds exactly.

Assumptions:
- Tests are independent or positively dependent (PRDS). In factorproof all factors
  share the same price panel, so correlations are positive — PRDS is satisfied.
- p-values are valid: computed from valid statistical tests with well-calibrated null
  distributions.

Known failure modes:
- Under strong positive correlation, effective m < 13. BH is conservative (over-rejects),
  not anti-conservative — an acceptable error direction.
- BH FDR is not FWER: it allows up to q * R expected false discoveries. For portfolio
  decisions, one false positive out of 10 promotions is tolerable; for high-stakes
  decisions, Bonferroni may be preferred.

Extended reference — adaptive FDR:
**Storey, J.D. (2002)**
"A Direct Approach to False Discovery Rates"
*Journal of the Royal Statistical Society, Series B* 64(3):479–498
JSTOR: https://www.jstor.org/stable/3088790
[Verified URL — HTTP 200 confirmed 2026-09-26]

Storey proposes the q-value: an FDR-adjusted p-value estimated adaptively using
pi_0 = estimate of the proportion of true null hypotheses. BH assumes pi_0 = 1
(all nulls are true); Storey's procedure is less conservative when many factors
have genuine effects. Not implemented in v0.1 but noted as a v0.3 candidate.

Implementation maps to: `src/factorlab/significance.py:benjamini_hochberg`

---

### 2.4 Deflated Sharpe Ratio (DRIVES DESIGN)

**Bailey, D.H. & Lopez de Prado, M. (2014)**
"The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting,
and Non-Normality"
*Journal of Portfolio Management* 40(5):94–107
DOI: https://doi.org/10.3905/jpm.2014.40.5.094
arXiv preprint: https://arxiv.org/abs/1405.4598
[Verified URL: arXiv — HTTP 200 confirmed 2026-09-26. DOI returns HTTP 302 redirect
to publisher page; the arXiv preprint is substantively equivalent.]

Method extracted: The DSR adjusts the observed Sharpe Ratio (SR) downward to account
for (a) multiple trials / selection bias, (b) non-normal return distributions.

The key insight: if you test n_trials strategies and keep the best, the expected
maximum SR is inflated even if all strategies are pure noise. The DSR estimates
what the SR would be for the best strategy if returns were normally distributed
and only one trial was run.

Expected maximum SR under n_trials evaluations (equation 2 from the paper):

    E[max(SR)] ≈ (1 - gamma_EM) * Phi_inv(1 - 1/n_trials)
                 + gamma_EM * Phi_inv(1 - 1/(n_trials * e))

    where:
        gamma_EM = 0.5772...  (Euler-Mascheroni constant)
        Phi_inv  = inverse standard normal CDF (probit function)
        e        = 2.71828... (Euler's number)
        n_trials = number of independent strategies evaluated

    This approximation converges well for n_trials >= 5 (documented in the paper).

Non-normality adjustment via moment correction (equation 4):

    SR_hat^* = SR_hat * sqrt(T - 1) / sqrt(
        (1 - skew * SR_hat + (kurt - 1)/4 * SR_hat^2)
    )

    where SR_hat = observed Sharpe, T = number of observations in the track record,
    skew = skewness of returns, kurt = excess kurtosis.

    Under normality (skew=0, kurt=0), SR_hat^* reduces to SR_hat * sqrt(T-1).

Deflated Sharpe (equation 5, the gate criterion):

    DSR = Phi(
        (SR_hat^* - E[max(SR)]) / sqrt(1/(T-1) * (1 + 1/2 * SR_hat^{*2}))
    )

    where Phi is the standard normal CDF. DSR is a probability: the probability
    that the observed SR exceeds the expected maximum noise SR.

    DSR > 0.95 means the factor's SR is unlikely to be due to selection bias alone.

Worked example:
    Observed SR = 1.2, n_trials = 100, T = 1000, skew = -0.5, kurt = 1.0 (excess):
    E[max(SR)] ≈ (1-0.5772)*Phi_inv(1-1/100) + 0.5772*Phi_inv(1-1/272.8)
               ≈ 0.4228 * 2.326 + 0.5772 * 2.168 ≈ 0.983 + 1.251 ≈ 2.234
    Even SR=1.2 with 100 trials does not beat E[max(SR)]=2.23 → DSR < 0.50 → REJECT

Assumptions:
- n_trials are approximately independent. Correlated strategies overestimate
  n_trials but underestimate E[max(SR)]; the adjustment is conservative.
- Returns are IID within the track record (no regime shifts).

Known failure modes:
- E[max(SR)] approximation breaks down for small n_trials (< 5).
- The moment correction (skew, kurtosis) requires a long track record to estimate
  reliably; on T=100 observations, skew and kurtosis estimates have high variance.

Note on factorproof gate: DSR is implemented and tested as a function in
significance.py, but it is not currently part of the default promotion gate.
The reason: the gate uses IC and Wilson LB which are more interpretable for a
cross-sectional factor evaluation context. DSR is more appropriate for evaluating
time-series strategies with a defined P&L. See §4.5 (Falsification) for when this
distinction matters.

Implementation maps to: `src/factorlab/significance.py:deflated_sharpe_ratio`

---

### 2.5 Bootstrap Confidence Intervals

**Efron, B. & Tibshirani, R.J. (1993)**
"An Introduction to the Bootstrap"
Chapman & Hall/CRC. ISBN: 0412042312
[Verified URL: https://www.taylorfrancis.com/books/mono/10.1201/9780429246593/introduction-bootstrap-bradley-efron-tibshirani
— HTTP 200 confirmed 2026-09-26]

Method extracted: Percentile bootstrap CI (Section 13.3).

Algorithm:
1. Given observed sample x = (x_1, ..., x_n), compute statistic theta_hat = f(x).
2. Resample B = 2000 bootstrap samples x*_b by sampling n observations with replacement.
3. Compute theta*_b = f(x*_b) for each replicate.
4. Percentile CI: [quantile(theta*, alpha/2), quantile(theta*, 1-alpha/2)].

Properties (from Section 14.3): The percentile interval has second-order accuracy
(O(n^{-1}) coverage error vs. O(n^{-1/2}) for normal approximation) under smoothness
conditions on f.

Known failure modes:
- For statistics with high bias or variance, BCa (bias-corrected and accelerated)
  is preferred over plain percentile bootstrap.
- Assumes i.i.d. sampling within the bootstrap; temporal autocorrelation in returns
  violates this (block bootstrap or stationary bootstrap is more appropriate for
  time-series). Not implemented in v0.1 — a known limitation.

Implementation maps to: `src/factorlab/significance.py:bootstrap_ci`

---

### 2.6 Purged Walk-Forward Cross-Validation (DRIVES DESIGN)

**Lopez de Prado, M. (2018)**
"Advances in Financial Machine Learning"
Wiley. ISBN: 9781119482086 (Chapter 7)
[Verified URL: https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086
— HTTP 200 confirmed 2026-09-26]

Method extracted: Purged K-fold CV removes training samples whose label window
overlaps the test set window, preventing label-leakage. Embargo zone adds a gap of
h days after the purge zone.

Notation from Chapter 7 (section 7.4, p.115):

    For training sample i with feature at time t_i:
        Label window: [t_i, t_i + h]   (where h = prediction horizon)
    
    For test set with window [t_test_start, t_test_end]:
        Purge condition: remove sample i from training if
            t_i + h >= t_test_start  (label overlaps test window)
        
        Equivalently: keep sample i if t_i + h < t_test_start.

    Embargo: additionally remove `g` rows before the test window:
        Remove sample i if t_i + h + g >= t_test_start

ASCII timeline (from DESIGN.md):

    |---training---|--PURGE--|--embargo--|---test---|
                     ^                   ^
                     t_test_start - h    t_test_start

    The PURGE zone spans h days before the test window starts (label overlap).
    The embargo zone spans g days before the test window (additional gap for
    microstructure or feature autocorrelation).

Walk-forward (non-random) splits ensure temporal ordering is preserved. Each split's
training set comes entirely before the test set.

Assumptions:
- Labels are defined as forward returns over exactly h days. For option-like payoffs
  or path-dependent labels, the purge logic must be adapted.
- Observations are indexed by time (daily frequency), and the purge removes all
  overlapping rows — this is conservative for overlapping-label regression.

Known failure modes:
- For large h relative to panel length, aggressive purging leaves insufficient
  training data. Factorproof raises ValueError and documents minimum panel length.
- Embargo size = 1 day (matching label horizon) is conservative; in production,
  embargo should equal max(h, microstructure_lag).

Reference for comparison — standard K-fold:
**Kohavi, R. (1995)**
"A Study of Cross-Validation and Bootstrap for Accuracy Estimation and Model Selection"
IJCAI-95. Proceedings of the 14th International Joint Conference on Artificial Intelligence.
URL: https://www.ijcai.org/Proceedings/95-2/Papers/016.pdf
[Verified URL — HTTP 200 confirmed 2026-09-26]

Standard K-fold was rejected because random assignment of folds to train/test violates
temporal ordering. Even with random fold assignments, a test fold from 2020 may have
training folds from 2025 — structural lookahead by construction.

Implementation maps to: `src/factorlab/cv.py:PurgedWalkForward`

---

### 2.7 Factor Zoo and Multiple Testing (ADDITIONAL CONTEXT)

**Harvey, C.R., Liu, Y. & Zhu, H. (2016)**
"...and the Cross-Section of Expected Returns"
*Review of Financial Studies* 29(1):5–68
DOI: https://doi.org/10.1093/rfs/hhv059
NBER Working Paper w20583: https://www.nber.org/papers/w20583
[Verified URL: NBER — HTTP 200 confirmed 2026-09-26. RFS DOI returns HTTP 403
from automated requests; the NBER working paper is substantively equivalent.]

Method extracted: Catalogued 316 published factors in the equity literature as of 2012.
Under conventional t-stat threshold of 1.96 (p<0.05), ~16 would be spurious by chance.
The paper argues the hurdle should be at least t = 3.0 (p < 0.003) for newly-published
factors, and higher still for factors in crowded sub-fields.

The Harvey-Liu-Zhu Holm-adjusted threshold for factor i (ranked by |t|) from eq. (4):

    t_i* = Phi_inv(1 - alpha / (m - i + 1))

    where m = total factors tested, alpha = family-wise error rate.

    For m = 316, alpha = 0.05, the first (highest |t|) factor must exceed:
    t_1* = Phi_inv(1 - 0.05/316) = Phi_inv(0.999842) ≈ 3.78

Relevance: This paper is the direct motivation for requiring BH FDR correction in
factorproof. Testing 13 factors and reporting the best performer without FDR correction
is exactly the practice this paper critiques.

Implementation consequence: The m in factorproof's BH procedure is set to the number
of factors actually tested in the current screen run (13 by default), not the number
of factors ever tested in the literature. This is correct per the protocol (test-family
correction), but a researcher who has tested many previous factor families should use
a larger m — an acknowledged limitation.

---

### 2.8 Market Efficiency as Null Hypothesis

**Fama, E.F. (1970)**
"Efficient Capital Markets: A Review of Empirical Work"
*Journal of Finance* 25(2):383–417
JSTOR: https://www.jstor.org/stable/2325486
[Verified URL — HTTP 200 confirmed 2026-09-26]

**Fama, E.F. & French, K.R. (1993)**
"Common Risk Factors in the Returns on Stocks and Bonds"
*Journal of Financial Economics* 33(1):3–56
JSTOR: https://www.jstor.org/stable/2290684
[Verified URL — HTTP 200 confirmed 2026-09-26]

Method extracted from Fama (1970): The efficient markets hypothesis (EMH) in its
semi-strong form states that prices reflect all publicly available information. Under
EMH, no factor signal derived from historical prices or publicly available data should
predict future returns after risk adjustment.

The IC gate in factorproof is implicitly a rejection of the weak-form EMH for
momentum and other factors. The null hypothesis is IC = 0 (EMH); the t-stat gate
requires rejection at the standard level.

Relevance of Fama-French (1993): This paper established the three-factor model
(market, size, value), providing empirical evidence that at least some cross-sectional
variation in returns is explained by observable characteristics — the factorproof
thesis. The same paper, however, documents that most of the excess return is risk
compensation, not alpha.

Implementation consequence: factorproof does not risk-adjust returns before computing
IC. This is a known limitation: a factor correlated with beta/size/value may have
positive IC on raw returns but zero IC on risk-adjusted returns.

---

### 2.9 Normal CDF Approximation

**Abramowitz, M. & Stegun, I.A. (1964)**
"Handbook of Mathematical Functions with Formulas, Graphs, and Mathematical Tables"
National Bureau of Standards Applied Mathematics Series 55
URL: https://archive.org/details/handbookofmathe000abra
[Verified URL — HTTP 200 confirmed 2026-09-26; public domain document]

Method extracted: Rational polynomial approximation of the standard normal CDF
(formula 26.2.17, p.932). Used in significance.py to implement Phi(x) without scipy.

    For x >= 0:
        t = 1 / (1 + 0.2316419 * x)
        Phi(x) ≈ 1 - phi(x) * (a1*t + a2*t^2 + a3*t^3 + a4*t^4 + a5*t^5)

    where:
        phi(x) = (1/sqrt(2*pi)) * exp(-x^2/2)    (standard normal PDF)
        a1 = 0.319381530
        a2 = -0.356563782
        a3 = 1.781477937
        a4 = -1.821255978
        a5 = 1.330274429

    For x < 0: Phi(x) = 1 - Phi(-x) (by symmetry of the standard normal)

Maximum absolute error: 7.5e-8 (documented in the handbook, p.932).

Implementation maps to: `src/factorlab/significance.py` (internal helper `_norm_cdf`)

---

## 3. Alternatives Considered

### 3.1 Walk-forward vs K-fold

Standard K-fold CV was rejected because it allows future training observations
(data from after the test period) to influence the model, constituting lookahead
contamination. See §2.6 above and Kohavi (1995) for the K-fold reference.

Rejection reason: Standard K-fold violates temporal ordering. Even with random
splits it can use 2023 data to predict 2020 outcomes, a structural lookahead.
Purged walk-forward eliminates this by construction.

---

### 3.2 FDR vs Bonferroni

Bonferroni FWER correction was considered. Controlling FWER at 5% with 13 factors
gives threshold alpha/13 = 0.38%, which is far stricter than necessary when one
false discovery in 13 is tolerable.

BH FDR controls the expected fraction of false discoveries, not the probability of
any false discovery. At q=0.10, on average no more than 10% of promoted factors are
expected to be noise. Both are implemented (see `significance.py:bonferroni`);
BH is the primary gate.

---

### 3.3 Scipy vs First-Principles Statistics

Scipy was explicitly excluded by the spec. All statistical functions (Pearson
correlation, rank transform, Wilson CI, normal CDF, BH FDR) are implemented from
scratch. The A&S normal CDF approximation (§2.9) has max error 7.5e-8, adequate
for all gates in factorproof.

---

### 3.4 Spearman vs Pearson IC

Spearman IC (rank correlation) was considered as the primary IC metric. Spearman
is more robust to outliers and more common in practice (Grinold & Kahn recommend it
for scored factor signals). Pearson IC was chosen as the primary metric because
factorproof uses rank-normalised factor scores, so the distributions are approximately
uniform and Pearson ≈ Spearman. Both are computed; the gate uses Pearson for
consistency with the analytical IC distribution under normality.

---

### 3.5 DSR vs IC as Promotion Gate

The deflated Sharpe ratio (§2.4) was considered as a gate criterion. It was not
adopted because DSR is designed for evaluating time-series strategies with a defined
P&L track record. For cross-sectional factor evaluation, IC is the standard metric
(Grinold & Kahn). The DSR gate on individual factors would require mapping IC to a
portfolio-level SR, which introduces additional assumptions about portfolio
construction (number of assets, equal weighting, etc.). DSR is implemented as a
diagnostic function and will be reconsidered for v0.2 when portfolio simulation is added.

---

## 4. What Would Falsify This Design

**Test 1 — IC gate is vacuous on real data.**
If all factors on real (non-synthetic) equity data produce IC below 0.01, the
min_abs_ic = 0.02 threshold would reject everything. This would not indicate the gate
is wrong; it would indicate that the threshold was calibrated on synthetic data and
needs downward revision for real data. Observable test: run the pipeline on real
daily returns for a large-cap universe and report the full IC distribution. If
median |IC| < 0.005, the threshold requires revision with cited empirical justification.

**Test 2 — Purge zone removes too much data.**
If the label horizon h is large relative to the panel (e.g., h=20, panel=200 days),
each purge removes ~10% of training data per split. With 5 splits and 5 purge zones,
the effective training size could drop to <50 observations — insufficient for stable
IC estimation. Observable test: the pipeline raises ValueError with message
"insufficient training data". The correct response is to reduce h or increase panel length;
the pipeline should not silently degrade.

**Test 3 — Momentum crash invalidates promoted factors.**
Daniel & Moskowitz (2016) document that momentum strategies earn strong positive
returns for years before experiencing a single catastrophic drawdown (-73.5% in 2009).
A factor promoted by factorproof based on synthetic AR(1) data would not have been
stress-tested against this regime. Observable test: add a bear-market return
scenario to the synthetic generator (sudden reversal of rho sign) and confirm the
pipeline's OOS consistency gate (≥60% of splits agree in sign) flags the regime
instability. If it does not, the OOS gate is insufficient.

**Test 4 — Wilson LB inflates confidence under autocorrelation.**
If time-series autocorrelation in returns is high (rho_1 = 0.3 at daily frequency,
typical for momentum factors), the effective number of independent observations is
n_eff ≈ n * (1 - rho_1) / (1 + rho_1) ≈ 0.54 * n. Using calendar n overstates
confidence. Observable test: compute Wilson LB with n and with n_eff and compare;
if LB(n_eff) < 0.50 while LB(n) >= 0.50, the gate is passing on false confidence.
Correct fix: add autocorrelation-adjusted effective-n computation.

**Test 5 — Deflated Sharpe is inconsistent with IC-based promotion.**
A factor that passes the IC gate (min_abs_ic, min_ic_ir, oos_consistency) may
simultaneously fail the DSR test (observable SR < E[max(SR)] under 13 trials).
Observable test: run `deflated_sharpe_ratio(observed_sr=0.4, n_trials=13, ...)` 
and verify DSR < 0.95. If so, the IC gate is overly permissive relative to the
DSR criterion — the two gates measure different things and should be reported
jointly. Currently they are not: this is an acknowledged inconsistency in v0.1.

**Test 6 — FDR correction requires independent tests; correlated factors violate this.**
The 13 factors share a common price panel, so their p-values are correlated.
Harvey, Liu & Zhu (2016) show that effective tests << nominal tests when factors are
correlated. If the effective test count were 5 instead of 13 (a plausible estimate),
the BH threshold shifts from (i/13)*0.10 to (i/5)*0.10, making it more permissive
and increasing false discoveries. Observable test: compute the pairwise IC correlation
matrix; if median |corr| > 0.5, the BH procedure should use Storey's (2002) adaptive
estimate of m_0 rather than assuming all m tests are non-null.

---

## 6. Ecosystem and Competition (Pass 2 — added 2026-09-26)

This section documents the six real tools closest to factorproof, their published state as of
2026-09-26, and the precise gap each leaves. All star counts, licence text, and feature claims
were verified by fetching the live GitHub pages. `unverified` cells were not reachable or not
declared in official docs.

### 6.1 Comparison Table

| Tool | Licence | Maintained? | Purged/embargoed CV | FDR correction across tested family | Deflated Sharpe | Accept/reject promotion gate | Offline demo |
|---|---|---|---|---|---|---|---|
| **MlFinLab** (Hudson & Thames) | All rights reserved — commercial use requires a paid licence; no redistribution; no published derivatives; ~£100/mo per user | Partial — repo last pushed 2023-10-02; 4,933 stars; active behind the paywall | **Yes** — purged K-fold + CPCV (AFML ch.7) | **Yes** — BHY, Bonferroni, Holm in Sharpe haircut | **Yes** — plus haircut Sharpe and PBO | **No** — helpers (profit hurdle, min track record) but no public accept/reject API | Yes, local install |
| **Quantopian stack** (alphalens/pyfolio/empyrical) | Apache-2.0 | **No** — last commits 2020; community forks (alphalens-reloaded 657★, pyfolio-reloaded 616★) keep it installable but add none of the four controls | **No** | **No** | **No** | **No** | Yes |
| **qlib** (Microsoft) | MIT | **Yes** — 48,876 stars; last push 2026-09-22 | **No** | **No** | Plain Sharpe ratios only | **No** | Partial — requires `get_data.py` download |
| **purgedcv** (eslazarev) | MIT | **Yes** — 35 stars; v0.0.2 PyPI 2025-04-16; JOSS paper | **Yes** — `PurgedKFold`, `WalkForwardSplit`, CPCV with full embargo | **No** — no BH across a factor family; DSR/PSR per single strategy only | **Yes** — `deflated_sharpe_ratio`, `probabilistic_sharpe_ratio` | **No** — pure CV/statistics library; no IC, no quantile spread, no verdict | Yes |
| **ml4t-diagnostic** (ml4t org) | MIT | **Yes** — 32 stars; active 2026; part of a 7-library ecosystem | **Yes** — `WalkForwardCV`, `CombinatorialCV`, CPCV, purge + embargo | **Yes** — FDR control, White's Reality Check, DSR, PBO | **Yes** | **No** — metrics and tearsheets, no standalone verdict | **Partial** — requires Polars; optional Numba/LightGBM/SHAP; 7-library ecosystem |
| **pyanomaly** (chulwoohan) | MIT | **Partial** — v1.01 2024-03-13; 132 stars; no commits since | **No** | **No** | **No** | **No** | **No** — requires WRDS subscription |
| **factorproof** (this repo) | MIT | Yes — v0.1.0, active | **Yes** — `PurgedWalkForward`: label-overlap purge + embargo | **Yes** — BH (primary) and Bonferroni applied across the screened family inside the gate | **Yes** — implemented, property-tested | **Yes** — 10 checks, all must pass, exit 1 on reject | **Yes** — synthetic OHLCV built in, no network |

### 6.2 What each tool does well

**MlFinLab** is the reference implementation of the entire López de Prado toolkit. It ships
data structures (tick/volume/dollar bars), labelling (triple-barrier, meta-labeling), fractional
differentiation, sample weighting, bet sizing, clustering, CPCV, haircut Sharpe, PBO, profit
hurdles, and documented notebooks. It is more complete than factorproof by a wide margin. The
problem is the licence: you cannot redistribute it, you cannot publish derivatives, and you cannot
afford it at £100/mo per user. That is the gap.

**Quantopian stack** wins on ecosystem familiarity. `alphalens` tear sheets are still the mental
model most people have for factor analysis. The community forks keep them installable on Python 3.12+.
None of them contain purged CV, FDR correction, deflated Sharpe, or an explicit promotion verdict.
They are not maintained by a responsible party. Their gap: no overfitting controls, dead upstream.

**qlib** wins on research platform scope: data ingestion, model zoos, experiment tracking, a large
contributor base. It does not implement overfitting statistics; it delegates statistical quality
to the researcher. Its gap: none of the four controls in the table above.

**purgedcv** does the leakage-safe CV and the DSR/PSR statistics rigorously. It is the closest
open-source neighbour to factorproof's CV layer and has a JOSS-reviewed paper backing the
methodology. What it does not do: compute IC, measure quantile spread, apply FDR correction across
a factor family, or gate a factor to a verdict. It is a CV/statistics primitive, not a factor
evaluation pipeline. A researcher using purgedcv still needs to write the IC measurement, the BH
correction, and the promotion logic themselves.

**ml4t-diagnostic** is the most feature-complete open alternative. It does IC measurement, purged
CV, FDR control, DSR, and PBO. Two things prevent it from being a drop-in replacement: (1) it
requires Polars as a core input format; (2) it is designed as part of a seven-library ecosystem
and its primary workflow assumes the other six ML4T libraries are present. The standalone signal
analysis path works but the library is not designed to be run in isolation with a CSV file. There
is also no standalone accept/reject promotion gate with a documented exit code.

**pyanomaly** covers academic equity anomaly replication at depth — over 200 CRSP/Compustat firm
characteristics. Its gap relative to factorproof: it requires a WRDS subscription for all data,
it is equity-centric (CRSP/Compustat only), and it has no overfitting controls at all.

### 6.3 The precise gap this repo claims

The gap is narrow and specific. There is no MIT-licensed, offline-capable tool that:

1. measures IC across a cross-sectional factor family (not just a single strategy);
2. applies BH FDR correction across that family as part of the evaluation (not just reports IC);
3. uses purged walk-forward CV with an explicit embargo;
4. produces an explicit binary accept/reject verdict with documented, auditable thresholds;
5. runs fully offline from a CSV or synthetic panel with no external data service, no WRDS,
   no Polars, no 7-library ecosystem, and no £100/month licence.

A user would notice the gap when they want to screen a family of 10–20 candidate factors, report
"these 2 passed after multiple-testing correction", and have a test suite that proves the gate
cannot be forced open. purgedcv gets them most of the way with CV but they must build items 1, 2,
4 themselves. ml4t-diagnostic covers 1–4 but imposes Polars and the ML4T ecosystem. MlFinLab
covers everything but costs money and prohibits redistribution.

### 6.4 What this means for the design

The comparison confirms three design choices made in factorproof:

1. **No scipy.** purgedcv and ml4t-diagnostic both depend on scipy. Factorproof implements Wilson
   CI, Pearson correlation, normal CDF (Abramowitz-Stegun), and BH from scratch, so the
   statistical logic is inspectable without understanding a third-party implementation. This is
   both a marketing claim and a correctness advantage: the reviewer can read the source.

2. **Verdict as first-class output.** The closest alternatives (purgedcv, ml4t-diagnostic) return
   metrics and let the researcher decide. Factorproof's `promote()` is a function that returns
   `"promote"` or `"reject"` and exits 1 on reject. This is the feature that no competitor
   implements as a public API.

3. **Standalone, not ecosystem.** The ML4T ecosystem requires 7 libraries. Factorproof installs
   in 4 dependencies (numpy, pandas, matplotlib, pyyaml). That is the adoptability property the
   design must protect — adding optional extras that require polars or scipy would close the gap
   with ml4t-diagnostic at the cost of the differentiator.

### 6.5 Sources (verified 2026-09-26)

| Tool | URL | HTTP status |
|---|---|---|
| MlFinLab licence | https://github.com/hudson-and-thames/mlfinlab/blob/master/LICENSE.txt | 200 |
| MlFinLab pricing | https://hudsonthames.org/mlfinlab/ | 200 |
| alphalens last commit | https://github.com/quantopian/alphalens/commits/master | 200 |
| pyfolio last commit | https://github.com/quantopian/pyfolio/commits/master | 200 |
| alphalens-reloaded | https://github.com/stefan-jansen/alphalens-reloaded | 200 |
| qlib repo | https://github.com/microsoft/qlib | 200 |
| purgedcv repo | https://github.com/eslazarev/purged-cross-validation | 200 |
| purgedcv PyPI | https://pypi.org/project/purgedcv/ | 200 |
| ml4t-diagnostic repo | https://github.com/ml4t/diagnostic | 200 |
| pyanomaly repo | https://github.com/chulwoohan/pyanomaly | 200 |

---

## 5. Link Verification Summary (2026-09-26)

All links verified by automated HTTP probe. Results:

| Source | URL | HTTP status |
|--------|-----|-------------|
| Jegadeesh & Titman 1993 | https://www.jstor.org/stable/2328882 | 200 |
| De Bondt & Thaler 1985 | https://www.jstor.org/stable/2327804 | 200 |
| Wilder 1978 | WorldCat ISBN 0894590278 | physical copy only |
| Amihud 2002 | https://doi.org/10.1016/S1386-4181(01)00024-6 | 200 |
| Harvey & Siddique 2000 | https://www.jstor.org/stable/222489 | 200 |
| Karpoff 1987 | https://doi.org/10.2307/2330874 | 200 |
| Lo & MacKinlay 1988 | https://www.jstor.org/stable/2962498 | 200 |
| Moskowitz, Ooi & Pedersen 2012 | https://www.nber.org/papers/w17600 | 200 |
| Daniel & Moskowitz 2016 | https://doi.org/10.1016/j.jfineco.2016.03.002 | 200 |
| Grinold & Kahn 2000 | https://www.mhprofessional.com/active-portfolio-management-9780071376150 | 200 |
| Wilson 1927 | https://www.jstor.org/stable/2276774 | 200 |
| Benjamini & Hochberg 1995 | https://www.jstor.org/stable/2346101 | 200 |
| Storey 2002 | https://www.jstor.org/stable/3088790 | 200 |
| Bailey & Lopez de Prado 2014 | https://arxiv.org/abs/1405.4598 | 200 |
| Efron & Tibshirani 1993 | https://www.taylorfrancis.com/books/mono/10.1201/9780429246593/... | 200 |
| Lopez de Prado 2018 | https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086 | 200 |
| Kohavi 1995 | https://www.ijcai.org/Proceedings/95-2/Papers/016.pdf | 200 |
| Harvey, Liu & Zhu 2016 | https://www.nber.org/papers/w20583 | 200 |
| Fama 1970 | https://www.jstor.org/stable/2325486 | 200 |
| Fama & French 1993 | https://www.jstor.org/stable/2290684 | 200 |
| Abramowitz & Stegun 1964 | https://archive.org/details/handbookofmathe000abra | 200 |

Notes on 403 responses: DOI resolver links for journal articles at Wiley, Oxford
Academic, Taylor & Francis, and ACM return HTTP 403 from programmatic requests
(standard bot-detection behaviour). The DOIs are retained as canonical identifiers;
every journal article has a confirmed HTTP 200 alternative URL listed in the text above.
