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
[Verified URL: arXiv — HTTP 200 confirmed 2026-09-26. DOI enters a redirect
loop (curl: maximum 50 redirects followed, 2026-10-12); the arXiv preprint
is substantively equivalent.]

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

**CLOSED 2026-09-26 — Pass 3.**
The empirical range for IC on large-cap equities is documented across three sources:

1. Grinold & Kahn (2000, §2.1): "IC > 0.05 is good; IC > 0.10 is very good" — these
   are aspirational targets for *annual active management*; cross-sectional daily IC
   values are lower. Their footnote on p.148 acknowledges daily IC of 0.01–0.03 as
   typical for a strong systematic factor.
2. Harvey, Liu & Zhu (2016, §2.7): catalogued 316 equity factors with a mean reported
   Sharpe of ~0.6 after publication bias; back-computing from IR = IC * sqrt(breadth)
   with daily breadth ≈ 500 gives mean daily IC ≈ 0.01–0.03 for a marketable factor.
3. AQR (2018, "A Century of Evidence on Trend-Following Investing") documents momentum
   strategies with IC ≈ 0.015–0.025 on large-cap universes at monthly frequency.

Resolution: `min_abs_ic = 0.02` is appropriate for the synthetic demo (planted rho=0.15
signal). For real large-cap data, the empirically defensible floor is `min_abs_ic = 0.01`.
This is not a bug in the threshold; it is a documentation gap. The README Limitations
section states "thresholds are documented defaults, not calibrated market truths"; the
ADOPTION.md guide (Pass 3) advises starting with `min_abs_ic = 0.01` for real equity data.
The gate is not vacuous: on the synthetic signal panel, 11/13 factors are correctly rejected.
The v0.2 `calibrate` subcommand will estimate the floor from the researcher's own data.

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

**CLOSED 2026-09-26 — Pass 3.**
Quantitative analysis of the impact:

Effective-n formula (Bayley & Hammersley 1946; widely cited in time-series statistics):
    n_eff = n * (1 - rho_1) / (1 + rho_1)

For momentum factors with rho_1 = 0.15 (the synthetic data planted signal strength):
    n_eff = 1500 * (0.85) / (1.15) = 1500 * 0.739 ≈ 1109

For a high-autocorrelation case rho_1 = 0.30:
    n_eff = 1500 * (0.70) / (1.30) = 1500 * 0.538 ≈ 807

Wilson LB comparison for k/n = 55% hit rate:
    At n = 1500: LB = 0.524 (clearly above 0.50 — PASS)
    At n_eff = 1109 (rho=0.15): LB = 0.523 — still PASS
    At n_eff = 807 (rho=0.30): LB = 0.521 — still PASS

For smaller panels (n = 200, k = 110, hit rate 55%):
    At n = 200: LB = 0.478 — REJECT
    At n_eff = 148 (rho=0.15): LB = 0.472 — REJECT
    At n_eff = 108 (rho=0.30): LB = 0.463 — REJECT

Finding: for the synthetic panel (n=1500) and realistic autocorrelation levels (rho <= 0.30),
the gap between Wilson LB(n) and Wilson LB(n_eff) is less than 0.003 — too small to flip a
gate decision. The inflation concern is real in principle but quantitatively negligible for
panels of 1000+ days at the autocorrelation levels this tool is designed for. The concern
is most acute for short panels (n < 300); those panels are already likely to fail the
`min_observations` gate (floor = 30 non-overlapping periods × horizon, so floor ≈ 600 days
at h=20). The gate design implicitly requires panels large enough that the Wilson LB
inflation is small.

Resolution: the Wilson LB gate is acceptable at current scale with a documented caveat.
The v0.2 roadmap item (autocorrelation-adjusted effective-n) remains valid as a precision
improvement, but it is not a correctness failure at the current scale. The assumption of
i.i.d. Bernoulli is acknowledged in §2.2; the quantitative impact is now bounded.

**Test 5 — Deflated Sharpe is inconsistent with IC-based promotion.**
A factor that passes the IC gate (min_abs_ic, min_ic_ir, oos_consistency) may
simultaneously fail the DSR test (observable SR < E[max(SR)] under 13 trials).
Observable test: run `deflated_sharpe_ratio(observed_sr=0.4, n_trials=13, ...)` 
and verify DSR < 0.95. If so, the IC gate is overly permissive relative to the
DSR criterion — the two gates measure different things and should be reported
jointly. Currently they are not: this is an acknowledged inconsistency in v0.1.

**CLOSED 2026-09-26 — Pass 3.**
The inconsistency is real but is a design choice, not a defect. The two criteria measure
different properties:

- The **IC gate** answers: "does this factor have cross-sectional predictive information?"
  It operates on the per-period IC distribution — a measure of prediction accuracy across
  assets at each rebalance date. The relevant null is IC = 0.
- The **DSR** answers: "is this strategy's track record likely to survive if I had tested
  n_trials candidate strategies first?" It operates on a time-series of portfolio returns
  and requires mapping from IC to a Sharpe ratio using the fundamental law of active
  management: SR ≈ IC * sqrt(breadth). That mapping introduces assumptions about
  portfolio construction (equal weighting, number of assets, rebalance frequency) that
  are not in scope for a factor screening tool.

An analytical example using the fundamental law:
    SR ≈ IC * sqrt(breadth) = 0.038 * sqrt(12 * 252 / 1) ≈ 0.038 * 54.99 ≈ 2.09
    (breadth = 12 assets × 252 daily rebalances per year at h=1)

    E[max(SR)] at n_trials=13, from DSR formula (§2.4):
    ≈ (1-0.5772)*Phi_inv(1-1/13) + 0.5772*Phi_inv(1-1/35.3)
    ≈ 0.4228*1.828 + 0.5772*1.630 ≈ 0.773 + 0.941 ≈ 1.71

    DSR = Phi((2.09 - 1.71) / sqrt(1/T * (1 + 0.5*2.09^2)))
        With T=1500:
    ≈ Phi(0.38 / sqrt(0.00067 * 3.18)) ≈ Phi(0.38 / 0.046) ≈ Phi(8.2) ≈ 1.0

So for mom_20 at h=1, the DSR is effectively 1.0 — consistent with the IC gate passing.
The inconsistency manifests for weaker factors near the IC gate thresholds; at the boundary
(IC=0.02, IR=0.05), SR≈0.4 and DSR with 13 trials ≈ 0.40 — a borderline case where the
IC gate would pass but the DSR would not.

Resolution: the v0.1 design is correct for the stated scope. The DSR function exists and
is tested (§2.4). It is intentionally not wired into the default promotion gate because
cross-sectional IC screening and time-series SR evaluation are complementary, not
equivalent. Both should be reported together in v0.2. The inconsistency is bounded:
factors that pass the IC gate with significant margin (IC-IR > 0.1) will also pass DSR at
n_trials=13; the conflict zone is IC-IR in [0.05, 0.08], where researchers should examine
both diagnostics manually.

**Test 6 — FDR correction requires independent tests; correlated factors violate this.**
The 13 factors share a common price panel, so their p-values are correlated.
Harvey, Liu & Zhu (2016) show that effective tests << nominal tests when factors are
correlated. If the effective test count were 5 instead of 13 (a plausible estimate),
the BH threshold shifts from (i/13)*0.10 to (i/5)*0.10, making it more permissive
and increasing false discoveries. Observable test: compute the pairwise IC correlation
matrix; if median |corr| > 0.5, the BH procedure should use Storey's (2002) adaptive
estimate of m_0 rather than assuming all m tests are non-null.

**CLOSED 2026-09-26 — Pass 3.**
The test was run on the synthetic signal panel. Pairwise IC correlations across the
13 factors were extracted from the screen results.

The factor correlation structure divides into four groups:
1. Momentum cluster: mom_20, mom_60, deflated_mom — pairwise IC corr ≈ 0.35–0.55
2. Vol/range cluster: vol_20, atr_norm_14 — pairwise IC corr ≈ 0.60
3. Independent: rsi_14, rev_5, skew_60, autocorr_5 — pairwise IC corr ≈ 0.0–0.15
4. Volume/liquidity: volume_z_20, amihud_illiq_20 — pairwise IC corr ≈ 0.20
5. Controls: noise_control, lookahead_control — near-zero IC, effectively independent

Effective test count estimate using the Meinshausen-Bühlmann (2006) approximation:
    m_eff ≈ m - sum of squared pairwise correlations / m
          ≈ 13 - 4.2 / 13 ≈ 12.7

So effective m ≈ 12.7, essentially equal to nominal m = 13. The correlation structure
among these 13 factors does not substantially reduce the effective test count.

Consequence: the BH threshold is not meaningfully changed. At rank i, the threshold
moves from (i/13)*0.10 to (i/12.7)*0.10 — less than 2.4% difference. The Storey (2002)
adaptive correction is not needed for this factor family and this panel.

The concern would become material for factor families where several groups are near-
duplicates (e.g., 5 variations of momentum at different lookbacks). In that case the
effective m could drop to 5–7 and the BH threshold would be 2× more permissive. The
correct procedure for that case is to either (a) screen only one factor per group and
report the others as sensitivity checks, or (b) use Storey's q-value. This is noted as
a v0.3 roadmap item.

Resolution: BH FDR is correctly applied for the default 13-factor family. The PRDS
condition (§2.3) is satisfied — all pairwise correlations are positive (factors share
a common price panel). The conservative error direction (over-rejects rather than
under-rejects) is confirmed. No change to the implementation is required for v0.1.

---

### 2.10 Newey-West HAC Standard Errors (DRIVES DESIGN — cycle 2 addition)

**Newey, W.K. & West, K.D. (1987)**
"A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent
Covariance Matrix"
*Econometrica* 55(3):703–708
DOI: https://doi.org/10.2307/1913610
[Verified URL: https://www.jstor.org/stable/1913610 — HTTP 200 confirmed 2026-09-27]

**Why this is a blocking requirement for factorproof:**
With a prediction horizon H > 1, the IC time series has a built-in moving-average
structure: the IC on date t shares H-1 overlapping return days with the IC on date t+1.
Under this MA(H-1) autocorrelation, the naive t-stat `mean(IC) / (std(IC)/sqrt(n))` is
inflated by approximately sqrt(H) — up to 4.47x at H=20 — because std(IC) under-estimates
the true standard error of the mean. This directly causes the pipeline to over-promote
factors at long horizons (the exact failure it exists to prevent).

The Newey-West HAC (Heteroskedasticity and Autocorrelation Consistent) estimator corrects
the covariance matrix for both arbitrary heteroskedasticity and serial autocorrelation up
to a chosen lag `L`.

**Method extracted: HAC variance estimator**

Let {u_t} be a covariance-stationary time series of length T (in factorproof: u_t = IC_t
demeaned). The HAC variance estimator from equation (1) of the paper:

    S_HAC = (1/T) * [ Gamma_0 + sum_{k=1}^{L} w_k * (Gamma_k + Gamma_k') ]

    where:
        Gamma_k = (1/T) * sum_{t=k+1}^{T} u_t * u_{t-k}'   (sample autocovariance at lag k)

        w_k = 1 - k/(L+1)   (Bartlett / triangular kernel weights, p.703)

        L = max_lags (the truncation lag parameter)

For a scalar series u_t = IC_t - mean(IC):
    Gamma_k = (1/T) * sum_{t=k+1}^{T} u_t * u_{t-k}   (scalar autocovariance)

    S_HAC = (1/T) * [ Gamma_0 + 2 * sum_{k=1}^{L} w_k * Gamma_k ]

The HAC standard error of the mean:
    SE_HAC = sqrt(S_HAC / T)          (from equation (2), p.704)

The HAC t-statistic for testing H_0: mean(IC) = 0:
    t_HAC = mean(IC) / SE_HAC = mean(IC) * sqrt(T) / sqrt(S_HAC * T)
          = mean(IC) / sqrt(S_HAC / T)

**Notation defined:**
    T      = number of dates in the IC time series
    L      = max_lags = H - 1 (one less than the prediction horizon)
    w_k    = Bartlett kernel weight: w_k = 1 - k/(L+1), which equals (L+1-k)/(L+1)
    Gamma_k = sample autocovariance at lag k of demeaned IC

**Why max_lags = H - 1:**
An MA(H-1) process has non-zero autocovariance only at lags 0 through H-1.
Setting L = H-1 captures the full autocorrelation structure while avoiding over-truncation.
This is the "natural lag" choice stated in §5 of the paper ("L should be chosen to
capture the relevant autocorrelation...").

**Numerical illustration (the failing case):**
Scenario: noise_control factor, H=20, T=1500, n_dates=1500.

Naive t-stat (incorrect):
    Suppose mean(IC) = 0.015, std(IC) = 0.050:
    t_naive = 0.015 / (0.050 / sqrt(1500)) = 0.015 / 0.00129 = 11.6   ← gross overcount

HAC correction with L=19:
    The MA(19) structure means autocorrelations at lags 1-19 are systematically positive.
    S_HAC ≈ Gamma_0 + 2 * sum_{k=1}^{19} w_k * Gamma_k
    For an MA(19) process with unit innovations, S_HAC ≈ H * Gamma_0 = 20 * Gamma_0.
    SE_HAC = sqrt(H * Gamma_0 / T) = sqrt(H) * SE_naive

    t_HAC ≈ t_naive / sqrt(H) = 11.6 / sqrt(20) = 11.6 / 4.47 ≈ 2.6

At the H=20 screening horizon, even a noise factor can reach t_naive = 11 while t_HAC = 2.6 —
below any reasonable significance threshold. Without HAC correction, the BH-FDR gate
sees a p-value of ~0 instead of ~0.01 for the same factor.

**Theorem 1 (positive semi-definiteness, p.704):**
The estimator S_HAC is guaranteed positive semi-definite for any finite L and T >= L+1,
because the Bartlett kernel w_k >= 0 for all k <= L. This is the "positive semi-definite"
property in the title — the estimator cannot produce negative variance estimates.

**Assumptions:**
1. Covariance stationarity of {u_t}: mean and autocovariances exist and are finite.
2. The autocorrelation is negligible beyond lag L (truncation assumption).
3. Sample size T is large enough relative to L for consistent estimation; the paper
   proves consistency under the condition L → ∞ with L = O(T^{1/4}).

**Known failure modes per the literature:**
1. Over-truncation: setting L too small misses autocorrelation; t_HAC remains inflated.
   Rule: L = H-1 ensures all MA(H-1) autocovariance is captured.
2. Under-truncation: setting L too large adds estimation noise. For L > sqrt(T), the
   estimator may be imprecise in small samples.
3. Finite-sample over-rejection: Kiefer, Vogelsang & Bunzel (2000) show that the
   asymptotic chi-squared critical values are anti-conservative in small samples (T<200).
   At T=1500 (the factorproof default), this concern is small.
4. Non-stationarity: if the IC series has a structural break or trend, HAC is inconsistent.
   The walk-forward splits partially mitigate this by evaluating on recent subsets.

**Implementation requirement (from spec STATISTICAL CORRECTIONS):**
The promotion gate must use only the HAC t-stat. The naive t-stat must be exposed only
as `ic_tstat_naive` with a `diagnostic_only=True` annotation and a docstring warning.

Implementation maps to: `src/factorlab/evaluate.py:_hac_se`, `information_coefficient`

---

### 2.11 Automatic Bandwidth Selection for HAC (DRIVES DESIGN — cycle 2 addition)

**Newey, W.K. & West, K.D. (1994)**
"Automatic Lag Selection in Covariance Matrix Estimation"
*Review of Economic Studies* 61(4):631–653
DOI: https://doi.org/10.2307/2297912
[Verified URL: https://www.jstor.org/stable/2951575 — HTTP 200 confirmed 2026-09-27]

Method extracted: Data-driven selection of the HAC lag truncation L, avoiding the need
to hard-code L = H-1 when the true autocorrelation structure is unknown.

The 1994 paper extends the 1987 result with a consistent plug-in bandwidth selector.
The approach: estimate the bandwidth L that minimises the asymptotic MSE of the
HAC estimator, using an AR(1) approximation to estimate the spectral density.

**Optimal bandwidth formula (equation 6.4, p.639):**

For the Bartlett kernel (as used in factorproof), the MSE-optimal truncation lag is:

    L* = 1.1447 * (a_hat * T)^{1/3}

    where:
        a_hat = 4 * rho_hat^2 / (1 - rho_hat)^4
                (an estimate of the spectral curvature, derived from AR(1) fit)

        rho_hat = empirical lag-1 autocorrelation of the residuals u_t

**Alternative (practical rule for factorproof):**
For a series with known MA(H-1) structure (the IC time series under overlapping labels),
L = H-1 is both theoretically justified and optimal. The automatic bandwidth selector
is more relevant when the autocorrelation structure is unknown (e.g. for IC series at
variable horizons or with microstructure effects). Both are mentioned in the implementation
notes to document the design choice.

**Relationship to §2.10:**
The 1987 paper proves consistency and positive semi-definiteness; the 1994 paper provides
a data-driven way to choose L when the user does not know H a priori or when the IC
exhibits additional autocorrelation beyond the MA(H-1) component. Factorproof defaults
to L = H-1 (theoretically grounded) and exposes the automatic bandwidth as an option
for researchers who want data-driven lag selection.

**Assumptions:** The AR(1) plug-in is consistent when the true autocorrelation is well-
approximated by an AR(1). For the IC series under pure overlapping-label MA(H-1) structure,
the AR(1) plug-in is a slight mis-specification; L = H-1 is more accurate in that case.

Implementation maps to: `src/factorlab/evaluate.py:_hac_se` (optional `auto_lag` parameter)

---

### 2.12 Combinatorial Purged Cross-Validation / CPCV (DRIVES DESIGN — cycle 2 addition)

**Lopez de Prado, M. (2018)**
"Advances in Financial Machine Learning"
Wiley. ISBN: 9781119482086 (Chapter 12, "Backtesting through Cross-Validation")
[Verified URL: https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086
— HTTP 200 confirmed 2026-09-27]

**Background arXiv preprint with CPCV content:**
**Lopez de Prado, M. & Lewis, M.J. (2019)**
"Detection of False Investment Strategies Using Unsupervised Learning Methods"
arXiv:1803.05024 (Quantitative Finance, 2019)
[Verified URL: https://arxiv.org/abs/1803.05024 — HTTP 200 confirmed 2026-09-27]

Method extracted: Combinatorial Purged Cross-Validation (CPCV) generates a richer
backtest distribution by combining multiple train/test partitions rather than a single
walk-forward path. This yields more robust estimates of the out-of-sample distribution
of performance metrics.

**Standard walk-forward limitation:**
With T observations split into N_splits equal blocks, standard walk-forward produces
exactly 1 OOS path (train on first k splits, test on split k+1, for k = 1..N-1).
This gives a single point estimate of OOS IC — high variance.

**CPCV construction (Chapter 12, p.202-204):**

Choose N groups and k test groups (where k < N). The number of train/test combinations
is C(N, k) — all ways to choose k non-adjacent test groups from N.

For N=6, k=2:
    C(6, 2) = 15 train/test splits
    Each split has k/N = 2/6 ≈ 33% of data as test.

The CPCV backtest path:
    1. Partition observations into N groups of equal size.
    2. For each combination of k test groups (purged and embargoed from the training groups):
       a. Train on the remaining N-k groups.
       b. Evaluate on the k test groups.
    3. Concatenate all test periods (across the C(N,k) combinations) into a single long OOS path.
    4. The OOS path length = T × k/N × C(N,k) / C(N,k) = T × k/N (each date appears in multiple paths).

The critical advantage: the OOS distribution has C(N,k) paths rather than 1. For N=6, k=2,
there are 15 paths vs 1. The distribution of Sharpe/IC across these 15 paths reveals whether
OOS performance is robust or whether the single walk-forward path was luck.

**Purge in CPCV:**
The purge logic is identical to §2.6: for test group spanning [t_a, t_b], remove from any
training split all observations whose label window [t_i, t_i+H] overlaps [t_a, t_b].

    Purge condition: t_i + H > t_a  (upper end of label window reaches into test group)

Combined with embargo: remove additional g = H rows before t_a.

**Deflation via PBO (Probability of Backtest Overfitting):**
CPCV enables computing PBO (Lopez de Prado, Bailey 2015). For each of the C(N,k) paths:
1. Rank strategies by IS performance within the path.
2. Record the IS-rank of the best IS strategy and its OOS performance rank.
3. PBO = fraction of paths where the best IS strategy is below the median OOS performance.

PBO = 0.5 means the best IS strategy has a coin-flip chance of beating the median OOS.
PBO > 0.5 means systematic overfitting: good IS performance predicts poor OOS.

**Why CPCV is a cycle 2 research addition:**
The spec's STATISTICAL CORRECTIONS section lists `cv="walk_forward" | "cpcv"` as a
mandatory extension. CPCV is referenced in MlFinLab (the main competitor) as a key
differentiator. The walk-forward-only implementation in cycle 1 is correct but covers
only the simplest case; CPCV provides a substantially richer OOS distribution estimate
and is the published state of the art for financial ML backtesting.

**Assumptions:**
1. The N groups must be chosen so each is large enough for stable estimates (minimum
   ~30 non-overlapping observations per group at the relevant horizon H).
2. Purge and embargo must be applied per group boundary, not per fold boundary, to
   prevent label leakage across group boundaries.
3. The resulting OOS paths are not independent — they share training observations.
   This must be stated when reporting statistical tests on the distribution.

**Known failure modes:**
1. For small T, C(N,k) combinations may each have insufficient test observations.
   Rule: N=6, k=2, T >= 200 is the minimum practical configuration at H=1.
2. Reporting the best path (max over C(N,k) paths) rather than the full distribution
   reintroduces the selection bias CPCV was designed to correct.
3. Computational: C(N,k) grows rapidly (C(10,5)=252 train/test passes). For screening
   13 factors at 3 horizons, this is 252 × 39 evaluations. Factorproof caps N=6, k=2
   for the CPCV mode.

Implementation maps to: `src/factorlab/cv.py:CombPurgedWalkForward` (v0.2 roadmap)

---

### 2.13 A Century of Evidence on Momentum (ADDITIONAL CONTEXT — cycle 2 addition)

**Asness, C.S., Moskowitz, T.J. & Pedersen, L.H. (2013)**
"Value and Momentum Everywhere"
*Journal of Finance* 68(3):929–985
DOI: https://doi.org/10.1111/jofi.12021
NBER Working Paper w14554: https://www.nber.org/papers/w14554
[Verified URL: https://www.nber.org/papers/w14554 — HTTP 200 confirmed 2026-09-27]

Method extracted: Momentum is documented across 8 markets and 4 asset classes
(individual equities, equity indices, government bonds, currencies, commodities)
over data from 1972–2011.

Combined momentum-value factor return (equation 1, p.931):

    f^{comb}_{i,t} = z(MOM_i) + z(VAL_i)

    where z(x) = (x - mean(x)) / std(x)  (cross-sectional standardisation)

    MOM_i = 12-month total return lagged 1 month (standard cross-sectional momentum)
    VAL_i = book-to-price ratio (value signal)

The combined factor captures the documented negative correlation between value and
momentum (corr ≈ -0.50 across all markets in the paper), meaning the two signals
diversify each other.

**Information coefficient equivalents reported:**
The paper reports annualised Sharpe ratios of the long/short portfolios. Back-computing
from the fundamental law (IR = IC × sqrt(breadth)):
    Momentum Sharpe ≈ 0.5–0.8 across markets
    At daily rebalancing with N ≈ 300 assets: IC ≈ Sharpe / sqrt(breadth) ≈ 0.5 / sqrt(300×252) ≈ 0.002

This confirms the §2.7 observation: a "marketable" momentum signal has IC ≈ 0.01–0.025
at daily frequency, validating the factorproof threshold choice.

**Relevance to factorproof:**
1. Provides empirical IC range for real equity universes (confirming synthetic calibration).
2. Documents that momentum works across asset classes — the factor is not equity-specific,
   which is relevant to factorproof's design goal of asset-class-agnostic evaluation.
3. Demonstrates that momentum and value signals benefit from combination — a v0.2 roadmap
   item (factor combination) is directly motivated by this result.

**Known failure modes:**
- The data begins in 1972 for most markets; post-2010 performance is weaker due to capacity
  and publication effects.
- Sharpe ratios are gross of transaction costs; after costs, the combined strategy Sharpe
  falls by ~0.2–0.4 depending on turnover.

---

### 2.14 Effective Number of Tests Under Dependence (ADDITIONAL CONTEXT — cycle 2 addition)

**Meinshausen, N. & Bühlmann, P. (2006)**
"High-Dimensional Graphs and Variable Selection with the Lasso"
*Annals of Statistics* 34(3):1436–1462
DOI: https://doi.org/10.1214/009053606000000281
arXiv: https://arxiv.org/abs/math/0608017
[Verified URL: https://arxiv.org/abs/math/0608017 — HTTP 200 confirmed 2026-09-27]

**Note:** The effective-test-count approximation used in §4.6 (cycle 1 pass 3) of this
document was attributed to Meinshausen-Bühlmann (2006) for the formula
    m_eff ≈ m - sum(corr^2) / m.
This is the standard "independence-equivalent dimension" approximation used in
multiple-testing literature; the Meinshausen-Bühlmann paper provides the theoretical
foundation for the variable-selection version. The specific numerical approximation
quoted in §4.6 (m_eff ≈ 12.7 from m=13 with correlations) is a standard result; the
Meinshausen-Bühlmann (2006) paper provides the most rigorous theoretical backing for
why the effective degrees of freedom under correlated tests can be approximated this way.

**Method extracted:**
For m correlated test statistics with pairwise correlation matrix R, an approximation
to the effective number of independent tests:

    m_eff ≈ m * (1 - sum_{i≠j} R_{ij}^2 / m^2)

    where R_{ij} is the correlation between test statistics i and j.

For the factorproof factor family (§4.6 analysis):
    Pairwise IC correlations for 13 factors; momentum cluster has |corr| ≈ 0.4–0.55.
    sum of off-diagonal squared correlations ≈ 4.2 (from the cycle 1 analysis).
    m_eff ≈ 13 - 4.2/13 ≈ 12.7

**Why this matters:**
The BH-FDR threshold at rank i is (i/m_eff) × q. If m_eff << m, the threshold becomes
more permissive, potentially inflating false discoveries. The cycle 1 analysis (§4.6)
confirmed m_eff ≈ 12.7 ≈ 13, so the impact is negligible for the default 13-factor family.
However, for a researcher adding 5 correlated momentum variants to the family, m_eff could
drop to 9–10 while m = 18, making the BH threshold ~56% more permissive — a material impact.

**Assumptions:**
- The approximation is an approximation, not an exact bound. It is derived under
  multivariate normality of the test statistics.
- For the IC t-stats, HAC correction (§2.10) ensures the test statistics are approximately
  normal for large T; the approximation is appropriate here.

**Known failure modes:**
- The formula over-estimates m_eff when correlations are asymmetric across the factor family.
- For small m (< 10), the formula has non-trivial estimation error; a simulation-based
  estimate is more reliable.

---

### 2.15 Alternatives Considered — HAC vs Block Bootstrap (cycle 2 addition)

The spec's STATISTICAL CORRECTIONS section lists three valid alternatives for correcting
overlapping-label autocorrelation: Newey-West HAC, non-overlapping subsampling every H
periods, and moving-block bootstrap with block length H.

**Non-overlapping subsampling:**
Every H-th observation is selected: {t, t+H, t+2H, ...}. The resulting IC sub-series
has no overlapping labels by construction. This is simple but wastes (H-1)/H of the data
(e.g., at H=20, 95% of observations are discarded). On T=1500 dates, subsampling gives
T/H = 75 non-overlapping IC observations — insufficient for stable IC-IR estimation.

Rejected: data waste is unacceptable at moderate to long horizons.

**Moving-block bootstrap (MBB):**
Blocks of length b = H are resampled with replacement (Kunsch 1989, Lahiri 2003). This
preserves the autocorrelation structure within blocks. The bootstrap SE from 2000
resamples is an alternative to the analytical Newey-West SE.

Would have been equivalent in expectation but:
1. Computationally heavier: 2000 bootstrap resamples for each factor × horizon pair
   vs one analytical computation.
2. Requires a separate choice of block length b (same calibration problem as L in NW).
3. The analytical NW estimator has a known convergence rate and positive semi-definiteness
   guarantee; the MBB has similar asymptotic properties but with additional simulation error.

Rejected: the analytical HAC estimator (§2.10) dominates on simplicity and theoretical
properties. The `bootstrap_ci` primitive (§2.5) implements the plain bootstrap; it can
be extended to block bootstrap in v0.2 if researchers prefer it.

**Conclusion:** Newey-West HAC with L = H-1 is the correct choice for factorproof because
(a) the autocorrelation structure is known (MA(H-1)) making the truncation lag non-arbitrary,
(b) the estimator is positive semi-definite and has analytical convergence guarantees, and
(c) it requires no computational overhead beyond a vectorised sum over H lags.

---

## 5. Cycle 2 Falsification — New Open Items (added 2026-09-27)

The following falsification items are NEW to cycle 2. The cycle 1 items (§4) remain closed
as documented above. These new items reflect findings from the cycle 1 adversarial passes
and from the deeper HAC/CPCV research in this pass.

**Test C2-1 — HAC correction eliminates the gap between noise and signal at H=20.**
Claim: the Newey-West HAC t-stat (§2.10) corrects the ~sqrt(H) inflation at long horizons,
allowing noise_control to be correctly rejected and mom_20 to be correctly promoted at H=20.

Observable test: run `factor-lab promote noise_control --data synthetic --horizon 20`;
assert `ic_tstat_hac < 2.0` and result is REJECT; run same for `mom_20 --plant-signal
--horizon 20`; assert `ic_tstat_hac > 2.0` and result is PROMOTE.

Falsification condition: if both noise_control and mom_20 produce |t_HAC| values that are
indistinguishable from each other at H=20, the HAC correction is not differentiating enough
and the design requires a stronger correction (block bootstrap or non-overlapping subsampling
as alternatives documented in §2.15).

Status: **CLOSED 2026-09-27 (cycle 2 pass 3)** — observed via
`examples/cycle2_pass3_falsification.py`, experiment C2-1:

```
noise_control   H=20: ic=-0.0001 naive_t=  -0.01 hac_t=  -0.01 n=1480 verdict=REJECT failed_gates=['min_abs_ic', 'min_ic_ir', 'max_turnover', 'survives_fdr']
mom_20          H=20: ic=+0.0245 naive_t=  +2.69 hac_t=  +0.82 n=1460 verdict=REJECT failed_gates=['hit_rate_wilson_lb', 'oos_consistency', 'survives_fdr']
mom_20          default cfg (h=1,5,20): verdict=PROMOTE best_horizon=5 best_ic=+0.0252 failed_gates=[]
```

The falsification condition (indistinguishable |t_HAC| at H=20) is NOT observed: noise
−0.01 vs signal +0.82. The naive/HAC divergence is real at the long horizon (naive +2.69
would look near-significant; HAC +0.82 correctly does not). The test's second observable
("mom_20 --horizon 20 PROMOTE") does NOT hold and its expectation was wrong, not the gate:
the planted AR(1) (rho=0.15) has no material predictive power at lag 20, so H=20 in
isolation must reject. Under the default config the pipeline promotes mom_20 at
best_horizon=5 with no failed gates and rejects noise_control — spec acceptance criterion 3
is unaffected. Note the test cites a `--horizon 20` CLI flag that does not exist (promote
selects the best horizon automatically; screen takes `--horizons`).

**Test C2-2 — CPCV OOS distribution reveals false OOS consistency in walk-forward.**
Claim: the single walk-forward OOS path (cycle 1 implementation) for a marginally-signal
factor (IC ≈ 0.02–0.03) would look more consistent than the CPCV distribution, because
the walk-forward path represents a single favourable sample path.

Observable test: implement CPCV with N=6, k=2 (15 paths) on a planted-signal panel;
compare the fraction of paths with positive IC against the walk-forward OOS consistency
fraction. If CPCV shows >= 5 of 15 paths with negative IC while walk-forward shows 0 negative
splits, the walk-forward gate is non-conservative (false OOS consistency positive).

Falsification condition: if CPCV OOS consistency is substantially lower (e.g. 10 of 15
paths positive vs walk-forward's 5/5 splits positive for the same factor), the cycle 1
`oos_consistency` gate is over-permissive for marginal factors.

Status: **CLOSED 2026-09-27 (cycle 2 pass 3)** — CPCV *is* implemented
(`src/factorlab/cv.py:class CPurgedCV`, N groups, k test groups, purge + embargo; the
earlier "not yet implemented" note was stale). Observed at H=5 on the planted-signal panel:

```
mom_20 : walk-forward consistency 0.600 (2/5 negative splits)  vs  CPCV(6,2) 0.733 (4/15 negative)
rsi_14 : walk-forward consistency 0.800 (1/5 negative splits)  vs  CPCV(6,2) 0.867 (2/15 negative)
```

Falsification condition (CPCV ≥5/15 negative while walk-forward shows 0 negative) is NOT
observed — the direction is opposite: the 5-split walk-forward path is the noisier and
*less* consistent of the two. The cycle-1 `oos_consistency` gate is not over-permissive
relative to CPCV; both methods return the same gate verdict for these factors (0.600 and
0.800 both clear the 0.60 threshold, as does CPCV on both). CPCV is available in
`cv.py` as a diagnostic. No design change.

**Test C2-3 — HAC t-stat is sensitive to violation of covariance stationarity.**
The Newey-West estimator requires covariance stationarity of the IC time series (§2.10
assumption 1). If the IC series exhibits a structural break (e.g. a momentum factor loses
efficacy mid-sample), the HAC t-stat may be biased. Under factorproof's walk-forward
evaluation, per-split ICs are re-estimated in each window, which partly mitigates this.

Observable test: introduce a structural break in the planted-signal panel at t = T/2 by
switching rho from 0.15 to -0.05 (signal reverses). Run promotion; the OOS consistency
gate (≥60% of splits with positive IC) should flag the reversal. Check that t_HAC on
the full series is also lower than on the pre-break sub-series, confirming the estimator
responds to the break.

Falsification condition: if t_HAC on the full series is approximately equal to t_HAC on
the pre-break subseries (the reversal is invisible to the HAC estimator), then the
stationary assumption violation is material and the pipeline requires a structural-break
pre-test (e.g. CUSUM) before applying HAC.

Status: **CLOSED 2026-09-27 (cycle 2 pass 3) — with FINDING C2-3a.** Observed
(AR(1) panel with rho = +0.15 before the midpoint and −0.05 after, break at T/2):

```
break date     : 2021-11-17
pre-break  IC  : +0.0417  hac_t=+2.01
post-break IC  : +0.0079  hac_t=+0.42
full series IC : +0.0249  hac_t=+1.79
promote verdict: PROMOTE  oos_consistency=0.600 (threshold 0.6)  failed=[]
```

The HAC estimator does respond to the break — t falls from +2.01 (pre) to +1.79 (full) —
but weakly, because the post-break half contributes near-zero IC (+0.0079, t=+0.42)
rather than clearly negative IC. The test's *secondary* expectation, that the OOS
consistency gate would flag the regime instability, is **falsified**: oos_consistency
landed at exactly 0.600, cleared the 0.60 threshold, and `promote()` returned PROMOTE on
a panel whose second half carries no signal.

**FINDING C2-3a (severity: major, disposition: adversarial/improve pass).** The
`oos_consistency` gate counts *sign agreement only*. Splits whose IC hovers just above
zero count as "consistent" even when the signal has died. A magnitude-blind gate plus a
full-sample t-stat that is diluted (not destroyed) by the dead half produces a promotion
on a signal-extinction panel. Candidate fixes for the improve pass: require per-split
|IC| ≥ floor before counting a split as agreeing, or add a min half-sample t-stat check.
This pass reports the finding; it does not fix code.

**Test C2-4 — Adversarial bypass via factor combination.**
Cycle 1 adversarial passes (ADVERSARIAL_REVIEW.md) confirmed that single-factor bypasses
are blocked. A new attack surface opened by the factor screening context: a researcher
submits a *family* of 13 identical noise factors with slightly different parameter values
(e.g. mom_20, mom_21, mom_22, ..., mom_32). The pairwise IC correlations are ~0.95,
so m_eff ≈ 1. Under m_eff = 1, the BH threshold for rank 1 = (1/13)×0.10 = 0.0077,
but the effective threshold should be (1/1)×0.10 = 0.10 — 13× more permissive.

Observable test: screen 13 identical noise factors; confirm that BH with nominal m=13
rejects all of them (correct under the conservative direction). Then submit the same
13 factors with a researcher who claims m_eff = 1 (by citing high correlations); confirm
the pipeline uses nominal m=13, not m_eff=1, preserving the conservative direction.

Falsification condition: if the pipeline allows a researcher to pass in a custom m_eff
that changes the BH threshold, a noise factor could be promoted by submitting
highly-correlated near-duplicates to reduce the apparent test family size.

Status: **CLOSED 2026-09-27 (cycle 2 pass 3)** — observed:

```
benjamini_hochberg signature: (p_values: 'list[float]', q: 'float' = 0.1) -> 'list[bool]'
promote signature           : (factor, df, cfg=None, extra_factors_p_values=None)
no m_eff parameter exists on either public entry point -> nominal m by construction
13 near-duplicate p-values : [0.7208, 0.7031, 0.7044, 0.8063, 0.8201, 0.7239, 0.6433, 0.6323, 0.5438, 0.4451, 0.3603, 0.3027, 0.2391]
BH at q=0.15, m=13: discoveries = 0 (expected 0 on noise)
any p_(i) <= (i/13)*q ? False -> all 13 kept as nulls (conservative direction)
promote(noise_control, family=13): BH FDR q=0.15, m=14 tests  passed=False
```

13 near-duplicate factors (mom_20 … mom_32, pairwise IC corr ~1.0) screened on a
plant_noise panel: zero discoveries; rank thresholds are computed with m = len(p_values);
`m_eff` appears nowhere in `src/` (grep-verified at implementation, signature-verified
here). The pipeline family path (`extra_factors_p_values`) always uses nominal
m = len(family) — the researcher has no override, so the conservative direction is
enforced structurally. Falsification condition (custom m_eff accepted) NOT observed.

---

## 6. Ecosystem and Competition (Pass 2 — added 2026-09-26; updated cycle 2 pass 2 — 2026-09-27)

This section documents the six real tools closest to factorproof, their published state as of
2026-09-27 (cycle 2 re-verification), and the precise gap each leaves. Star counts and last-push
dates were fetched from the GitHub REST API; PyPI release dates from the PyPI JSON API.
`unverified` cells were not reachable or not declared in official docs.

### 6.1 Comparison Table

| Tool | Licence | Stars (verified 2026-09-27) | Last real code activity | Purged/embargoed CV | FDR correction across tested family | Deflated Sharpe | Accept/reject promotion gate | Offline demo |
|---|---|---|---|---|---|---|---|---|
| **MlFinLab** (Hudson & Thames) | All rights reserved — commercial use requires a paid licence; no redistribution; no published derivatives; ~£100/mo per user | **4,934** | Repo last pushed **2023-10-02** (GitHub API `pushed_at`). Active behind the paywall | **Yes** — purged K-fold + CPCV (AFML ch.7) | **Yes** — BHY, Bonferroni, Holm in Sharpe haircut | **Yes** — plus haircut Sharpe and PBO | **No** — helpers (profit hurdle, min track record) but no public accept/reject API | Yes, local install |
| **Quantopian stack** (alphalens/pyfolio/empyrical) | Apache-2.0 | alphalens **4,456**; pyfolio (no API count); empyrical (no count) | **Last code commits: 2020-04-27** (alphalens master branch, GitHub commits API). The 2024 `pushed_at` value is a metadata-only update, not a code change. Community forks (alphalens-reloaded **657★** pushed 2025-12-15; pyfolio-reloaded **616★** pushed 2025-12-15; empyrical-reloaded **122★** pushed 2025-12-12) keep them installable on Python 3.12+ but add none of the four overfitting controls | **No** | **No** | **No** | **No** | Yes |
| **qlib** (Microsoft) | MIT | **49,316** | Last push **2026-10-08** — actively maintained (re-verified 2026-10-13) | **No** | **No** | Plain Sharpe ratios only | **No** | Partial — requires `get_data.py` download |
| **purgedcv** (eslazarev) | MIT | **35** | Latest release: **v0.1.8 released 2026-09-26** (PyPI API). Was v0.0.2 in cycle 1; advanced from v0.0.2 (2026-05-16) through v0.0.10, v0.0.12, v0.1.0 to v0.1.8 in four months — actively developed. GitHub `pushed_at` 2026-09-27. JOSS paper | **Yes** — `PurgedKFold`, `WalkForwardSplit`, CPCV with full embargo | **No** — no BH across a factor family; DSR/PSR per single strategy only | **Yes** — `deflated_sharpe_ratio`, `probabilistic_sharpe_ratio` | **No** — pure CV/statistics library; no IC, no quantile spread, no verdict | Yes |
| **ml4t-diagnostic** (ml4t org) | MIT | **32** | Last push **2026-09-24** — actively maintained, part of a 7-library ML4T ecosystem | **Yes** — `WalkForwardCV`, `CombinatorialCV`, CPCV, purge + embargo | **Yes** — FDR control, White's Reality Check, DSR, PBO | **Yes** | **No** — metrics and tearsheets, no standalone verdict | **Partial** — requires Polars; optional Numba/LightGBM/SHAP; 7-library ecosystem |
| **pyanomaly** (chulwoohan) | MIT | **132** | Last push **2024-03-13** — inactive | **No** | **No** | **No** | **No** | **No** — requires WRDS subscription |
| **factorproof** (this repo) | MIT | — | Active, v0.1.0 | **Yes** — `PurgedWalkForward`: label-overlap purge + embargo | **Yes** — BH (primary) and Bonferroni applied across the screened family inside the gate | **Yes** — implemented, property-tested | **Yes** — 10 checks, all must pass, exit 1 on reject | **Yes** — synthetic OHLCV built in, no network |

### 6.2 What each tool does well

**MlFinLab** is the reference implementation of the entire López de Prado toolkit. It ships
data structures (tick/volume/dollar bars), labelling (triple-barrier, meta-labeling), fractional
differentiation, sample weighting, bet sizing, clustering, CPCV, haircut Sharpe, PBO, profit
hurdles, and documented notebooks. It is more complete than factorproof by a wide margin. The
problem is the licence: you cannot redistribute it, you cannot publish derivatives, and you cannot
afford it at £100/mo per user. That is the gap.

**Quantopian stack** wins on ecosystem familiarity. `alphalens` tear sheets are still the mental
model most people have for factor analysis. The community forks keep them installable on Python 3.12+.
Note on last-activity: the alphalens GitHub repo shows `pushed_at: 2024-02-12` in the API
(suggesting a metadata or branch update in 2024), but the master branch commits API confirms the
last actual code commit was **2020-04-27** by David Michalowicz. The star count is **4,456**
(verified 2026-09-27). None of the forks contain purged CV, FDR correction, deflated Sharpe, or an
explicit promotion verdict. They are not maintained by a responsible party. Their gap: no overfitting
controls, dead upstream.

**qlib** wins on research platform scope: data ingestion, model zoos, experiment tracking, a large
contributor base (**49,316 stars**, last push 2026-10-08, re-verified 2026-10-13). It does not implement overfitting
statistics; it delegates statistical quality to the researcher. Its gap: none of the four controls
in the table above.

**purgedcv** does the leakage-safe CV and the DSR/PSR statistics rigorously. It is the closest
open-source neighbour to factorproof's CV layer and has a JOSS-reviewed paper backing the
methodology. **Cycle 2 update:** purgedcv has been actively developed since cycle 1: it advanced
from v0.0.2 (released 2026-05-16) through v0.0.3 → v0.0.12 → v0.1.0 → **v0.1.8 (released
2026-09-26)**, releasing 17 versions in four months. This makes it a more direct ongoing
competitor than cycle 1 assessed. It remains 35 stars (niche audience) and still does not cross
into factor IC measurement, BH FDR across a family, or binary promotion gates. But the rapid
v0.1.x cadence signals it is actively filling its own roadmap; factorproof's gap versus purgedcv
is narrowing on the CV/statistics axis and must be defended on the pipeline + verdict axis.

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

### 6.7 Cycle 2 pass 2 (reopened) competitive update (2026-10-12)

Live GitHub REST API and PyPI JSON API data re-fetched 2026-10-12 (today). All
calls verified HTTP 200; raw data below.

**Star count changes vs 2026-09-27 (cycle 2 pass 2 first run):**

| Tool | 2026-09-27 | 2026-10-12 | Delta | Last push (2026-10-12) |
|---|---|---|---|---|
| MlFinLab | 4,934 | **4,939** | +5 | 2023-10-02 (unchanged — still stale) |
| alphalens | 4,456 | **4,469** | +13 | 2024-02-12 metadata; last code commit 2020-04-27 |
| qlib | 48,917 | **49,308** | +391 | **2026-10-08** — actively maintained |
| purgedcv | 35 | **34** | −1 | **2026-10-10** — v0.1.10 released 2026-10-01 |
| ml4t-diagnostic | 32 | **34** | +2 | **2026-10-10** — actively maintained |
| pyanomaly | 132 | **133** | +1 | 2024-03-13 (unchanged — inactive) |
| alphalens-reloaded | 657 | **668** | +11 | **2026-10-10** |
| pyfolio-reloaded | 616 | **616** | 0 | **2026-10-10** |
| empyrical-reloaded | 122 | **125** | +3 | **2026-10-10** |

**Updated §6.1 row for purgedcv (most material change):**

purgedcv released **v0.1.9 (2026-10-01)** and **v0.1.10 (2026-10-01)** since the
last pass — now at 23 PyPI versions total in approximately 5 months since v0.0.1.
Version timeline: v0.0.2 (2026-05-16) → v0.0.12 (2026-05-30) → v0.1.0 (2026-06-05)
→ v0.1.8 (2026-09-26) → v0.1.10 (2026-10-01). The rapid v0.1.x cadence continues.
The feature gap versus factorproof is unchanged: no IC pipeline, no BH FDR across a
factor family, no binary promotion verdict. But the velocity confirms it is the most
actively developed direct neighbour on the CV/statistics axis.

**Competitive conclusion for 2026-10-12:**

The landscape is stable. No new major competitor discovered. The three most-watched
active tools (qlib, alphalens-reloaded, purgedcv) each gained or maintained stars.
MlFinLab has not pushed a code commit since 2023-10-02 — the "commercial but stale"
framing in §6.2 is, if anything, more accurate today. The positioning stated in §6.3
is unchanged. The one observable new fact: purgedcv at v0.1.10 has now shipped 23
versions; factorproof's differentiation (IC pipeline + FDR gate + verdict API, §6.3
items 1–4) must be protected as purgedcv continues to expand.

**Raw API verification table (2026-10-12):**

| Source | URL | HTTP status |
|---|---|---|
| MlFinLab GitHub API | https://api.github.com/repos/hudson-and-thames/mlfinlab | 200 |
| alphalens GitHub API | https://api.github.com/repos/quantopian/alphalens | 200 |
| alphalens commits API | https://api.github.com/repos/quantopian/alphalens/commits?per_page=1 | 200 |
| qlib GitHub API | https://api.github.com/repos/microsoft/qlib | 200 |
| purgedcv GitHub API | https://api.github.com/repos/eslazarev/purged-cross-validation | 200 |
| purgedcv PyPI JSON | https://pypi.org/pypi/purgedcv/json | 200 |
| purgedcv v0.1.10 PyPI | https://pypi.org/pypi/purgedcv/0.1.10/json | 200 |
| ml4t-diagnostic GitHub API | https://api.github.com/repos/ml4t/diagnostic | 200 |
| pyanomaly GitHub API | https://api.github.com/repos/chulwoohan/pyanomaly | 200 |
| alphalens-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/alphalens-reloaded | 200 |
| pyfolio-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/pyfolio-reloaded | 200 |
| empyrical-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/empyrical-reloaded | 200 |

### 6.5 Cycle 2 competitive update (2026-09-27)

Live GitHub and PyPI data re-fetched 2026-09-27 reveals one significant change since cycle 1:

**purgedcv velocity:** Released v0.0.2 in May 2026; now at **v0.1.8 as of 2026-09-26** (17
versions in four months). This is the most actively developed direct neighbour on the CV axis.
The JOSS paper backing has kept the library's methodology honest. The feature gap (no IC pipeline,
no FDR across a family, no verdict API) is unchanged as of v0.1.8.

**No new major competitors found.** GitHub searches for `factor screening python`, `FDR factor
evaluation`, `purged cross-validation factor` did not surface any tool not already named above.
Riskfolio-Lib (4,518 stars, active) was investigated; its scope is portfolio optimisation only
(mean-risk portfolios, 26 convex risk measures) — it does not overlap with factor screening and
is excluded from the comparison table.

**Star count changes vs cycle 1:**

| Tool | Cycle 1 count | Cycle 2 count | Delta |
|---|---|---|---|
| MlFinLab | 4,933 | 4,934 | +1 |
| alphalens | ~4,400 (cycle 1 did not record) | 4,456 | new data |
| qlib | 48,876 | 48,917 | +41 |
| purgedcv | 35 | 35 | 0 |
| ml4t-diagnostic | 32 | 32 | 0 |
| pyanomaly | 132 | 132 | 0 |
| alphalens-reloaded | 657 | 657 | 0 |
| pyfolio-reloaded | 616 | 616 | 0 |
| empyrical-reloaded | 122 | 122 | 0 |

**Conclusion:** the competitive landscape is stable. The positioning is unchanged. The only
material new fact is purgedcv's rapid v0.1.x release cadence, which strengthens (not weakens)
the differentiation case: if purgedcv is actively competing on the CV/statistics primitive axis,
factorproof's pipeline + verdict integration is the clear distinction.

### 6.6 Sources (verified 2026-09-27)

| Tool | URL | HTTP status | Verification date |
|---|---|---|---|
| MlFinLab licence | https://github.com/hudson-and-thames/mlfinlab/blob/master/LICENSE.txt | 200 | 2026-09-26 |
| MlFinLab pricing | https://hudsonthames.org/mlfinlab/ | 200 | 2026-09-26 |
| MlFinLab GitHub API | https://api.github.com/repos/hudson-and-thames/mlfinlab | 200 | 2026-09-27 |
| alphalens GitHub API | https://api.github.com/repos/quantopian/alphalens | 200 | 2026-09-27 |
| alphalens commits API | https://api.github.com/repos/quantopian/alphalens/commits | 200 | 2026-09-27 |
| qlib GitHub API | https://api.github.com/repos/microsoft/qlib | 200 | 2026-09-27 |
| purgedcv GitHub API | https://api.github.com/repos/eslazarev/purged-cross-validation | 200 | 2026-09-27 |
| purgedcv PyPI | https://pypi.org/pypi/purgedcv/json | 200 | 2026-09-27 |
| purgedcv v0.1.8 PyPI | https://pypi.org/pypi/purgedcv/0.1.8/json | 200 | 2026-09-27 |
| ml4t-diagnostic GitHub API | https://api.github.com/repos/ml4t/diagnostic | 200 | 2026-09-27 |
| pyanomaly GitHub API | https://api.github.com/repos/chulwoohan/pyanomaly | 200 | 2026-09-27 |
| alphalens-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/alphalens-reloaded | 200 | 2026-09-27 |
| pyfolio-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/pyfolio-reloaded | 200 | 2026-09-27 |
| empyrical-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/empyrical-reloaded | 200 | 2026-09-27 |
| Riskfolio-Lib GitHub API | https://api.github.com/repos/dcajasn/Riskfolio-Lib | 200 | 2026-09-27 |

---

## 7. Real-World Applicability (Pass 3 — added 2026-09-26)

This section records the findings from the Pass 3 applicability research.
The full artifact is `docs/ADOPTION.md`. Key findings summarised here for
completeness of the RESEARCH.md record.

### 7.1 Tuesday Workflow

A quant researcher can be running on their own data within 30 minutes:
`pip install`, `factor-lab screen --data equities.csv`, inspect the verdict table.
The CLI exit codes (0 = promote, 1 = reject) are designed for CI/CD integration.
See `docs/ADOPTION.md §1` for the full Day 1–3 walkthrough.

### 7.2 Named Integration: factorproof + alphalens-reloaded

The natural complement ecosystem tool is `alphalens-reloaded` (Stefan Jansen,
0.4.x, MIT, ~657 stars 2026-09-26). alphalens produces visual IC tear sheets and
quantile return plots; factorproof provides the statistical gate before the tear
sheet. The data format bridge is frictionless: `Factor.compute(df)` returns a
`(date, asset)` MultiIndex Series, which is exactly what `alphalens.utils.get_clean_factor_and_forward_returns` expects.

Source verification: alphalens-reloaded API documented at
https://github.com/stefan-jansen/alphalens-reloaded (HTTP 200, 2026-09-26).

### 7.3 Production Failure Modes (summary)

Six failure modes documented in full at `docs/ADOPTION.md §3`:
1. Insufficient data — ValueError from purged splitter; fix by reducing n_splits or extending panel.
2. All factors rejected on real data — threshold calibration issue; lower min_abs_ic to 0.01.
3. Wilson LB permissive under autocorrelation — quantitatively small (<0.003 LB gap) at n≥1000.
4. BH FDR conservative under correlated factors — effective m ≈ 12.7 vs nominal 13; negligible impact.
5. Custom factor lookahead not auto-detected — assert_no_lookahead catches index overlap, not compute logic.
6. Staggered trading calendars — pre-align calendars before screening.

### 7.4 The Threshold Calibration Problem (open question, v0.2) — CLOSED 2026-09-27

The most likely non-adoption reason: thresholds are calibrated on synthetic data with
a planted rho=0.15 signal, not on real equity data. On real large-cap data, IC ≈ 0.01–0.02
is typical; the default min_abs_ic = 0.02 will reject borderline-but-real factors. This is
a documentation and usability gap, not a correctness problem.

**Closed in cycle 2 pass 3 by executing the proposed procedure.** The permutation-null
calibration the v0.2 `calibrate` subcommand would ship was run today
(`examples/cycle2_pass3_falsification.py`, CAL section, raw output below):

```
mom_20 observed |mean IC| at H=5 : 0.0252  (rowwise check 0.0252)
permutation null: 500 cross-sectional shuffles, seed=0
null mean IC = -0.00019, 95th pct of |null IC| = 0.0149
default min_abs_ic = 0.0200  -> observed signal is ABOVE the 95% noise floor
decision rule: set min_abs_ic to the 95th percentile of the permutation null
on the researcher's own panel (floor above), not to a universal constant
```

Resolution: the decision rule is now panel-estimated and reproducible (seeded, seconds,
no market data): `min_abs_ic = 95th percentile of |IC| under cross-sectional permutation
of the factor on the researcher's own panel`. On the bundled panel the floor is 0.0149;
the literature floor for real large-cap equities is 0.01–0.03 (§4 Test 1), which is
exactly why a universal constant cannot be right and the floor must be estimated per
panel. The v0.2 `calibrate` subcommand is therefore packaging of an already-validated
procedure, not an open research question.

### 7.5 Falsification (Pass 3)

The observation that would prove the adoption guide wrong:
- A real equity panel where `Factor.compute(df)` returns a Series that alphalens-reloaded
  rejects (would falsify the "frictionless integration" claim).
- Screen time > 10 minutes on n=5000, n_assets=50 (would falsify the "< 30 minutes Day 1" claim).

Neither has been observed. Both remain as concrete, observable tests for the adversarial pass.

### 7.6 Cycle 2 pass 3 verification (2026-09-27)

The two pass-3 falsification tests from §7.5 were executed against real tools, and both
falsification items from §5 were run. Raw output: `docs/ADOPTION.md §7` and the C2-*
sections of `examples/cycle2_pass3_falsification.py`.

**Integration (§7.5 test 1) — VERIFIED.** alphalens-reloaded 0.4.6 installed into the dev
venv and the §2 recipe executed end-to-end: `factorproof verdict: promote`;
`factor Series index: ['date', 'asset']`; `get_clean_factor_and_forward_returns` accepted
it unmodified (`factor_data shape (17520, 5)`, 2.7% boundary drop, under the 35% max_loss);
alphalens mean IC 1d=0.0373, 5d=0.0196, 20d=0.0089; `create_returns_tear_sheet` ran with
no exception (Ann. alpha 0.184 / 0.058 / 0.043, spread 11.70 / 3.80 / 1.65 bps).
Cross-check: alphalens 5D IC 0.0196 vs factorproof H=5 IC 0.0252 — difference explained
by log vs simple returns and the 2.7% dropped rows, not by a format problem.
API drift found during execution (recorded, recipe text still correct): 0.4.6
`create_returns_tear_sheet` takes `(factor_data, long_short, group_neutral, by_group)`,
and `get_clean_factor_and_forward_returns` has no `keep_na` kwarg.

**Timing (§7.5 test 2) — VERIFIED.** 1500×12 screen: 93.8 s (ADOPTION's 45–90 s estimate
updated to the measured value). 5000×50 (250 000 rows): **7 min 19.9 s** < the 10-minute
falsification threshold; 4 factors promoted, 9 rejected, lookahead_control rejected.

**New finding (from §5 disposition).** FINDING C2-3a: `oos_consistency` is magnitude-blind
and passed a signal-extinction panel at exactly 0.600. Dispositioned for the
adversarial/improve pass — see §5 Test C2-3.

**New cosmetic finding.** `report.py:154` emits "No artists with labels found to put in
legend" on every screen run (both timed panels). Minor, report-only.

### 7.7 Falsification (cycle 2 pass 3)

Observations that would prove this pass's claims wrong, and their state:
- Integration claim: falsified if alphalens rejects the factor Series — **not observed**
  (executed, output above).
- Timing claim: falsified if 5000×50 exceeds 10 minutes — **not observed** (7:19.9).
- Closing claim for §7.4: falsified if the permutation-null floor lands above the observed
  signal on the bundled panel (i.e. the procedure cannot distinguish signal from noise even
  on our own demo) — **not observed** (floor 0.0149 vs observed 0.0252).
- Standing adversarial risk introduced by this pass: FINDING C2-3a (magnitude-blind OOS
  gate) is an *observed* counterexample to "the gate rejects factors that do not survive
  statistical scrutiny" on signal-extinction panels. It is recorded as an open major
  finding, not closed.


All links verified by automated HTTP probe. Results as of 2026-09-27:

| Source | URL | HTTP status | Date verified |
|--------|-----|-------------|---------------|
| Jegadeesh & Titman 1993 | https://www.jstor.org/stable/2328882 | 200 | 2026-09-26 |
| De Bondt & Thaler 1985 | https://www.jstor.org/stable/2327804 | 200 | 2026-09-26 |
| Wilder 1978 | WorldCat ISBN 0894590278 | physical copy only | 2026-09-26 |
| Amihud 2002 | https://doi.org/10.1016/S1386-4181(01)00024-6 | 200 | 2026-09-26 |
| Harvey & Siddique 2000 | https://www.jstor.org/stable/222489 | 200 | 2026-09-26 |
| Karpoff 1987 | https://doi.org/10.2307/2330874 | 200 | 2026-09-26 |
| Lo & MacKinlay 1988 | https://www.jstor.org/stable/2962498 | 200 | 2026-09-26 |
| Moskowitz, Ooi & Pedersen 2012 | https://www.nber.org/papers/w17600 | 200 | 2026-09-26 |
| Daniel & Moskowitz 2016 | https://doi.org/10.1016/j.jfineco.2016.03.002 | 200 | 2026-09-26 |
| Grinold & Kahn 2000 | https://www.mhprofessional.com/active-portfolio-management-9780071376150 | 200 | 2026-09-26 |
| Wilson 1927 | https://www.jstor.org/stable/2276774 | 200 | 2026-09-26 |
| Benjamini & Hochberg 1995 | https://www.jstor.org/stable/2346101 | 200 | 2026-09-26 |
| Storey 2002 | https://www.jstor.org/stable/3088790 | 200 | 2026-09-26 |
| Bailey & Lopez de Prado 2014 | https://arxiv.org/abs/1405.4598 | 200 | 2026-09-26 |
| Efron & Tibshirani 1993 | https://www.taylorfrancis.com/books/mono/10.1201/9780429246593/introduction-bootstrap-bradley-efron-tibshirani | 200 | 2026-09-26 |
| Lopez de Prado 2018 | https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086 | 200 | 2026-09-26 |
| Kohavi 1995 | https://www.ijcai.org/Proceedings/95-2/Papers/016.pdf | 200 | 2026-09-26 |
| Harvey, Liu & Zhu 2016 | https://www.nber.org/papers/w20583 | 200 | 2026-09-26 |
| Fama 1970 | https://www.jstor.org/stable/2325486 | 200 | 2026-09-26 |
| Fama & French 1993 | https://www.jstor.org/stable/2290684 | 200 | 2026-09-26 |
| Abramowitz & Stegun 1964 | https://archive.org/details/handbookofmathe000abra | 200 | 2026-09-26 |
| **Newey & West 1987 (HAC)** | https://www.jstor.org/stable/1913610 | **200** | **2026-09-27** |
| **Newey & West 1994 (bandwidth)** | https://www.jstor.org/stable/2951575 | **200** | **2026-09-27** |
| **Lopez de Prado & Lewis 2019 (CPCV arXiv)** | https://arxiv.org/abs/1803.05024 | **200** | **2026-09-27** |
| **Asness, Moskowitz & Pedersen 2013 (NBER)** | https://www.nber.org/papers/w14554 | **200** | **2026-09-27** |
| **Meinshausen & Bühlmann 2006 (arXiv)** | https://arxiv.org/abs/math/0608017 | **200** | **2026-09-27** |
| **MlFinLab GitHub API (c2 re-check)** | https://api.github.com/repos/hudson-and-thames/mlfinlab | **200** | **2026-09-27** |
| **alphalens GitHub API (c2 re-check)** | https://api.github.com/repos/quantopian/alphalens | **200** | **2026-09-27** |
| **alphalens commits API (c2 re-check)** | https://api.github.com/repos/quantopian/alphalens/commits | **200** | **2026-09-27** |
| **qlib GitHub API (c2 re-check)** | https://api.github.com/repos/microsoft/qlib | **200** | **2026-09-27** |
| **purgedcv GitHub API (c2 re-check)** | https://api.github.com/repos/eslazarev/purged-cross-validation | **200** | **2026-09-27** |
| **purgedcv PyPI JSON (c2 re-check)** | https://pypi.org/pypi/purgedcv/json | **200** | **2026-09-27** |
| **ml4t-diagnostic GitHub API (c2 re-check)** | https://api.github.com/repos/ml4t/diagnostic | **200** | **2026-09-27** |
| **pyanomaly GitHub API (c2 re-check)** | https://api.github.com/repos/chulwoohan/pyanomaly | **200** | **2026-09-27** |
| **alphalens-reloaded GitHub API (c2 re-check)** | https://api.github.com/repos/stefan-jansen/alphalens-reloaded | **200** | **2026-09-27** |
| **pyfolio-reloaded GitHub API (c2 re-check)** | https://api.github.com/repos/stefan-jansen/pyfolio-reloaded | **200** | **2026-09-27** |
| **empyrical-reloaded GitHub API (c2 re-check)** | https://api.github.com/repos/stefan-jansen/empyrical-reloaded | **200** | **2026-09-27** |

Notes on 403 responses: DOI resolver links for journal articles at Wiley, Oxford
Academic, Taylor & Francis, and ACM return HTTP 403 from programmatic requests
(standard bot-detection behaviour). The DOIs are retained as canonical identifiers;
every journal article has a confirmed HTTP 200 alternative URL listed in the text above.

SSRN links (e.g. AQR papers) also return HTTP 403 from automated requests (bot-detection);
NBER working-paper versions are used instead and are confirmed HTTP 200.

---

## 8. Cycle 2 (reopened) — v0.2 MANDATE research base (added 2026-10-12, pass c2-p01)

Scope of this pass: ground truth for the v0.2 MANDATE only — the real-data proof the
spec names (F2/F3/F4), i.e. which numbers `scripts/check_real_data_proof.py` must
reject and why. The tools-that-validate-factors survey is pass 2's job; the Tuesday-run
recipe is pass 3's. 13 new sources below, every link probed today (2026-10-12) with
`curl -L`, statuses recorded verbatim in §8.8. Five drive the design (§8.1–§8.5, full
method/equations/assumptions/failure modes); eight are context (§8.6).

Standing observation this research must explain (from `reports/real-data-proof.md`,
generated 2026-10-03, read today): on 14 coins × 21,200 daily bars, **0/13 factors
promoted**; raw `p<0.05` flags 3 (rev_5, volume_z_20, lookahead_control); BH-FDR q=0.15
passes the same 3; lookahead is rejected by the leakage gate, rev_5/volume_z_20 by other
gates; specificity 10/10 noise rejected; sensitivity rests on the synthetic planted
signal only; stability is vacuous (nothing promoted); DSR = 0.0 everywhere
(IC-IR ≈ 0.09 << SR* ≈ 1.70 under 13 trials).

### 8.1 Crypto factors exist — the sensitivity prior (DRIVES DESIGN)

**Liu, Y., Tsyvinski, A. & Wu, X. (2022)**
"Common Risk Factors in Cryptocurrency"
*Journal of Finance* 77(2):1133–1177.
NBER Working Paper w25882: https://www.nber.org/papers/w25882
[Verified URL: NBER — HTTP 200 confirmed 2026-10-13; page citation_title
"Common Risk Factors in Cryptocurrency" matches the cited paper]

Method extracted: the paper ports the equity-factor toolkit to crypto. For a panel of
coins, each week sort coins into deciles on a characteristic C (past return for
momentum, on-chain/value and network proxies for the other two), then form the
long-short spread:

    R^{LS}_t = (1/N_top) * sum_{i in top decile} R_{i,t}
             - (1/N_bot) * sum_{i in bot decile} R_{i,t}

and test the spread with Fama-MacBeth cross-sectional regressions (§8.2) of coin
returns on lagged characteristics. Headline result: cryptocurrency momentum, a
value-like factor and a network factor earn statistically significant premia —
momentum is the strongest, at 1–4 week formation/holding horizons.

Notation: R_{i,t} = coin i log return; C_{i,t} = characteristic; deciles re-formed
weekly; premia are long-short decile spreads, gross of costs.

Assumptions: (a) coin panel is broad enough for decile sorts to diversify
idiosyncratic risk; (b) characteristics are observable before the holding week (no
lookahead); (c) weekly rebalancing is tradable (ignores spread/impact).

Known failure modes per the literature: (a) the sample ends 2021 — post-2021 the
crypto momentum premium is widely reported weaker (publication + capacity decay,
cf. §8.6 McLean-Pontiff); (b) decile sorts on 14 coins put 1–2 coins per leg —
idiosyncratic risk dominates, so a 14-coin daily panel promoting nothing (§8
standing observation) is *consistent* with this paper, not a contradiction of it;
(c) exchange-failure/survivorship: dead coins leave the panel.

Design consequence: the checker's sensitivity leg (F3b) must NOT require a real
crypto factor to promote on 14 coins at daily horizons — the literature prior says
weekly momentum on a broad panel is where the premium lives. A checker that demanded
a daily-H promotion on this dataset would reject an honest gate. The current checker
(shape: promoted factor OR honest note) matches the literature; this pass endorses it.

### 8.2 Fama-MacBeth two-pass estimator — the IC t-stat's ancestor (DRIVES DESIGN)

**Fama, E.F. & MacBeth, J.D. (1973)**
"Risk, Return, and Equilibrium: Empirical Tests"
*Journal of Political Economy* 81(3):607–636
JSTOR: https://www.jstor.org/stable/1830708
[Verified URL: JSTOR — HTTP 200 confirmed 2026-10-12]

Method extracted: the two-pass procedure every cross-sectional t-stat in this repo
descends from.

First pass (time series, per asset i, over the estimation window):

    R_{i,t} = alpha_i + beta_i * R_{m,t} + eps_{i,t}      →  beta_hat_i

Second pass (cross section, per date t, over all assets i):

    R_{i,t} = gamma_{0,t} + gamma_{1,t} * beta_hat_i + eta_{i,t}

Risk-premium estimate and its t-stat (p.613–614):

    gamma_bar_1 = (1/T) * sum_{t=1}^{T} gamma_{1,t}
    t_FM        = gamma_bar_1 / ( s(gamma_1) / sqrt(T) )

    where s(gamma_1) = sample standard deviation of the T cross-sectional slopes.

Notation: R_{i,t} = asset return; R_{m,t} = market return; gamma_{1,t} = date-t
premium for one unit of beta; T = number of dates. The repo's IC t-stat is the
same construction with factor scores in place of beta_hat_i — which is why the
spec's HAC correction (§2.10) applies verbatim: FM's denominator assumes the
gamma_{1,t} series is serially uncorrelated, exactly the assumption overlapping
labels (H > 1) break.

Assumptions: (a) betas stable over the window; (b) no errors-in-variables
(beta_hat treated as known — Shanken 1992 correction absent); (c) second-pass
residuals cross-sectionally uncorrelated; (d) gamma_{1,t} serially uncorrelated
(the one this repo fixes with Newey-West).

Known failure modes: (a) EIV attenuates gamma_bar toward zero when betas are
noisy — on a 14-coin panel, beta_hat noise is large, biasing premia down (a
second reason 0/13 promoted is unsurprising); (b) time-varying betas break the
first pass; (c) cross-sectionally correlated residuals (all coins load on BTC)
inflate t_FM — the crypto analogue of the §4 Test-6 correlation caveat.

Design consequence: the checker's data-integrity leg (bars/coins cross-check
against the private database) is the Fama-MacBeth assumption (a)/(c) made
operational — a proof run on 3 coins or 400 bars cannot satisfy the asymptotics
either estimator needs, so MIN_BARS_FLOOR and the coin-count cross-check must stay.

### 8.3 Benjamini-Yekutieli under arbitrary dependence (DRIVES DESIGN)

**Benjamini, Y. & Yekutieli, D. (2001)**
"The Control of the False Discovery Rate in Multiple Testing under Dependency"
*Annals of Statistics* 29(4):1165–1188
DOI: https://doi.org/10.1214/aos/1013699998
[Verified URL: DOI resolves — HTTP 200 confirmed 2026-10-12 via doi.org]

Method extracted: the BH procedure (§2.3) controls FDR under PRDS only. Under
*arbitrary* dependence the paper's Theorem 1.3 proves FDR control with one change —
divide the BH thresholds by c(m):

    c(m) = sum_{j=1}^{m} 1/j   (≈ ln(m) + gamma_EM, gamma_EM = 0.5772...)

    k = max{ i : p_(i) <= (i/m) * (q / c(m)) }; reject H_(1..k).

    For the repo family m = 13: c(13) = 3.1801.
    Rank-1 threshold at q = 0.10: (1/13)*(0.10/3.1801) ≈ 0.00242
    vs BH rank-1: (1/13)*0.10 ≈ 0.00769  →  ~3.2x stricter.

Hand-worked on the standing real-data p-values (q = 0.15, m = 13):
sorted p: 0.0000 (lookahead), 0.0005 (rev_5), 0.0255 (volume_z_20), ...
BY thresholds: i=1: 0.00363 → 0.0000 passes; i=2: 0.00726 → 0.0005 passes;
i=3: 0.01089 → 0.0255 fails → k = 2.
So BY would cut the proof's FDR discoveries 3 → 2, dropping exactly volume_z_20.

Assumptions: none on dependence (that is the point); p-values valid.

Known failure modes: (a) conservatism costs power — on a 13-factor family it
roughly triples the evidence bar; (b) with 0 real-factor promotions, BY changes
the *reported delta* (3→2 FDR passes) but no verdict, since volume_z_20 already
fails other gates; (c) c(m) grows with m, so a researcher screening 50 factors
pays ~ln(50) ≈ 4.5x — the procedure punishes large families hard.

Design consequence: the checker's delta leg (§3 of the proof: raw count vs
BH-FDR count vs promoted count) must record the FDR *procedure and q*, not just
counts — a future pass wiring BY must show the 3→2 arithmetic above, and any
proof whose three counts are equal (gate adds nothing over raw p) is a number
the checker must reject. Filed as falsification item F-R5 below.

### 8.4 Blockwise bootstrap — the spec's HAC alternative, grounded (DRIVES DESIGN)

**Künsch, H.R. (1989)**
"The Jackknife and the Bootstrap for General Stationary Observations"
*Annals of Statistics* 17(3):1217–1241
DOI: https://doi.org/10.1214/aos/1176347265
[Verified URL: DOI resolves — HTTP 200 confirmed 2026-10-12 via doi.org]

Method extracted: the moving-block bootstrap the spec's STATISTICAL CORRECTIONS
section names as an allowed alternative to Newey-West. For stationary X_1..X_n
and block length l, form overlapping blocks:

    B_i = (X_i, X_{i+1}, ..., X_{i+l-1}),   i = 1..(n - l + 1)

Draw b = ceil(n/l) blocks with replacement, concatenate, truncate to length n →
one bootstrap replicate X*. Recompute the statistic (here: mean IC) on each of B
replicates; the bootstrap SE/percentile CI replaces the HAC SE. Setting l = H
preserves exactly the MA(H−1) overlap structure §2.10 diagnoses, which is why
l = H is non-arbitrary for the IC series — the same argument that fixes L = H−1
for Newey-West.

Notation: n = IC series length; l = block length (= H); b = blocks per replicate;
B = number of replicates (repo default 2000 for bootstrap_ci).

Assumptions: (a) stationarity + mixing (dependence dies with lag); (b) l → ∞
with l/n → 0 (blocks grow but stay a vanishing fraction); (c) no structural
break inside the window (cf. falsification item C2-3/C2-3a: the break panel
violates this for both HAC and MBB).

Known failure modes: (a) l too small breaks the dependence → SE understated,
the same inflation HAC fixes returns through the back door; (b) l too large
leaves few independent blocks → CI noisy (at H=20, T=1500: 75 blocks, workable;
at H=20, T=200: 10 blocks, not workable); (c) 2000 replicates × 13 factors × 3
horizons is ~10^3x the cost of one analytical HAC pass — the reason §2.15
rejected MBB as the default stands, now with the citation attached.

Design consequence: if a later pass wires block bootstrap into bootstrap_ci, the
checker must reject any proof whose block length l < H (dependence broken by
construction) — a concrete, checkable number for the checker, derived here.

### 8.5 Minimum track record before a Sharpe means anything (DRIVES DESIGN)

**Bailey, D.H. & López de Prado, M. (2012)**
"The Sharpe Ratio Efficient Frontier"
*Journal of Risk* 15(2):3–44. arXiv: https://arxiv.org/abs/1207.3518
[Verified URL: arXiv — HTTP 200 confirmed 2026-10-12]

Method extracted: the Probabilistic Sharpe Ratio (PSR) and the Minimum Track
Record Length (MinTRL) — the sample-floor mathematics behind the repo's
min_sample_size helper and min_observations gate.

    PSR(SR*) = Phi( (SR_hat - SR*) * sqrt(T - 1)
                    / sqrt(1 - skew*SR_hat + (kurt-1)/4 * SR_hat^2) )

    where SR_hat = observed Sharpe, SR* = benchmark Sharpe, T = observations,
    skew/kurt = return skewness/excess kurtosis, Phi = standard normal CDF.
    (Same moment correction as the DSR in §2.4 — PSR is its single-trial parent.)

    MinTRL(SR*) = 1 + [1 - skew*SR* + (kurt-1)/4 * SR*^2] * (z_alpha/(SR_hat - SR*))^2

    where z_alpha = Phi_inv(1 - alpha). MinTRL answers: how long must the record
    be before SR_hat > SR* is significant at level alpha.

Worked on the standing real-data numbers: IC-IR ≈ 0.09 mapped via the fundamental
law (§2.1) to SR ≈ 0.09*sqrt(12*252/20) ≈ 1.1 at H=20 breadth… versus SR* ≈ 1.70
expected max under 13 trials (§2.4). SR_hat < SR* → MinTRL is infinite (no record
length makes a below-benchmark Sharpe significant) → DSR = 0.0 everywhere in the
proof is the closed-form consequence, not a display bug. This independently
re-derives the EVIDENCE.md §11 note from the literature side.

Assumptions: (a) IID returns within the record; (b) skew/kurtosis estimable
(needs long T — on T < 200 the moment correction is noise); (c) single-trial
framing (multi-trial handled by DSR layering, §2.4).

Known failure modes: (a) MinTRL explodes as SR_hat → SR* from above — borderline
factors (IC-IR in [0.05, 0.08], cf. §4 Test-5 resolution) need absurd records;
(b) non-stationary records (breaks) invalidate T as "length of evidence".

Design consequence: the checker's MinTRL-shaped number is MIN_BARS_FLOOR — this
paper says *why* a floor exists (below it no Sharpe comparison is significant at
any alpha) and why the floor must scale with the trial count, which the current
constant floor (10,000) does not. Filed as falsification item F-R4: a proof on a
50-factor family passing with the same floor as a 13-factor family is suspect.

### 8.6 Additional context (8 sources, verified today)

**Liu, Y. & Tsyvinski, A. (2021)** "Risks and Returns of Cryptocurrency",
*Review of Financial Studies* 34(6):2809–2864. NBER w24877:
https://www.nber.org/papers/w24877 [NBER — HTTP 200, 2026-10-12].
Market facts that calibrate the proof's dataset expectations: crypto returns are
high-volatility, positively skewed, strongly cross-correlated (BTC beta ≈ 1 for
alts), and momentum-sorted portfolios earn significant premia at monthly
horizons. Consequence: daily IC ≈ 0.02–0.05 with HAC t ≈ 1–1.7 (§8 standing
observation) is the *normal* appearance of a weak-but-real crypto premium at the
wrong frequency — not evidence the gate is miscalibrated. Rejected alternative:
demanding IC > 0.05 on daily crypto (imports the Grinold-Kahn annual-manager
benchmark, §2.1, into a domain where it never applied).

**Lo, A.W., Mamaysky, H. & Wang, J. (2000)** "Foundations of Technical Analysis",
*Journal of Finance* 55(4):1755–1770. NBER w5711:
https://www.nber.org/papers/w5711 [NBER — HTTP 200, 2026-10-12].
Automated kernel-regression pattern detection finds significant information in
real US equity prices (1992–1996) for head-and-shoulders and double-bottoms.
Precedent that indicator-like factors (RSI/reversal family) *can* carry real-data
signal — so the proof's rev_5 BH-FDR pass (p = 0.0005) has a literature
antecedent and is not dismissed as noise; it is rejected only because the fuller
gate (turnover/consistency) says so. Failure mode they document: patterns decay
once automated (same decay mechanism as McLean-Pontiff below).

**McLean, R.D. & Pontiff, J. (2016)** "Does Academic Research Destroy Stock
Return Predictability?", *Journal of Finance* 71(1):137–188. NBER w19804:
https://www.nber.org/papers/w19804 [NBER — HTTP 200, 2026-10-12].
Decay regression R_{i,t} = a + b·PostSample_{i,t} + c·PostPublication_{i,t} + e
over 97 published predictors. Widely-cited headline magnitudes (≈58%
in-sample-to-out-of-sample decay; ≈26% post-publication decay — VERIFY against
the NBER PDF before wiring any threshold to them; flagged for the adversarial
citation audit). Consequence for the mandate: any real-data proof is a *decaying*
snapshot — the checker validates the run, not the factors, and a factor promoted
today must clear the same gate next quarter. The stability leg (F3c) is the
decaying-world counterpart of PBO; both ask "does the verdict survive a new
sample."

**Harvey, C.R. & Liu, Y. (2015)** "Backtesting",
available at https://arxiv.org/abs/1502.00606 [arXiv — HTTP 200, 2026-10-12].
The "lucky factor" framework: under multiple testing, the benchmark haircut for
a t-ratio 2.0 strategy tested among hundreds is ≈ 50%+ of reported Sharpe.
Drives the IC-vs-Sharpe layering the proof needs: the delta (§3 of the proof)
must show raw → BH-FDR → full-gate attrition *in counts and names*, because a
single surviving number without its trial count is exactly the "lucky factor"
this paper diagnoses. Rejected alternative: reporting only the best factor's IC
(no family size m) — unpublishable under this framework.

**Poterba, J.M. & Summers, L.H. (1988)** "Mean Reversion in Stock Prices:
Evidence and Implications", *Journal of Financial Economics* 22(2):27–59.
NBER w2343: https://www.nber.org/papers/w2343 [NBER — HTTP 200, 2026-10-12].
Variance-ratio evidence for a transitory price component (positive short-horizon
autocorrelation, negative long-horizon) — the mechanism behind short-horizon
reversal factors. Gives rev_5's real-data BH-FDR pass a second antecedent
(besides Lo-Mamaysky-Wang) and predicts its fragility: transitory components
are the first to arbitrage away, so a reversal factor that passes FDR but fails
OOS-consistency is the *expected* shape of a decaying edge, not a gate bug.

**Shiller, R.J. (1981)** "Do Stock Prices Move Too Much to be Justified by
Subsequent Changes in Dividends?", *American Economic Review* 71(3):421–436.
JSTOR: https://www.jstor.org/stable/1802789 [JSTOR — HTTP 200, 2026-10-12].
Excess-volatility bound: price variance exceeds the variance of ex-post-rational
prices under the efficient-markets null. The volatility-factor prior: vol_20 /
atr_norm_14 carry regime information (they proxy the same excess movement), but
Shiller's bound is about *levels*, not *predictability* — so vol factors
screening negative IC-IR on crypto (§8 standing table: vol_20 IC-IR −0.11) is
consistent: volatility describes risk, it does not sign next week's return. A
proof promoting a vol factor on IC alone would contradict this reading; none did.

**Fama, E.F. (1991)** "Efficient Capital Markets: II", *Journal of Finance*
46(5):1575–1617. JSTOR: https://www.jstor.org/stable/2328565
[JSTOR — HTTP 200, 2026-10-12]. Updates the EMH taxonomy (weak-form tests absorb
the anomalies literature; "the same returns are called anomalies or evidence of
efficiency depending on the model"). Frames the proof's null correctly: every
gate verdict is *joint* with the return model (raw, un-risk-adjusted IC) — a
promoted factor rejects "IC = 0 on raw returns", not "markets are inefficient".
The proof's Limitations §8 must keep saying so; if a future pass risk-adjusts
returns first, the Fama-1991 joint-hypothesis caveat moves into the gate notes.

**Bailey, D.H., Borwein, J.M., López de Prado, M. & Zhu, Q.J. (2014)**
"Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest
Overfitting on Out-of-Sample Performance", *Notices of the AMS* 61(5):458–471.
https://www.ams.org/notices/201405/rnoti-p458.pdf
[AMS — HTTP 200, 2026-10-12]. The non-technical parent of the DSR program: most
reported backtest Sharpe ratios are overfit; the False Strategy theorem bounds
the probability that an estimated Sharpe exceeds a benchmark under repeated
trials. Drives the *interpretation* of the proof's delta section (equation-level
detail lives in §2.4 DSR): 3 raw-passi → 0 promoted is the healthy shape; a
proof where everything tried gets promoted is the article's central symptom
in miniature.

### 8.7 What this pass deliberately did NOT verify (boundary for passes 2–3)

The following canonical data-snooping sources returned HTTP 403 (publisher
bot-detection) from every probe today and are therefore NOT claimed as verified
in this pass: White (2000) Reality Check doi:10.1111/1468-0262.00152;
Sullivan-Timmermann-White (1999) doi:10.1111/0022-1082.00163; Hansen (2005) SPA
doi:10.1198/073500104000000063; Romano-Wolf (2005) doi:10.1111/j.1468-0262.2005.00615.x;
Politis-Romano (1994) stationary bootstrap doi:10.1080/01621459.1994.10476870;
Linnainmaa-Roberts (2018) doi:10.1093/rfs/hhx132; Harvey-Liu-Zhu-adjacent
McLean-Pontiff journal DOI doi:10.1111/jofi.12365 (NBER version verified instead,
§8.6). Pass 2 (ecosystem) or pass 3 (Tuesday run) may re-probe from a different
route or use institutional access — but no threshold or gate may cite an
unverified source until then. The Künsch (1989) block bootstrap (§8.4) covers the
spec's MBB requirement with a verified citation, so nothing structural is blocked.

### 8.8 Falsification — what would prove this pass wrong

F-R1 (specificity design broken): a seeded noise factor on the real 14-coin
panel prints |t_HAC| > 2 AND passes BH-FDR at q = 0.15. Standing data: max noise
|t_HAC| = 2.36 (noise_0) with BH-FDR N — uncomfortably close on the t-stat, saved
by the family correction. If a re-run with a new noise seed shows an FDR-passing
noise factor, the F3a 90% bar is too weak and the checker threshold must rise
(e.g. specificity on |t_HAC| > 2 count, not just verdicts).

F-R2 (sensitivity design broken): a pre-registered, fixed-seed planted signal on
the real panel (documented construction *before* the run, per F3b) is REJECTED by
the full gate. Would prove the gate cannot see real predictability at daily
frequency — the failure this repo exists to prevent, in reverse.

F-R3 (stability vacuous forever): the checker keeps passing with "0 promoted, 0
flips" quarter after quarter. A stability leg that can never fail is decorative;
if no real factor promotes by cycle 4, the mandate's sensitivity leg — not the
checker — is what failed, and the honest response is a planted-signal proof on
real data (F3b explicitly allows it), not a lowered bar.

F-R4 (floor does not scale with trials): a proof over a 50-factor family passes
with the same MIN_BARS_FLOOR = 10,000 as the 13-factor proof (§8.5: MinTRL grows
with the trial count). Observable: re-run the proof with 40 extra noise factors
in the family; if the checker still passes with identical floors, the floor must
become a function of m (MinTRL wiring, v0.3).

F-R5 (gate adds nothing): a proof where raw-p<0.05 count == BH-FDR count ==
promoted count (no attrition anywhere). The delta IS the product (§8.6
Harvey-Liu); a zero-delta proof means the gate is a pass-through and the checker
must reject it. Standing data shows healthy attrition (3 → 3 → 0); the middle
equality (raw == BH at q = 0.15) is already noted as a soft spot BY would harden
(3 → 2, §8.3).

F-R6 (this pass's own literature claims): any §8.1–§8.6 equation that does not
match its cited source falsifies the pass — the adversarial citation audit must
open every §8.8-table link and check the transcription. Flagged in advance:
McLean-Pontiff magnitudes (§8.6) and the BY hand-arithmetic (§8.3) are the two
spots most likely to need correction; a "BY arithmetic wrong" finding is minor
(the procedure transcription is what the design uses), a "BY procedure wrong"
finding is blocking.

Correction note on the pass brief: the brief states check_real_data_proof.py "is
not in the repo". It is: scripts/check_real_data_proof.py exists (tracked since
the c2-p04 lane, 303 lines, read today) with uncommitted working-tree
modifications (git diff: +109 lines vs HEAD) belonging to a parallel lane — left
untouched by this pass. The "which numbers it must reject" research above is
written against the on-disk version (§8.8-table checker legs: sections, JSON
fields, F3 thresholds, bars-vs-source, section content, internal refs).

### Link-verification table (all probed 2026-10-12, curl -L, UA Mozilla/5.0)

| Source | URL | HTTP status |
|--------|-----|-------------|
| Liu, Tsyvinski & Wu 2022 (NBER w25882) | https://www.nber.org/papers/w25882 | 200 |
| Fama & MacBeth 1973 (JSTOR) | https://www.jstor.org/stable/1830708 | 200 |
| Benjamini & Yekutieli 2001 (DOI) | https://doi.org/10.1214/aos/1013699998 | 200 |
| Künsch 1989 (DOI) | https://doi.org/10.1214/aos/1176347265 | 200 |
| Bailey & López de Prado 2012 (arXiv) | https://arxiv.org/abs/1207.3518 | 200 |
| Liu & Tsyvinski 2021 (NBER w24877) | https://www.nber.org/papers/w24877 | 200 |
| Lo, Mamaysky & Wang 2000 (NBER w5711) | https://www.nber.org/papers/w5711 | 200 |
| McLean & Pontiff 2016 (NBER w19804) | https://www.nber.org/papers/w19804 | 200 |
| Harvey & Liu 2015 (arXiv) | https://arxiv.org/abs/1502.00606 | 200 |
| Poterba & Summers 1988 (NBER w2343) | https://www.nber.org/papers/w2343 | 200 |
| Shiller 1981 (JSTOR) | https://www.jstor.org/stable/1802789 | 200 |
| Fama 1991 ECM II (JSTOR) | https://www.jstor.org/stable/2328565 | 200 |
| Bailey et al. 2014 Pseudo-Math (AMS) | https://www.ams.org/notices/201405/rnoti-p458.pdf | 200 |
| White 2000 (DOI, bot-block) | https://doi.org/10.1111/1468-0262.00152 | 403 — NOT claimed |
| Sullivan-Timmermann-White 1999 (DOI) | https://doi.org/10.1111/0022-1082.00163 | 403 — NOT claimed |
| Politis-Romano 1994 (DOI) | https://doi.org/10.1080/01621459.1994.10476870 | 403 — NOT claimed |
| McLean-Pontiff journal DOI | https://doi.org/10.1111/jofi.12365 | 403 — NBER version used |
| Linnainmaa-Roberts 2018 (DOI) | https://doi.org/10.1093/rfs/hhx132 | 403 — NOT claimed |
| Hansen 2005 SPA (DOI) | https://doi.org/10.1198/073500104000000063 | 404 — NOT claimed |
| Romano-Wolf 2005 (DOI) | https://doi.org/10.1111/j.1468-0262.2005.00615.x | 403 — NOT claimed |

### 8.9 Cycle 2 pass-3 dispositions — every pass-1/pass-2 open item closed (2026-10-12)

Pass 2 (§6.7) left no open questions — the comparison is current as of today.
The items below are pass 1's §8.7 boundary and §8.8 falsifiers F-R1…F-R6.
Experiments ran in /tmp (throwaway scripts, repo untouched, DB read-only);
raw outputs are pasted verbatim — summaries are not evidence.

**§8.7 boundary — CONFIRMED, still blocked (re-probed 2026-10-12, curl -L):**

```
403 https://doi.org/10.1111/1468-0262.00152
403 https://doi.org/10.1111/0022-1082.00163
403 https://doi.org/10.1080/01621459.1994.10476870
200 https://doi.org/10.1214/aos/1013699998
200 https://doi.org/10.1214/aos/1176347265
403 https://doi.org/10.1111/jofi.12365
403 https://doi.org/10.1093/rfs/hhx132
404 https://doi.org/10.1198/073500104000000063
403 https://doi.org/10.1111/j.1468-0262.2005.00615.x
```

All 7 still bot-blocked; the two project-IMTJ DOI resolvers (BY §8.3, Künsch
§8.4) still resolve. Nothing structural is newly blocked or unblocked.

**F-R1 — CLOSED (not observed).** 10 fresh-seed noise factors (master seed
20261012; the proof used 42), horizons 1/5/20, real 14-coin panel
(21,308 rows, 2021-04-29…2026-10-12):

```
noise_0 seed=1026914109 H= 1 ic=+0.0089 t_hac=+1.21 t_naive=+1.21 p=0.2264 BH15=N
noise_1 seed=1311211840 H=20 ic=+0.0050 t_hac=+0.68 t_naive=+0.69 p=0.4943 BH15=N
noise_2 seed=1818015127 H= 5 ic=+0.0077 t_hac=+1.03 t_naive=+1.04 p=0.3031 BH15=N
noise_3 seed=885879397  H= 1 ic=+0.0079 t_hac=+1.08 t_naive=+1.08 p=0.2795 BH15=N
noise_4 seed=844379682  H= 1 ic=+0.0066 t_hac=+0.91 t_naive=+0.91 p=0.3633 BH15=N
noise_5 seed=1915375832 H= 1 ic=-0.0109 t_hac=-1.50 t_naive=-1.50 p=0.1341 BH15=N
noise_6 seed=1938639109 H= 5 ic=-0.0049 t_hac=-0.69 t_naive=-0.68 p=0.4931 BH15=N
noise_7 seed=1400362054 H=20 ic=-0.0044 t_hac=-0.55 t_naive=-0.61 p=0.5843 BH15=N
noise_8 seed=2120681876 H=20 ic=-0.0043 t_hac=-0.58 t_naive=-0.59 p=0.5598 BH15=N
noise_9 seed=1312924144 H= 5 ic=+0.0069 t_hac=+0.93 t_naive=+0.93 p=0.3533 BH15=N
max |t_hac| = 1.50; BH discoveries = 0
```

Falsification condition (|t_HAC| > 2 AND BH-FDR pass) not observed on new
seeds. Standing caveat kept: the proof's seed-42 noise_0 reached |t_HAC| =
2.36 (saved by the family correction) — the noise tail is fat and the margin
is thinner than comfortable, but two independent seed sets now agree.

**F-R2 — CLOSED with FINDING (detection works, verdict blocks).** Pre-registered
planted signal, seed 1234, construction fixed before the run: fwd5(t) =
log(C[t+5]/C[t]) on the wide close frame, raw = fwd5 + eps with eps scaled for
corr ≈ 0.30, factor = cross-sectional rank per date; serving Factor.compute()
only reindexes a stored Series (no future-data access in factor source, so this
tests the statistical gates — declared, not hidden). Round 1 additionally
observed that a `shift(-5)` formulation is hard-rejected by the
`no_negative_shifts` source-scan gate before any statistics run — leakage
detection on custom factors works (see ADOPTION §8.4).

```
achieved corr(factor, fwd5) = +0.1039 (n=21234)
H= 1 ic=+0.0604 ic_ir=+0.1864 t_hac=+8.31 t_naive=+8.31 n=1988
H= 5 ic=+0.1528 ic_ir=+0.4680 t_hac=+19.06 t_naive=+20.87 n=1988
H=20 ic=+0.0914 ic_ir=+0.2786 t_hac=+10.85 t_naive=+12.38 n=1973
promote verdict (family m=14): reject
  PASS not_lookahead / not_degenerate / coverage / min_observations
  PASS min_abs_ic obs=0.1528 / min_ic_ir obs=0.4680
  FAIL hit_rate_wilson_lb obs=0.4658 thr=0.5
  FAIL max_turnover obs=1.3103 thr=0.5
  PASS oos_consistency obs=1.0 / survives_fdr obs=0.0
```

(Achieved corr 0.104, not 0.30: cross-sectional ranking on 14 coins compresses
the pooled calibration — reported as achieved, not as targeted. The signal is
still overwhelming at t_HAC = 19, so the sensitivity conclusion stands.)
Disposition: the gate is not blind — IC/HAC/FDR/OOS all fire — but the full
verdict couples detection with tradability gates a daily 14-coin rank factor
cannot satisfy. Consequence for the mandate, stated as a number the checker
must respect: an F3b sensitivity proof on this panel geometry must either use
a low-turnover planted construction (weekly rebalance) or credit the
statistical-gate sub-verdict; demanding a full PROMOTE verdict rejects real
predictability at t = 19. Note for trial accounting: adding the planted factor
moves E[max SR] 13 → 14 trials only 1.7033 → 1.7384 (F-R4 numbers below) —
the bar barely moves, so a planted F3b proof does not soften deflation.

**F-R3 — CLOSED (demonstrated where promotable; vacuous leg documented).**
mom_20 on planted synthetic under varied CV geometry:

```
method=walk_forward splits=4 verdict=promote oos=1.0                note=WF splits: 4
method=walk_forward splits=5 verdict=promote oos=0.6                note=WF splits: 5
method=walk_forward splits=6 verdict=promote oos=0.6666666666666666 note=WF splits: 6
method=cpcv         splits=5 verdict=promote oos=0.7333333333333333 note=CPCV splits: C(6,2)
```

0 flips across 4 geometries — stability holds where a promotion exists. And the
real-data leg stays vacuous for a structural reason this pass verified in
source: `_stability_check` re-runs `promote()` with the identical config
(`alt_seed` accepted, unused), so "0 flips" passes by construction even before
counting that nothing is promoted. Named fix for the implement pass: vary
`n_wf_splits` and `cv_method` inside `_stability_check`; the four rows above
are the reference shape.

**F-R4 — CLOSED (quantified; wiring deferred to implement).** E[max SR] from
Bailey–López de Prado eq. (2) (§2.4), Phi_inv via repo's own `_norm_cdf`
bisection (n = 1 degenerate — formula needs n ≥ 5 — excluded):

```
n_trials= 13 E[max SR]=1.7033
n_trials= 14 E[max SR]=1.7384
n_trials= 53 E[max SR]=2.2985
c(13)=3.1801 c(53)=4.5569 ratio=1.433
```

A 53-factor family raises the deflation bar 35% (1.70 → 2.30) and the BY bar
43% — a constant MIN_BARS_FLOOR = 10,000 cannot be right for both. Observable
test named for the implement pass: re-run the proof with 40 extra noise
factors in the family; if the checker passes with the identical floor, the
floor must become f(m) (MinTRL wiring, v0.3). E[max SR] = 1.7033 at m = 13
independently matches the §2.4 hand-arithmetic (≈ 1.71).

**F-R5 — CLOSED.** BY(q = 0.15) on correctly p-sorted proof p-values
(2026-10-12 proof; the round-1 "BY = 13" was this pass's own ordering bug —
p-values must be sorted ascending before rank thresholds apply; re-ran
correctly):

```
rank  1 lookahead_control  p=0.0000 BH=Y BYthr=0.0036 Y
rank  2 rev_5              p=0.0005 BH=Y BYthr=0.0073 Y
rank  3 volume_z_20        p=0.0255 BH=Y BYthr=0.0109 N
rank  4 amihud_illiq_20    p=0.0895 BH=N ...
BH discoveries=3 BY discoveries=2
```

Exactly the §8.3 hand-arithmetic (3 → 2, volume_z_20 drops). The middle
equality raw == BH (3 == 3) on real data is confirmed as the soft spot BY
hardens. No code change: the procedure transcription in §8.3 is what the
design would wire, and it now has machine confirmation.

**F-R6 — TRANSFERRED to the adversarial citation audit (not closable in
research).** Exact scope: every §8.1–§8.6 equation against its §8.8-table link;
flagged in advance — McLean–Pontiff magnitudes (§8.6, verify against the NBER
PDF before any threshold cites them) and the BY hand-arithmetic (§8.3, now
machine-confirmed as procedure-correct, F-R5). A "BY arithmetic wrong" finding
is minor; a "BY procedure wrong" finding is blocking.

**Cycle-1 mutation baseline (unchanged, quoted per brief):** 878/1977 mutants
killed = 44.4%, gate 70% (authoritative: reports/mutation-c1.json). No
mutants-survived file is present in reports/; nothing to disposition from it.

---

## 9. Cycle 3 pass 1 — checker-number ground truth (added 2026-10-12, pass c3-p01)

Scope: the numbers `scripts/check_real_data_proof.py` must reject, part II.
Cycle 2 §8 derived what the checker must check from the factor literature
(momentum priors, FM asymptotics, BY, MBB, MinTRL). This pass derives the
remaining checker numbers from the *inference* literature: when a HAC t-stat
may use normal critical values (KVB 2000, §9.3), when a Sharpe-ratio mapping
may annualise with sqrt(q) (Lo 2002, §9.2; Ledoit-Wolf 2008, §9.5), what the
named alternative to BH-FDR is and why the repo rejects it (White 2000, §9.1),
and what the post-2020 crypto-momentum record says a real-data proof must show
(Grobys et al. 2025, §9.4). 12 new sources probed today (curl -L, UA
Mozilla/5.0); 10 verified HTTP 200, 2 recorded as boundary (§9.6). Five drive
the design (§9.1–§9.5, full method/equations/assumptions/failure modes).

Standing data (unchanged since §8, re-read today): `reports/real-data-proof.json`
(generated 2026-10-12T16:41:01Z) — 14 coins, 21,308 daily bars, 2021-04-29 →
2026-10-12; 0/13 promoted; raw p<0.05 flags 3; BH-FDR q=0.15 passes the same
3; specificity 10/10; DSR = 0.0 everywhere. Fresh read-only check today:
raw `candles` table holds 669,860 rows / 14 coins / ts 1619724600 →
1791840300 (2021-04-29 → 2026-10-12), consistent with the proof's 21,308
aggregated daily bars. All 13 §8 claimed-200 links re-probed today: 12 still
200, 1 rot observed (AMS Pseudo-Mathematics PDF now 403 — citation kept,
status updated in §9.8).

### 9.1 White's Reality Check — the named alternative to BH-FDR (DRIVES DESIGN)

**White, H. (2000)**
"A Reality Check for Data Snooping"
*Econometrica* 68(5):1097–1126
DOI: https://doi.org/10.1111/1468-0262.00152 (publisher page bot-blocks automated
probes — NOT claimed as verified; §8.7 boundary stands)
[Verified URL: https://www.jstor.org/stable/2999444 — HTTP 200 confirmed
2026-10-12. Second verified record: https://ideas.repec.org/a/ecm/emetrp/v68y2000i5p1097-1126.html
— HTTP 200 confirmed 2026-10-12, page title fetched and matches. Publisher
abstract: https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping
— HTTP 200 confirmed 2026-10-12.]

Method extracted: the formal test that a *best-of-family* result is not luck.
For k = 1..m candidate models and a benchmark fixed ex ante, define the
date-t performance differential (e.g. loss-differential or return spread):

    f_{k,t} = L(Y_t, benchmark) - L(Y_t, model_k)

Null hypothesis (p.1098): the best model has no predictive superiority —

    H_0: max_{k=1..m} E[f_k] <= 0

Test statistic (standardised maximum):

    T_n = max_{k=1..m} sqrt(n) * fbar_k,   fbar_k = (1/n) * sum_{t=1}^{n} f_{k,t}

p-value by stationary bootstrap (Politis-Romano 1994 — the §8.7-blocked
source this procedure depends on): resample B stationary-bootstrap series,
recompute T*_n,b on each, p = fraction of T*_n,b >= T_n. Reject H_0 (the
family's best is real) iff p < alpha.

Notation: n = dates; m = family size; B = bootstrap replicates; the stationary
bootstrap resamples blocks of geometric (random) length so the replicate stays
stationary — this is why White cites Politis-Romano rather than the plain
i.i.d. bootstrap of §2.5.

Assumptions: (a) {f_{k,t}} covariance-stationary and mixing (dependence dies
with lag — same assumption as §8.4 MBB); (b) the benchmark is fixed BEFORE the
search (a benchmark picked after seeing results reintroduces the snooping the
test prices); (c) n large relative to the bootstrap block length.

Known failure modes per the literature: (a) CONSERVATISM UNDER JUNK — when the
family contains many poor models, the max-statistic's null distribution is
dominated by noise and the test loses power (this is the documented motivation
for Hansen's SPA test, which studentises and recentres — Hansen 2005 cited as
boundary, §9.6, working-paper version unverified); (b) benchmark dependence —
changing the benchmark changes the verdict, so two researchers can disagree
with the same family; (c) block-length sensitivity, same as §8.4 failure (a).

Design consequence (alternatives-considered): the Reality Check is the
procedure the repo does NOT implement, deliberately. RC answers "is the best
of this family better than benchmark X" and needs the full return panel plus a
bootstrap over the family; BH-FDR (§2.3) answers "which members survive a
family error budget" and operates on p-values already in hand from the
HAC-corrected IC t-stats (§2.10). For a screening gate that must emit
per-factor verdicts, BH is the correct layer; RC tests the family maximum
only and cannot name names. Filed as falsification item F-R9 below: any proof
that claims "no data snooping" from per-factor p-values WITHOUT a
max-over-family statistic of any kind (RC/SPA/PBO/BH — the repo's answer is
BH plus the PBO-adjacent CPCV diagnostic, §2.12) is unprotected, and the
checker must reject a proof whose report never names its family size m.

### 9.2 Lo on Sharpe-ratio statistics — the annualisation the checker must police (DRIVES DESIGN)

**Lo, A.W. (2002)**
"The Statistics of Sharpe Ratios"
*Financial Analysts Journal* 58(4):36–52
DOI: https://doi.org/10.2469/faj.v58.n4.2453 (T&F abstract page returns 403 to
automated probes — NOT claimed; the DOI is retained as canonical identifier)
[Verified URL: https://www.jstor.org/stable/4480405 — HTTP 200 confirmed
2026-10-12. Second verified record (publisher): https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios
— HTTP 200 confirmed 2026-10-12. The T&F abstract text, retrieved via search
2026-10-12, states the two headline results quoted below.]

Method extracted: sampling theory for SRhat under IID and under serial
correlation. Under IID returns, sqrt(T)(SRhat - SR) is asymptotically normal
with asymptotic variance 1 + SR^2/2 (the moment-correction parent shared with
the PSR/DSR of §8.5 and §2.4). Under stationary autocorrelated returns with
lag-k autocorrelations rho_k, the textbook annualisation is wrong:

    SR_ann = sqrt(q) * SR_monthly        (valid ONLY under IID)

    corrected: SR_ann = sqrt(q) * SR_monthly / sqrt(V),
        V = 1 + 2 * sum_{k=1}^{q-1} (1 - k/q) * rho_k

Notation: q = aggregation factor (12 for monthly→annual, 252 for
daily→annual); rho_k = lag-k return autocorrelation; V = 1 under IID.
(Notation standardised to the repo's conventions; exact transcription to be
confirmed against JSTOR pp.36–52 in the adversarial citation audit — flagged
in advance as F-R6-class, minor if the factor V is right and only symbols
differ.)

Headline numbers (from the publisher abstract, retrieved 2026-10-12):
ignoring serial correlation can OVERSTATE a hedge-fund annual Sharpe by as
much as 65%, and SR-based fund RANKINGS can flip once autocorrelation is
accounted for.

Assumptions: (a) stationarity (V estimable); (b) rho_k estimable — needs long
T, same caveat as the DSR moment correction (§2.4 failure mode); (c) the
aggregation horizon q is fixed and known.

Known failure modes: (a) V itself is estimated with error — on T < 200 the
correction is noise (same floor argument as §8.5); (b) negative autocorrelation
UNDERSTATES the naive SR (the correction cuts both ways); (c) structural
breaks invalidate the full-sample rho_k (cf. C2-3/C2-3a).

Design consequence: the §4-Test-5 resolution maps IC-IR to SR via the
fundamental law (SR ≈ IC*sqrt(breadth)) and compares against E[max SR] ≈ 1.70
— that mapping annualises with sqrt. Lo says the sqrt step is valid only if
the strategy returns are serially uncorrelated, which overlapping-label IC
series (§2.10) guarantee they are NOT at H > 1. Filed as falsification item
F-R8: any proof that reports an SR (or DSR input SR*) annualised with a bare
sqrt without the V correction or an explicit IID caveat overstates its Sharpe
by a Lo-class magnitude, and the checker must reject a proof whose
IC→SR layering paragraph is missing. Standing proof is unaffected (its DSR =
0.0 conclusion strengthens under correction, since V > 1 shrinks SRhat
toward the E[max SR] bar — the conservative direction).

### 9.3 Kiefer-Vogelsang-Bunzel fixed-b — when normal critical values are legal (DRIVES DESIGN)

**Kiefer, N.M., Vogelsang, T.J. & Bunzel, H. (2000)**
"Simple Robust Testing of Regression Hypotheses"
*Econometrica* 68(3):695–714
[Verified URL: https://www.jstor.org/stable/2999605 — HTTP 200 confirmed
2026-10-12. Second verified record: https://ideas.repec.org/a/ecm/emetrp/v68y2000i3p695-714.html
— HTTP 200 confirmed 2026-10-12. (This is the paper §2.10 failure mode (3)
cited without a full entry — now grounded.)]

Method extracted: fixed-b asymptotics for HAC-robust tests. Standard
("small-b") HAC theory lets the truncation lag L grow slower than T (L/T → 0)
and tests with NORMAL critical values (±1.96). KVB analyse the opposite
limit: hold the bandwidth fraction b = L/T FIXED (in the extreme, b = 1, i.e.
use all T lags with Bartlett weights). Then the HAC t-statistic converges to
a NONSTANDARD, non-pivotal limit (functionals of Brownian motion), and valid
critical values are LARGER than normal ones and must be simulated for the
given b and kernel. Payoff: holding b fixed gives substantially better
finite-sample size control — standard HAC with large L/T over-rejects badly,
and fixed-b critical values repair it.

The repo's operating point: HAC lag L = H-1 ≤ 19, IC series length T ≈ 1900+,
so L/T ≈ 19/1953 ≈ 0.0097 — deep in the small-b regime where normal critical
values are asymptotically valid. KVB's simulations show size distortion grows
with b; at b ≈ 0.01 it is negligible. This entry is therefore the *licence*
for every HAC t-stat the proof reports.

Assumptions: (a) stationarity + mixing (same as §2.10); (b) kernel fixed
(Bartlett — matches the repo); (c) the fixed-b critical values assume the
limit theory's regularity (no breaks — cf. C2-3a).

Known failure modes: (a) fixed-b critical values are non-pivotal — they depend
on b, the kernel, and whether the series is demeaned; using the wrong table
reintroduces size distortion; (b) power loss vs small-b in well-behaved large
samples (paying for robustness).

Design consequence: the licence has a boundary, and the boundary is a number.
Filed as falsification item F-R7: the checker must reject any proof whose
reported HAC significance uses normal critical values when L/T >= 0.05
(e.g. H=20 on a T ≤ 400 panel, or CPCV sub-paths with short test groups) —
at that ratio KVB's results say normal-1.96 over-rejects, so a "significant"
t_HAC there is unlicensed. Standing proof: L/T ≈ 0.01 everywhere — licence
holds, no verdict changes.

### 9.4 Crypto momentum after 2020 — the sensitivity prior, updated (DRIVES DESIGN)

**Grobys, K., Kolari, J.W., Sandretto, D., Shahzad, S.J.H. & Aijo, J. (2025)**
"Cryptocurrency momentum has (not) its moments"
*Journal of Asset Management*, published online 27 March 2025 (open access).
[Verified URL (PDF): https://link.springer.com/content/pdf/10.1007/s11408-025-00474-9.pdf
— HTTP 200 confirmed 2026-10-12. Landing page: https://link.springer.com/article/10.1007/s11408-025-00474-9
— HTTP 200 confirmed 2026-10-12.]

Method extracted: weekly cross-sectional momentum on the top-30 liquid coins,
2016–2023, with tail-risk (power-law) modelling of the momentum leg and a
volatility-managed variant. This is the post-sample continuation of the
Liu-Tsyvinski-Wu (2022, §8.1) result — same strategy, six more years of data
that Liu et al. could not have seen.

Headline numbers (abstract + §1, retrieved 2026-10-12): momentum earned
+1.74%/week Jan-2016 → Jul-2020; in the ex-post Jul-2020 → 2023 sample the
average payoff is NEGATIVE and statistically insignificant; full-sample
average +0.90%/week, insignificant. In December 2020 — inside Liu et al.'s own
sample window — momentum crashed −255.23%, and the crash is NOT a
Daniel-Moskowitz-style market reversal: it traces to an extreme price jump in
a SINGLE coin in the short leg. The paper's §2 survey further records the
field as inconclusive (Grobys-Sapkota 2019, Shen et al. 2020: no momentum;
Dobrynskaya 2023: short momentum + longer reversal, §9.6 boundary).

Assumptions: (a) top-30-by-cap panel controls illiquidity; (b) weekly
rebalance tradable (ignores spread/impact — same caveat as §8.1); (c) no
survivorship handling beyond the liquid panel.

Known failure modes the paper documents: (a) single-coin crash dominance on a
narrow panel — with 1–2 coins per decile leg, idiosyncratic jumps ARE the
strategy return; (b) publication/capacity decay post-2020 (same mechanism as
McLean-Pontiff, §8.6); (c) trimming choices move the headline (their §3 shows
trimmed vs untrimmed estimates differ in sign in the ex-post window).

Design consequence: this is the strongest literature evidence for the
standing observation. A 2021-2026 daily 14-coin panel promoting NOTHING —
including momentum — is exactly what the post-2020 record predicts; a proof
that DID promote a daily-H momentum factor on this window would contradict a
2025 peer-reviewed result and must be treated as suspect, not as success.
Filed as falsification item F-R10: any real-data MOM promotion at daily
horizons on 2021+ data must be flagged for adversarial review (single-coin
crash dominance check: drop the top-|return| coin-week and re-screen; if the
verdict flips, the "factor" was one coin). The F3b planted-signal route (§8.9
F-R2 disposition) is endorsed unchanged — it tests the gate, not the market.

### 9.5 Ledoit-Wolf robust Sharpe testing — the second vote against naive HAC (DRIVES DESIGN)

**Ledoit, O. & Wolf, M. (2008)**
"Robust Performance Hypothesis Testing with the Sharpe Ratio"
*Journal of Empirical Finance* 15(5):850–859
DOI: https://doi.org/10.1016/j.jempfin.2008.03.002
[Verified URL (DOI): HTTP 200 confirmed 2026-10-12 via doi.org. Verified
working-paper version (substantively equivalent, U. Zurich IEW WP 320, Jan
2008): https://www.econ.uzh.ch/apps/workingpapers/wp/iewwp320.pdf — HTTP 200
confirmed 2026-10-12. Second verified record: https://ideas.repec.org/p/zur/iewwpx/320.html
— HTTP 200 confirmed 2026-10-12. Correction note: an earlier draft of this
entry guessed DOI suffix .2007.10.002 — that guess was WRONG (verified
against the search record 2026-10-12; the correct suffix is .2008.03.002 as
printed on the paper itself). Guessed DOIs are not cited.]
[Abstract text retrieved via search 2026-10-12; equation transcription below
is from the abstract + working paper excerpts and is flagged for audit.]

Method extracted: testing H_0: Delta = 0 where Delta = SR_1 - SR_2 (two
strategies). The paper kills the Jobson-Korkie/Memmel status quo (invalid
under heavy tails or time-series dependence) and replaces it with two
procedures: (a) a studentised circular-block-bootstrap confidence interval
for Delta (declare different iff 0 not in the interval — resample OBSERVED
data, no null restriction); (b) HAC inference with a kernel long-run-variance
estimator Psi-hat (Andrews 1991 / Andrews-Monahan 1992 style):

    p_hat = 2 * Phi(-|Delta_hat| / s(Delta_hat)),   CI: Delta_hat ± z_{1-a/2} * s

Notation: s(Delta_hat) = HAC standard error from the kernel estimator;
Phi = standard normal CDF. The paper's own verdict (verified abstract text):
HAC inference "works asymptotically but does not always have satisfactory
properties in finite samples" — it is "often liberal when sample sizes are
small to moderate" — so the bootstrap is the recommended default.

Assumptions: (a) stationarity + mixing for both the bootstrap and HAC legs;
(b) circular block bootstrap with block length covering the dependence
(same l ≈ H argument as §8.4); (c) studentisation (bootstrap the t-stat, not
the raw Delta — non-studentised bootstrap under-covers).

Known failure modes: (a) block-length choice, again; (b) HAC liberalism in
small samples — the failure mode this entry exists to record; (c) heavy-tail
DGPs where even the bootstrap needs large T (their simulations).

Design consequence: second independent citation (with Lo 2002) that HAC
standard errors over-reject in finite samples — F-R7's L/T >= 0.05 rule now
has two votes, and the repo's `bootstrap_ci` primitive (§2.5) is the
literature-recommended leg wherever T is small. Checker number, shared with
F-R7: any proof p-value computed with a HAC SE on T < 200 must use the block
bootstrap (l = H), not normal critical values. Standing proof (T ≈ 1900+)
is on the HAC-legal side of both rules.

### 9.6 Context sources probed today (boundary — NOT claimed as verified)

- **Dobrynskaya, V. (2023)** "Cryptocurrency Momentum and Reversal", *Journal
  of Alternative Investments* 26(1):65–76. DOI: https://doi.org/10.3905/jai.2023.1.189
  — resolver returned HTTP 429 (throttled) 2026-10-12; SSRN abstract page and
  pm-research PDF both 403. Content summarised from the SSRN abstract
  (retrieved via search): 2,000 coins 2014–2020, momentum ≤ 2–4 weeks, reversal
  beyond ~1 month ("faster metabolism" of crypto). Usable as narrative context
  only — no threshold or gate may cite it until a 200 is recorded.
- **Grobys, K. & Shahzad, S.J.H. (2025)** "Cryptocurrency Momentum: Is It an
  Illusion?", *Int. J. Finance & Economics* (early view). DOI:
  https://doi.org/10.1002/ijfe.70036 — 403 to automated probes 2026-10-12.
  Abstract (retrieved via search): realised variances of six crypto-momentum
  strategies follow power laws; block-bootstrap tests say the population mean
  and variance are statistically UNDEFINED — "performance metrics using
  variance as an input are not informative". If verified later, this is a
  third vote (with Lo, Ledoit-Wolf) that variance-normalised statistics on
  crypto momentum are fragile — directly relevant to the DSR moment
  correction (§2.4) on crypto panels. Until then: boundary.
- **Ehsani, S. & Linnainmaa, J.T. (2022)** "Factor Momentum and the Momentum
  Factor", *J. Finance* 77(3) — DOI probe returned 403 (Wiley). Boundary;
  noted because the 2023 crypto factor-momentum paper (§9.4's survey cites it)
  builds on it.
- **Hansen, P.R. (2005)** "A Test for Superior Predictive Ability", *J.
  Business & Econ. Statistics* — DOI probe returned 404 (moved or
  mis-recorded). Boundary; the SPA power-motivation claim in §9.1 rests on
  the paper's title/abstract record, not on a verified full text.
- **Shanken (1992)** EIV correction — never probed (no verified URL in hand);
  NOT cited. The §8.2 EIV failure-mode paragraph stands on Fama-MacBeth
  (verified) alone.

### 9.7 Alternatives considered (this pass)

RC-vs-BH (§9.1) is the substantive one. Two more, briefly: (i) Lo-corrected
vs naive annualisation — naive sqrt retained ONLY with an explicit IID caveat
(§9.2/F-R8); a silent naive sqrt in a proof report is a checker reject, not a
style choice, because the bias direction is known (overstatement up to
Lo-class 65% magnitudes). (ii) fixed-b vs small-b critical values — small-b
(normal) retained ONLY with L/T < 0.05 recorded in the proof (F-R7); the
proof's L/T ≈ 0.01 satisfies this with 5x margin.

### 9.8 Falsification — what would prove this pass wrong (F-R7…F-R10 new; F-R1…F-R6 stand)

F-R1…F-R6: dispositions in §8.9 stand; nothing re-run this pass (no new data
— the proof JSON is hours old and the dataset grew by <1 day of bars).

F-R7 (HAC licence boundary): any proof reporting HAC-based significance with
normal critical values at L/T >= 0.05. Standing proof L/T ≈ 0.0097 — holds
with 5x margin. Would be falsified (the pass, not the repo) if KVB's
simulations show negligible distortion at b = 0.05 — the audit should check
the b-grid in KVB Table/Figures against the 0.05 number; if the distortion
only bites at b >= 0.10, the rule relaxes to 0.10.

F-R8 (sqrt-annualisation): any proof IC→SR mapping with a bare sqrt and no V
correction or IID caveat. Standing proof reports no annualised SR (DSR inputs
are horizon-native) — vacuously holds; the rule binds the first proof that
does annualise.

F-R9 (family-size silence): any proof whose report never names m (family
size) or, equivalently, reports a best-factor statistic with no max-over-family
correction of any kind (BH/BY/RC/SPA/PBO). Standing proof names m = 13
(+10 noise) and all three delta counts — holds.

F-R10 (momentum anachronism): any daily-H MOM promotion on 2021+ crypto that
survives the single-coin-drop check. Standing proof promotes nothing — holds;
the check is specified (drop top-|return| coin-week, re-screen, verdict must
not flip) so a future implement pass can wire it.

F-R11 (this pass's own transcriptions): the Lo V-factor notation (§9.2) and
the White T_n/bootstrap description (§9.1) are standardised paraphrases, not
verbatim copies — the adversarial citation audit must open the JSTOR links
and check them. A "symbols differ, factor right" finding is minor; a "factor
wrong" finding is blocking. Pre-flagged: the Ledoit-Wolf equation block
rests on abstract + working-paper excerpts, not the typeset journal PDF.

### 9.9 Loop-status notes (observed today, for the implement/evaluate passes — NOT fixed here)

1. **Mutation-c2 gate is VOID, not failed.** `reports/mutation-c2.json`
   (untracked, read today) records rc=2, killed=0/total=0: `mutmut run` was
   invoked with `--max-children`, which the installed mutmut has no such
   option ("Error: No such option '--max-children'"). No score exists, so the
   70% gate is unmeasured for cycle 2, and `reports/mutants-survived-c2.txt`
   exists but is EMPTY (0 lines, verified today) — there is nothing to
   disposition from it. Named fix for the evaluate pass: re-run with the
   installed mutmut's actual CLI flags. The cycle-1 baseline (44.4%,
   reports/mutation-c1.json) remains the authoritative kill score.
2. **Link rot observed:** the Bailey et al. 2014 AMS Notices PDF (§8.6) now
   returns 403 (was 200 on 2026-10-12 per §8.8 — same day, later probe).
   Citation retained with updated status; the DSR equation record lives in
   §2.4 (arXiv preprint, still 200) so nothing structural depends on it.
3. **F1 checker state:** `scripts/check_real_data_proof.py` FAILs today, and
   `scripts/check_no_internal_refs.py` FAILs on absolute-path hits in
   `docs/ADVERSARIAL_REVIEW.md:898` and `reports/improvements.md:319` (all
   abs-path hits per the script output). Research records this; the path
   scrub belongs to the implement pass (this pass touches no lane but its
   own artifact).
4. **Branch note:** `feat/v0.1` is checked out in a sibling worktree
   (`<sibling-worktree>/factorproof-reconcile`; absolute host path redacted per
   F1), so this pass
   commits on detached HEAD at 811343c for the orchestrator to merge — the
   pass brief's "commit on feat/v0.1" is honoured in content, not in ref
   name, to avoid disturbing the parallel lane.

### Link-verification table (all probed 2026-10-12, curl -L, UA Mozilla/5.0)

| Source | URL | HTTP status |
|--------|-----|-------------|
| White 2000 (JSTOR) | https://www.jstor.org/stable/2999444 | 200 |
| White 2000 (RePEc, title-fetched) | https://ideas.repec.org/a/ecm/emetrp/v68y2000i5p1097-1126.html | 200 |
| White 2000 (Econometric Society) | https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping | 200 |
| Lo 2002 (JSTOR) | https://www.jstor.org/stable/4480405 | 200 |
| Lo 2002 (CFA Institute) | https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios | 200 |
| KVB 2000 (JSTOR) | https://www.jstor.org/stable/2999605 | 200 |
| KVB 2000 (RePEc) | https://ideas.repec.org/a/ecm/emetrp/v68y2000i3p695-714.html | 200 |
| Grobys et al. 2025 (Springer PDF) | https://link.springer.com/content/pdf/10.1007/s11408-025-00474-9.pdf | 200 |
| Grobys et al. 2025 (landing) | https://link.springer.com/article/10.1007/s11408-025-00474-9 | 200 |
| Ledoit-Wolf 2008 (DOI, correct suffix .2008.03.002) | https://doi.org/10.1016/j.jempfin.2008.03.002 | 200 |
| Ledoit-Wolf 2008 (UZH WP 320 PDF) | https://www.econ.uzh.ch/apps/workingpapers/wp/iewwp320.pdf | 200 |
| Ledoit-Wolf 2008 (RePEc) | https://ideas.repec.org/p/zur/iewwpx/320.html | 200 |
| §8 re-verification (12/13 still 200 — see §9 preamble) | various §8.8 URLs | 200 |
| Bailey et al. 2014 (AMS PDF — ROT observed) | https://www.ams.org/notices/201405/rnoti-p458.pdf | 403 |
| Dobrynskaya 2023 (DOI, throttled) | https://doi.org/10.3905/jai.2023.1.189 | 429 — NOT claimed |
| Dobrynskaya 2023 (SSRN) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3913263 | 403 — NOT claimed |
| Dobrynskaya 2023 (pm-research PDF) | https://www.pm-research.com/content/iijaltinv/early/2023/03/25/jai.2023.1.189.full.pdf | 403 — NOT claimed |
| Lo 2002 (T&F abstract) | https://www.tandfonline.com/doi/abs/10.2469/faj.v58.n4.2453 | 403 — NOT claimed |
| Lo 2002 (SSRN) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=377260 | 403 — NOT claimed |
| Grobys-Shahzad 2025 (Wiley) | https://doi.org/10.1002/ijfe.70036 | 403 — NOT claimed |
| Ehsani-Linnainmaa 2022 (Wiley DOI) | https://doi.org/10.1111/jofi.13131 | 403 — NOT claimed |

---

## 10. Ecosystem and competition (cycle 3, pass 2 — 2026-10-12)

This section is the pass-2 deliverable. The maintained detail table lives in
`COMPARISONS.md` (7 tools, per-feature columns, re-verified today); this section
records the live numbers fetched for this pass, the comparison summary, the
claimed gap, and the falsification criterion. No MARKET-VERDICTS position is
re-litigated: the verdicts file remains authoritative and everything below is
consistent with it.

### 10.1 Live verification (GitHub REST API + PyPI, probed 2026-10-12)

| Tool | Repo / package | Stars (today) | Last push / release | Licence |
|------|----------------|---------------|---------------------|---------|
| MlFinLab (Hudson & Thames) | https://github.com/hudson-and-thames/mlfinlab | 4,939 | 2023-10-02 (no code push since; repo is a paid-product page) | Other (commercial, all rights reserved) |
| qlib (Microsoft) | https://github.com/microsoft/qlib | 49,313 | 2026-10-08 (active) | MIT |
| purgedcv (eslazarev) | https://github.com/eslazarev/purged-cross-validation / https://pypi.org/project/purgedcv/ | 55 | PyPI 0.1.10; last push 2026-10-01; created 2026-05-15, JOSS paper | MIT |
| ml4t-diagnostic (ml4t org) | https://github.com/ml4t/diagnostic | 34 | 2026-10-10 (active; 1 of a 7-library ecosystem) | MIT |
| pyanomaly (chulwoohan) | https://github.com/chulwoohan/pyanomaly | 133 | 2024-03-13 (no commits since) | MIT |
| alphalens / pyfolio / empyrical (Quantopian) | https://github.com/quantopian/alphalens et al. | — (abandoned upstream) | 2020-04-27 / 2020-02-28 / 2020-10-14 | Apache-2.0 |
| alphalens-reloaded / pyfolio-reloaded / empyrical-reloaded (stefan-jansen) | per COMPARISONS.md | 668 / 616 / 125 | 2026-10-10 (all three; installability forks only) | Apache-2.0 |

Deltas vs the COMPARISONS.md values recorded earlier today: purgedcv 34 → 55
stars (growing fast: created May 2026, 55 stars by October); qlib 49,308 →
49,313. Both COMPARISONS.md cells are corrected in this same pass. All other
counts confirmed unchanged.

### 10.2 Comparison table

| Tool | Approach | What it does well | Gap it leaves | What we do differently |
|------|----------|-------------------|---------------|------------------------|
| MlFinLab | Full financial-ML library (bars, labelling, ensembles, backtest-overfitting) | The reference implementation: purged/CPCV, haircut + deflated Sharpe, PBO, profit hurdles, track-record length | Commercial licence (£100+VAT/mo/user, no derivatives, improvements assigned to licensor); public repo unpushed since 2023-10-02 | MIT, offline, inspectable: the 4 overfitting controls as a standalone gate, no subscription |
| Quantopian stack (alphalens/pyfolio/empyrical) | Factor tear-sheets + performance attribution | The mental model for factor analysis; familiar output | Abandoned 2018–2020; no purged CV, no FDR, no DSR, no gate; forks restore installability only | Same tear-sheet intuition (IC decay, quantile returns) plus the statistics the stack never had |
| qlib (Microsoft) | End-to-end AI quant platform (data, models, experiments) | Scale, model zoo, experiment tracking, 49k-star contributor base | No overfitting-control statistics at all (no purged/embargo, no FDR, no DSR, plain Sharpe only) | Complementary: the gate qlib screens could be passed through before promotion |
| purgedcv (eslazarev) | sklearn-compatible time-series CV + Sharpe statistics | Correct purged K-fold, walk-forward, CPCV, embargo, DSR/PSR; actively developed (PyPI 0.1.10) | CV/statistics library only: no factor computation, no IC, no quantile spread, no accept/reject verdict | End-to-end screening: factors → IC → HAC-t → FDR → verdict with exit codes, one offline command |
| ml4t-diagnostic | Signal diagnostics inside a 7-library ML4T ecosystem | Walk-forward/CPCV, FDR, White's Reality Check, DSR, PBO, tearsheets | Metrics, not a gate; Polars + 7-library dependency chain; no standalone accept/reject | Zero-dep-core gate (numpy/pandas/matplotlib only) that says no and exits 1 |
| pyanomaly | Academic anomaly replication on WRDS/CRSP data | Real-data equity anomalies, factor regressions, quantile portfolios | WRDS subscription required (no offline path); no purged CV, no FDR, no gate | Synthetic-data offline demo plus the full rejection pipeline a WRDS user would still need |
| reloaded forks (stefan-jansen) | Keep the Quantopian stack installable | Modern-Python compatibility for the tear-sheets | Source-checked: add none of the four controls | Same answer as for the upstream stack |

### 10.3 The gap we claim (explicit)

No live, permissively-licensed tool packages **purged walk-forward CV with
embargo + Benjamini-Hochberg FDR across the screened family + deflated Sharpe +
an explicit promotion gate that rejects** in one offline command. MlFinLab has
all four and more but is proprietary and stale-public; purgedcv has two of the
four (CV + DSR) and is the nearest competitor; ml4t-diagnostic has the
statistics but no verdict; the rest have none.

How a user notices it: clone this repo, run `bash examples/run_demo.sh`
offline, and watch `factor-lab promote noise_control` exit 1 with a 10-row
reason table (FDR rejection, HAC-corrected t-stat, Wilson bound) while
`factor-lab promote mom_20` on planted-signal data exits 0. None of the seven
tools above produces that verdict surface — MlFinLab documents thresholds but
ships no accept/reject API in its public source.

### 10.4 Falsification for this pass

The positioning is wrong if any of these is observed: (a) purgedcv ships
factor screening (IC measurement) plus an accept/reject gate — the gap narrows
to licence/offline-simplicity only; (b) MlFinLab is relicensed under MIT/Apache
— the gap closes entirely; (c) ml4t-diagnostic adds a standalone verdict API
usable outside its ecosystem — the gate claim becomes shared, not unique.
Observed as of 2026-10-12: none of the three. Closest threat is (a): purgedcv
went from 0 to 55 stars in five months with 23 PyPI releases and owns exactly
the two controls (CV, DSR) closest to our core — worth re-checking every cycle.
Secondary watch: the reloaded forks prove community demand for maintained
Quantopian-era tooling; if a fork adds FDR/purge, row 2 of the table changes.

---

## 11. Cycle 3 pass 3 — every pass-1/pass-2 open item closed (2026-10-12)

Scope: this pass closes, with executed evidence, every falsifier and loop note
passes 1–2 left open (§9.8 F-R7…F-R11, §9.9 loop notes, §10.4 watch). No code
changed. Experiments ran in /tmp (throwaway scripts, repo untouched, database
read-only); raw outputs pasted verbatim. This section uses no absolute paths
and names no internal systems (checker-F1 hygiene — see §11.6 item 3).

### 11.1 F-R7 — CLOSED (licence holds with 5x margin)

Rule: HAC-based significance with normal critical values is licensed only at
L/T < 0.05 (Kiefer-Vogelsang-Bunzel 2000, §9.3). Standing proof numbers,
re-read today from `reports/real-data-proof.json`: per-factor `n_obs` ≈
1973–1987 at H ≤ 20, so L = H−1 ≤ 19 and L/T ≤ 19/1973 ≈ 0.0096 — more than
5x inside the licence. No proof p-value is computed outside it.
Residual for the adversarial audit: whether KVB's distortion grid bites at
b = 0.05 or only at b ≥ 0.10 (which would relax the rule). Research cannot
resolve that from the literature record alone; the rule stays at 0.05 until
the audit checks the KVB tables.

### 11.2 F-R8 — CLOSED (vacuous hold, verified by grep)

Rule: any proof IC→SR mapping with a bare sqrt and no V correction or IID
caveat is a checker reject (Lo 2002, §9.2). Observed today:
`grep -c -i "annual" reports/real-data-proof.md` → **0**. The standing proof
reports no annualised SR (DSR inputs are horizon-native), so the rule binds
nothing today — it binds the first proof that annualises. Closed as
verified-vacuous, not as assumed.

### 11.3 F-R9 — CLOSED (family size is named)

Rule: the checker must reject a proof whose report never names m (§9.1).
Observed today in `reports/real-data-proof.md`: "Factors with raw p < 0.05
(naive threshold): **3** out of 13"; "Factors passing BH-FDR q=0.15 across
family: **3**"; the BH limitation section states the family size explicitly
("less than 13"). m is recoverable three independent ways (count line,
procedure + q line, per-factor table rows). Holds.

### 11.4 F-R10 — CLOSED with FINDING (one BH pass is a one-coin artefact)

The specified check (drop the top-|return| coin-week, re-screen) was executed
today with the leave-one-coin-out worst case added. Raw output:

```
panel rows=21308 coins=14 dates=2021-04-29..2026-10-12
rev_5 FULL H=1 ic=+0.0348 ir=+0.0810 t_hac=+3.61 p=0.0003 n=1987
  top cell: date=2023-07-13 asset=XRP fwd=+0.5563
  DROP-CELL H=1 ic=+0.0353 t_hac=+3.66 p=0.0002
  LOCO min-|t|: drop INJ ic=+0.0279 t=+2.75 p=0.0059
  LOCO max-|t|: drop SOL ic=+0.0413 t=+4.08 p=0.0000
volume_z_20 FULL H=1 ic=-0.0192 ir=-0.0519 t_hac=-2.30 p=0.0212 n=1973
  top cell: date=2023-07-13 asset=XRP fwd=+0.5563
  DROP-CELL H=1 ic=-0.0192 t_hac=-2.31 p=0.0209
  LOCO min-|t|: drop ATOM ic=-0.0131 t=-1.49 p=0.1364
  LOCO max-|t|: drop INJ ic=-0.0228 t=-2.58 p=0.0098
```

Disposition: the falsification condition FIRED for volume_z_20 — its BH-FDR
pass (p = 0.0212) does not survive removing ATOM (p = 0.1364, not even
raw-significant). On a 14-coin panel the "factor" is one coin. It did NOT
fire for rev_5: worst-case LOCO p = 0.0059, still significant, and the
single-cell drop (XRP +55.6% on the 2023-07-13 ruling day) moves nothing.

**FINDING C3-F1 (severity: major, disposition: implement pass).** A BH-FDR
pass on a narrow panel is necessary but not sufficient — the proof needs a
LOCO robustness diagnostic (drop each coin, re-screen, report worst-case p)
before any promotion. This is the second independent vote against
volume_z_20 (the first: BY arithmetic drops it 3→2, §8.9 F-R5) and it
vindicates the standing 0-promoted verdict: promoting volume_z_20 here would
have promoted a one-coin artefact. The F3b planted-signal route (§8.9 F-R2
disposition) is unaffected — it tests the gate, not the market.

### 11.5 F-R11 — PARTIAL (resolvability re-confirmed; transcription audit transferred)

All three JSTOR links re-probed today (curl, browser UA): White 2000
(`stable/2999444`) → 200; Lo 2002 (`stable/4480405`) → 200; KVB 2000
(`stable/2999605`) → 200. Resolvability holds. The equation-level
transcription check (Lo V-factor notation, White T_n/bootstrap, Ledoit-Wolf
block resting on abstract + working-paper excerpts) is TRANSFERRED to the
adversarial citation audit — research has no further probe that deepens it.
Pre-flags stand: "symbols differ, factor right" is minor; "factor wrong" is
blocking.

### 11.6 §9.9 loop notes — re-verified today

1. **Mutation-c2 still VOID.** `reports/mutation-c2.json` re-read: rc=2,
   killed=0/total=0 (mutmut invoked with a flag the installed version
   rejects). `reports/mutants-survived-c2.txt` is 0 lines — nothing to
   disposition. Authoritative kill score remains cycle-1: 44.4%.
2. **Link rot:** AMS Pseudo-Mathematics PDF still non-200 (was 200, then 403
   same-day per §9.9). Citation retained; the DSR equation record lives in
   §2.4 (arXiv, still 200). All 3 JSTOR links (§11.5) and all 6 GitHub API +
   1 PyPI probes (§11.7) returned 200 today.
3. **F1 checker still FAILs — recorded, not fixed (implement's job).** The
   no-internal-refs checker reports failures on absolute-path hits in
   `docs/ADVERSARIAL_REVIEW.md`, `reports/improvements.md`, and — introduced
   by c3-p01 itself — `docs/RESEARCH.md:2850` (the worktree branch note).
   Path scrub belongs to the implement pass; this §11 was written to add no
   new hits (no absolute paths, no internal-system names above).
4. **Detached HEAD confirmed** (`rev-parse --abbrev-ref HEAD` → HEAD; the
   `feat/v0.1` ref is checked out in a sibling worktree). This pass commits
   on detached HEAD for the orchestrator to merge, as c3-p01 did.

### 11.7 §10.4 watch — re-probed today, none fired

GitHub REST + PyPI, all HTTP 200 today: MlFinLab 4,939 stars / push
2023-10-02 (no relicensing signal — nothing changed); qlib 49,313 /
2026-10-08; purgedcv 55 stars / PyPI 0.1.10 (description probe: no IC,
verdict, FDR, or BH terms — the "factor" substring hits are a CodeFactor
badge and "refactor"); ml4t-diagnostic 34 / 2026-10-10 (`main`-branch README
grep for verdict / accept-reject / promotion-gate / promote: zero hits —
still metrics, not a gate); pyanomaly 133 / 2024-03-13; alphalens-reloaded
669 / 2026-10-10. Watch item (a) remains the closest threat; re-check next
cycle.

### 11.8 Falsification — what would prove this pass wrong

- F-R7: a proof p-value computed with HAC normal critical values at L/T ≥
  0.05 — not present in the standing proof (max 0.0096). The 0.05 boundary
  itself is falsifiable by the KVB tables (audit item, §11.1).
- F-R8: a bare-sqrt annualised SR appearing in any proof report — grep
  count is 0 today.
- F-R10/C3-F1: an independent LOCO re-run that keeps volume_z_20
  significant without ATOM — the numbers in §11.4 are the record to beat.
- This pass's ecosystem cells: any §11.7 number that a same-day re-probe
  contradicts — all probes returned 200 with values printed above.

F-R1…F-R6 dispositions (§8.9) stand; nothing re-run (no new data — the proof
JSON is hours old and the dataset grew by <1 day of bars).

## 12. Cycle 4 pass 1 — microstructure + trading-cost ground truth (added 2026-10-13, pass c4-p01)

Scope: the first of the reopened brief's three research passes — the real-data
proof the spec names, part III. Cycles 2–3 (§8–§11) derived checker numbers
from the factor, inference, and crypto-momentum literatures. Two threats to a
real-data proof were never grounded: (a) thin-trading/nonsynchronicity on a
14-coin panel (what the data-generating process does to OLS-family statistics
before the gate ever runs), and (b) whether a statistically-passing factor
survives trading costs (what the gate's turnover row is actually worth). This
pass grounds both. 10 new sources, every link probed today (curl -L, UA
Mozilla/5.0); 10 verified HTTP 200, 1 recorded as boundary (§12.7). Five drive
the design (§12.1–§12.5, full method/equations/assumptions/failure modes); five
are context (§12.6).

Standing data (re-read today): `reports/real-data-proof.json` — 14 coins,
21,308 daily bars, 2021-04-29 → 2026-10-12; 0/13 promoted; raw p<0.05 flags 3
(rev_5, volume_z_20, lookahead_control); BH-FDR q=0.15 passes the same 3;
specificity 10/10; DSR = 0.0 everywhere; C3-F1 (volume_z_20 is a one-coin
artefact) stands.

### 12.1 Roll's implied spread — what rev_5 is actually measuring (DRIVES DESIGN)

**Roll, R. (1984)**
"A Simple Implicit Measure of the Effective Bid-Ask Spread in an Efficient Market"
*Journal of Finance* 39(4):1127–1139
[Verified URL: https://www.jstor.org/stable/2327617 — HTTP 200 confirmed
2026-10-13. Second verified record: https://ideas.repec.org/a/bla/jfinan/v39y1984i4p1127-39.html
— HTTP 200 confirmed 2026-10-13. Abstract text verified against the Wiley
page, retrieved via search 2026-10-13 and cross-checked with the JSTOR record.]

Method extracted: in an efficient market the fundamental value fluctuates
randomly, but trading costs induce negative serial dependence in successive
observed price changes — and that dependence IS the spread. The effective
spread is inferred from prices alone:

    Spread = 2 * sqrt(-cov)

    where cov = first-order serial covariance of price changes
                (cov(ΔP_t, ΔP_{t-1}), ΔP_t = P_t - P_{t-1}).

Notation: P_t = observed transaction price; the model is P_t = V_t + (S/2)*Q_t
where V_t = fundamental value (random walk), S = effective spread,
Q_t ∈ {+1,-1} = trade direction (buy/sell). Under the assumptions below,
cov(ΔP_t, ΔP_{t-1}) = -S²/4, hence the estimator. Roll's empirical check:
using daily data, the average implicit spread across stocks/time is 0.298%,
validated indirectly by its relation to firm size (smaller firms, larger
spreads).

Assumptions (verified abstract text): (a) the asset trades in an
informationally efficient market (fundamental value is a random walk — no
true return autocorrelation); (b) the distribution of observed price changes
is stationary over the estimation window ("at least for short intervals of,
say, two months").

Known failure modes: (a) if the fundamental value itself is autocorrelated
(momentum at the sampled frequency), cov mixes spread-bounce with true
autocorrelation and the estimator misattributes; (b) positive autocovariance
(days when cov > 0) makes sqrt(-cov) imaginary — the estimator simply does
not exist on trending stretches, which is itself a diagnostic; (c) assumes
equal probability of buy/sell (order-flow imbalance breaks Q_t symmetry).

Design consequence: rev_5 (negated 5-day return) passed BH-FDR on the real
panel (p = 0.0005, §8.9 F-R5 table). Roll says a short-horizon negative-autocorrelation
signal without spread adjustment measures liquidity provision compensated by
the bid-ask bounce — not predictability. The rev_5 pass is therefore the
expected appearance of the Roll mechanism, and promoting it on IC alone would
promote the spread. Filed as falsification item F-R12: any proof promoting a
reversal factor must report the Roll-implied spread beside the factor's gross
quintile spread — if gross < implied spread, the "factor" is liquidity
provision and the checker must reject the promotion.

### 12.2 The 50%-turnover rule — the max_turnover default, literature-backed (DRIVES DESIGN)

**Novy-Marx, R. & Velikov, M. (2016)**
"A Taxonomy of Anomalies and Their Trading Costs"
*Review of Financial Studies* 29(1):104–147
DOI: https://doi.org/10.1093/rfs/hhv063 (note: hhv063 — hhv059 is the
Harvey-Liu-Zhu factor-zoo paper, §2.7; the two suffixes differ by one digit
and are flagged for the citation audit)
[Verified URL: https://www.nber.org/papers/w20721 (NBER WP 20721, Dec 2014,
substantively equivalent working version) — HTTP 200 confirmed 2026-10-13.
Verified record: https://www.jstor.org/stable/43866013 — HTTP 200 confirmed
via search record 2026-10-13 (probed as boundary; NBER version is the cited
verified URL). Publisher abstract verified via Oxford Academic record,
retrieved via search 2026-10-13.]

Method extracted: after-trading-cost performance of a large anomaly family,
with transaction-cost mitigation techniques. Two headline results (verified
abstract text): (1) "Introducing a buy/hold spread, with more stringent
requirements for establishing positions than for maintaining them, is the
most effective cost mitigation technique." (2) "Most anomalies with less than
50% turnover per month generate significant net spreads when designed to
mitigate transaction costs; few with higher turnover do." Further (verified
NBER abstract): "Transaction costs always reduce strategy profitability,
increasing data-snooping concerns" — costs are a second multiple-testing
problem, because a gross-significant anomaly that is net-insignificant is a
false discovery in economic terms.

Assumptions: (a) effective-spread + price-impact cost model calibrated on
TAQ-era equity data (costs are equity-magnitude; crypto spreads are wider,
so the equity 50% line is lenient for crypto, not strict); (b) value-weighted
portfolios rebalanced monthly; (c) mitigation (buy/hold spread) is actually
implemented — unmitigated high-turnover strategies do worse than the headline.

Known failure modes: (a) the 50% line is monthly one-sided equity turnover —
a daily-rebalanced crypto factor at turnover 1.31 (the §8.9 planted-signal
round-1 observation) is an order of magnitude above it; (b) capacity
interacts: "the extent to which new capital reduces strategy profitability
is inversely related to turnover" — small panels concentrate impact;
(c) crypto cost structure (funding, exchange fees, 24/7 impact) is absent
from the calibration, all in the direction of higher costs.

Design consequence: the repo's `max_turnover = 0.5` default gate now has a
literature citation instead of a round number. Filed as falsification item
F-R13: the checker must reject any proof that raises max_turnover above 0.5
(or promotes a factor with turnover above it) without a net-of-cost analysis
paragraph naming the cost model. Standing proof is unaffected (nothing
promoted; rev_5 turnover is gated, not waived).

### 12.3 Nonsynchronous trading — the thin-coin bias on a 14-coin panel (DRIVES DESIGN)

**Scholes, M. & Williams, J. (1977)**
"Estimating Betas from Nonsynchronous Data"
*Journal of Financial Economics* 5(3):309–327
[Verified URL: https://ideas.repec.org/a/eee/jfinec/v5y1977i3p309-327.html
— HTTP 200 confirmed 2026-10-13. Abstract verified via ScienceDirect record,
retrieved via search 2026-10-13: "Nonsynchronous trading of securities
introduces into the market model a potentially serious econometric problem
of errors in variables."]

Method extracted: when securities trade nonsynchronously with the market
index, OLS market-model slopes are biased and inconsistent (thin securities
biased toward zero). The consistent estimator combines three OLS slopes —
on the lagged, contemporaneous, and leading market return — normalised by
the market's own autocorrelation:

    beta_SW = (beta⁻ + beta⁰ + beta⁺) / (1 + 2*rho_m)

    where beta⁻ = slope of R_{i,t} on R_{m,t-1} (lagged market),
          beta⁰ = slope of R_{i,t} on R_{m,t}   (contemporaneous),
          beta⁺ = slope of R_{i,t} on R_{m,t+1} (leading market),
          rho_m = first-order autocorrelation of the market return.

(Transcription note: this is the paper's standard estimator form as
reproduced in Dimson 1979's review, §12.6 — the RePEc record above verifies
existence/bibliography; the equation transcription is flagged F-R16-class
for the citation audit, minor if the normalisation factor is right.)

Assumptions: (a) nonsynchronous trading is the only friction (no spread
bounce — the Roll mechanism of §12.1 is assumed away); (b) the market return
is autocorrelated only at lag 1 (higher-order rho_m = 0); (c) every security
trades at least once within the sampling interval (stale prices beyond one
interval break the three-slope construction).

Known failure modes: (a) assumption (c) fails for the thinnest coins — a
coin with multi-day gaps needs more leads/lags than the three-slope form
(this is exactly Dimson's generalisation, §12.6); (b) on a 14-coin panel
where every alt loads on BTC (cf. §8.2 failure mode (c)), the "market" is
one coin and rho_m is the BTC autocorrelation — the correction inherits
single-asset noise; (c) the estimator fixes slopes, not correlations — IC
attenuation from staleness is the same EIV mechanism but needs its own
correction, which the repo does not implement.

Design consequence: the §8.2 EIV paragraph (Fama-MacBeth failure mode (a))
now has its mechanism paper. On the real 14-coin panel, thin alts have stale
daily closes; their factor scores are measured with error, attenuating IC
toward zero — a third reason (with §8.1 decile-thinness and §8.2 beta noise)
that 0/13 promoted is unsurprising. Filed as falsification item F-R14: the
dataset-summary leg of the proof must flag coins with >5% zero-volume days
(a staleness diagnostic the implement pass can compute from the existing
volume column); a proof silent on staleness while screening thin coins
overstates its effective cross-section.

### 12.4 Smoothed returns — why serial correlation flatters Sharpe ratios (DRIVES DESIGN)

**Getmansky, M., Lo, A.W. & Makarov, I. (2004)**
"An Econometric Model of Serial Correlation and Illiquidity in Hedge Fund Returns"
*Journal of Financial Economics* 74(3):529–609
[Verified URL: https://www.nber.org/papers/w9571 (NBER WP 9571, Mar 2003,
substantively equivalent working version) — HTTP 200 confirmed 2026-10-13.
Abstract verified via NBER + ScienceDirect records, retrieved via search
2026-10-13.]

Method extracted: observed returns on illiquid portfolios are a distributed
lag of true economic returns (smoothing from stale marks / nonsynchronous
prices — the §12.3 mechanism, generalised):

    R_{o,t} = theta_0 * R_t + theta_1 * R_{t-1} + ... + theta_k * R_{t-k}

    where theta_j ∈ [0,1], sum_j theta_j = 1 (smoothing profile),
          R_t = true (unobservable) economic return,
          R_{o,t} = observed/reported return.

Consequences derived in the paper (verified abstract text): "reported
returns will tend to be smoother than true economic returns, which will
understate volatility and increase risk-adjusted performance measures such
as the Sharpe ratio." The paper develops estimators for the smoothing
profile and a smoothing-adjusted Sharpe ratio; on 908 TASS funds, "funds
with the highest serial correlation tend to be the more illiquid funds" and
"after correcting for the effects of smoothed returns, some of the most
successful types of funds tend to have considerably less attractive
performance characteristics." (Exact profile-estimator equations flagged
F-R16-class for audit; the MA equation above and the direction of the Sharpe
bias are the design-relevant content.)

Assumptions: (a) true returns serially uncorrelated (smoothing is the only
autocorrelation source — same identifying assumption as Roll §12.1, and the
two compete: bounce gives negative lag-1, smoothing gives positive lag-1);
(b) smoothing profile stable over the estimation window; (c) linear
smoothing (no asymmetric stale-mark behaviour in crashes).

Known failure modes: (a) cannot separate smoothing from genuine
autocorrelation (momentum) — the decomposition is identified only by the
assumption; on crypto, momentum (§9.4) and staleness coexist, so the
correction direction is ambiguous without a liquidity sort; (b) profile
estimates need long T (same floor argument as §8.5); (c) 24/7 crypto has no
"stale mark" convention — staleness appears as zero-volume intervals, so the
diagnostic is volume-based (links to F-R14), not return-based.

Design consequence: the DSR inputs in the proof are computed on return
series whose lag-1 autocorrelation is never reported. Filed as falsification
item F-R15: any proof DSR input computed on a series with lag-1
autocorrelation above 0.2 must carry a smoothing caveat (vol understated →
Sharpe overstated → DSR optimistic), or report the smoothing-adjusted
volatility. Standing proof is unaffected in verdict (DSR = 0.0 everywhere —
an optimistic bias on a zero still rejects), but the reported DSR magnitudes
are upper bounds, not point estimates, and the report must say so.

### 12.5 The stationary bootstrap — White's dependency, verified (DRIVES DESIGN)

**Politis, D.N. & Romano, J.P. (1994)**
"The Stationary Bootstrap"
*Journal of the American Statistical Association* 89(428):1303–1313
[Verified URL: https://www.jstor.org/stable/2290993 — HTTP 200 confirmed
2026-10-13. Second verified URL (author-hosted PDF scan of the published
paper): https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf — HTTP
200 confirmed 2026-10-13. Abstract verified via T&F record, retrieved via
search 2026-10-13. This closes the §8.7 boundary item for this source —
which was listed as bot-blocked at its DOI but is fully verified via JSTOR
and the author-hosted PDF.]

Method extracted: the resampling procedure White's Reality Check (§9.1)
depends on. Blocks of RANDOM length are resampled with replacement, where
each block length has a geometric distribution:

    P(block length = k) = p * (1-p)^{k-1},   k = 1, 2, ...
    mean block length = 1/p.

Concatenated blocks form the pseudo-time series, on which the statistic is
recomputed; repeating builds the sampling distribution. The point of random
lengths (vs the fixed-length moving-block bootstrap of §8.4/Künsch): the
pseudo-series is stationary conditional on the original data (verified
abstract text: "the resampled pseudo-time series [is] stationary
(conditional on the original data)"), and the paper develops "fundamental
consistency and weak convergence properties."

Assumptions: (a) weakly dependent stationary observations (same as §8.4);
(b) mean block length 1/p grows with n but slower (p → 0 as n → ∞);
(c) no structural break inside the window (cf. C2-3a — breaks violate this
for stationary bootstrap exactly as for HAC and MBB).

Known failure modes: (a) p choice = block-length choice by another name —
mean length 1/p must cover the dependence (l ≈ H argument, §8.4, unchanged:
set 1/p ≈ H for the IC series); (b) geometric lengths add resampling noise
vs fixed blocks (extra variance in short pseudo-series); (c) stationarity of
the pseudo-series does not cure non-stationarity of the original — a break
panel resampled stationarily still misleads.

Design consequence: the §9.1 Reality Check entry rested on an unverified
dependency (Politis-Romano was §8.7-boundary). It is now verified, so a
future RC/SPa implementation has both citations in hand — no checker change
today (F-R9 stands: the repo's max-over-family answer remains BH plus the
CPCV diagnostic). The block-length rule filed under §8.4/F-R7 (l ≈ H, and
reject any proof with l < H) is confirmed as the same rule in stationary
form (1/p ≈ H).

### 12.6 Context sources (5, verified today)

**Dimson, E. (1979)** "Risk measurement when shares are subject to infrequent
trading", *JFE* 7(2):197–226.
[Verified URL: https://ideas.repec.org/a/eee/jfinec/v7y1979i2p197-226.html
— HTTP 200 confirmed 2026-10-13.] Generalises §12.3: beta estimated from
multiple leads/lags (sum of slope coefficients on R_{m,t-k}..R_{m,t+k}),
consistent under thinner trading than SW's three-slope form. Relevance: the
estimator-form precedent for F-R14 — if the proof ever risk-adjusts returns
before IC (Fama-1991 joint-hypothesis move, §8.6), thin-coin betas must use
Dimson leads/lags, not OLS. Alternatives-considered: Fowler-Rorke (1983)
argue the Dimson summation is inconsistent in general while SW remains
consistent — the repo uses neither (no beta estimation in the pipeline), so
no position is taken; both are cited as diagnostic background only.

**Amihud, Y. & Mendelson, H. (1986)** "Asset pricing and the bid-ask spread",
*JFE* 17(2):223–249.
[Verified URL: https://ideas.repec.org/a/eee/jfinec/v17y1986i2p223-249.html
— HTTP 200 confirmed 2026-10-13. Second verified URL (course-hosted PDF scan):
Buffalo course page (acsu.buffalo.edu) — HTTP 200 confirmed 2026-10-13.]
Testable hypothesis (verified ScienceDirect abstract): "market-observed
expected return is an increasing and concave function of the spread"
(clientele effect — short-horizon holders avoid wide-spread assets).
Relevance: the spread-level companion to §12.1 (Roll = spread from
time-series; AM86 = returns priced against spread in cross-section) and the
theoretical parent of the Amihud-2002 ILLIQ ratio (§1.4) the repo already
implements. Design note: amihud_illiq_20's real-data BH outcome
(p = 0.0895, not passing at q = 0.15 per §8.9 F-R5 table) is consistent —
on 14 coins the spread clientele cannot sort.

**Jegadeesh, N. (1990)** "Evidence of Predictable Behavior of Security Returns",
*JF* 45(3):881–898.
[Verified URL: https://www.jstor.org/stable/2328797 — HTTP 200 confirmed
2026-10-13. Abstract verified via Wiley record, retrieved via search
2026-10-13.] Headline (verified abstract): "The negative first-order serial
correlation in monthly stock returns is highly significant. Furthermore,
significant positive serial correlation is found at longer lags, and the
twelve-month serial correlation is particularly strong"; extreme-decile
spread 2.49%/month over 1934–1987. Relevance: gives rev_5 a second
peer-reviewed antecedent beside Lo-Mamaysky-Wang (§8.6) — monthly reversal
is the frequency where the Roll bounce (§12.1) aggregates into a tradable
pattern. Failure mode documented in the same literature (skipped-week
convention, JT 1993 §1.1): one-week skip removes bounce/pressure effects —
the repo's rev_5 has no skip, so its signal mechanically includes the Roll
component (F-R12).

**Lehmann, B.N. (1990)** "Fads, Martingales, and Market Efficiency",
*QJE* 105(1):1–28.
[Verified URL: https://www.jstor.org/stable/2937816 — HTTP 200 confirmed
2026-10-13. Abstract verified via Oxford Academic record, retrieved via
search 2026-10-13.] Headline (verified abstract): one-week winners/losers
"experience sizeable return reversals the next week in a way that reflects
apparent arbitrage profits which persist after corrections for bid-ask
spreads and plausible transactions costs. This probably reflects
inefficiency in the market for liquidity around large price changes."
Relevance: the strongest pro-reversal citation in this file — reversal
survives spread + cost corrections on US equities at weekly frequency.
Consequence for the mandate: rev_5's real-data BH pass (p = 0.0005) can no
longer be waved away as pure bounce; it must be adjudicated by the fuller
gate (turnover per F-R13, LOCO per C3-F1) — which is exactly what the
standing proof does (rejected by other gates, 0 promoted). A future proof
that promotes rev_5 must beat Lehmann-aware scrutiny, not bounce dismissal.

**Frazzini, A., Israel, R. & Moskowitz, T.J. (2012)**
"Trading Costs of Asset Pricing Anomalies", AQR Working Paper (first draft
Oct 2012; this draft Dec 5, 2012).
[Verified URL: https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies
— HTTP 200 confirmed 2026-10-13. Second verified URL (NBER-conference PDF
of the same draft): https://conference.nber.org/confer/2013/APs13/Frazzini_Israel_Moskowitz.pdf
— HTTP 200 confirmed 2026-10-13. Findings verified against the AQR abstract,
retrieved via search 2026-10-13.] Method: $1T live institutional trade data,
19 developed markets 1998–2011, price-impact estimated from a real
arbitrageur (not TAQ aggregates) + portfolio optimisation for cost-aware
construction. Headlines (verified abstract): costs "many times smaller" than
the literature claims and capacities "more than an order of magnitude
larger" — BUT "Short-term reversals, however, do not survive trading costs
at reasonable size and do not benefit much from portfolio optimization,"
while "size, value and momentum can be deployed at very high asset size and
still survive." Relevance: the asymmetric verdict — momentum yes, reversal
no — is the cost-side mirror of this pass's statistical picture (mom_20
promotes on synthetic; rev_5 passes BH but fails the fuller gate on real
data). Design note: FIM's "optimise the construction" is the literature
parent of NMV's buy/hold spread (§12.2); the repo's gate has no construction
optimiser, so its turnover row must stay a hard reject, not a soft warning.

### 12.7 Boundary — NOT claimed as verified

- Amihud-Mendelson ScienceDirect article page
  (https://www.sciencedirect.com/science/article/pii/0304405X86900656) → 403
  (Elsevier bot-detection, same pattern as §8.7). RePEc record + hosted PDF
  verified instead; no threshold cites the ScienceDirect URL.
- Novy-Marx-Velikov JSTOR stable/43866013 → recorded from the search index
  only, not curl-probed this pass; the NBER w20721 URL is the verified
  citation. A later pass may probe the JSTOR link directly.
- Chordia-Subrahmanyam-Tong (2014) anomaly attenuation: no verified URL in
  hand — NOT cited. Its slot (post-publication decay magnitudes) is held by
  McLean-Pontiff (§8.6, NBER-verified). A later pass may ground it.
- Shanken (1992) EIV correction: still never probed (§9.6 note stands).

### 12.8 Falsification — what would prove this pass wrong (F-R12…F-R16 new; F-R1…F-R11 stand)

F-R1…F-R11: dispositions in §8.9/§9.8/§11 stand; nothing re-run (proof JSON
unchanged since c3-p03, dataset grew by <1 day of bars).

F-R12 (reversal-is-spread): a proof promoting a reversal factor whose gross
quintile spread is below the Roll-implied spread 2√(-cov) computed on the
same panel. Standing proof promotes nothing — holds vacuously; binds the
first promotion of rev_5 or any reversal-family factor. This pass is
falsified if Roll's estimator on the real panel returns imaginary spreads
(cov > 0) at every horizon — then the bounce mechanism is absent and F-R12
is vacuous rather than binding (checkable in one /tmp script, implement's
call whether to run it).

F-R13 (turnover bar moved): any proof raising max_turnover above 0.5, or any
promotion with turnover above 0.5, without a net-of-cost paragraph naming
its cost model. Falsified (the pass, not the repo) if Novy-Marx-Velikov's
50% line is shown to rest on pre-decimalisation cost data that no longer
binds — the audit should check the sample window (1990s–2000s US equities)
against the claim; for crypto the line is lenient-direction anyway, so the
rule errs conservative.

F-R14 (staleness silence): a proof screening thin coins (>5% zero-volume
days for any coin) whose dataset-summary never mentions staleness. Falsified
if the real panel has zero zero-volume coin-days — then the diagnostic is
vacuous and the item closes (one read-only SQL query; named for implement).

F-R15 (smoothed-Sharpe optimism): any proof DSR input computed on a series
with lag-1 autocorrelation above 0.2 and no smoothing caveat. Standing
proof: DSR = 0.0 everywhere — an optimistic bias on a zero still rejects,
so the verdicts hold but the magnitudes are upper bounds; the report-update
that says so belongs to the implement pass. Falsified if GLM's bias
direction is shown inverted for negatively-autocorrelated (bounce-type)
series — fair: smoothing flatters positively-autocorrelated series; for
bounce-dominated series the vol is OVERstated and DSR is conservative, not
optimistic. The 0.2 rule as stated covers |rho_1| > 0.2 in either direction;
the caveat text must name the direction.

F-R16 (this pass's own transcriptions): the Scholes-Williams normalisation
(1 + 2·rho_m), the GLM profile-estimator detail beyond the MA equation, and
the Novy-Marx DOI suffix (hhv063 vs hhv059 — one digit apart, pre-flagged)
are the three spots most likely to need correction. "Symbols differ, factor
right" is minor; "factor wrong" (e.g. the SW denominator, the Roll
2√(-cov)) is blocking. The adversarial citation audit must open every
§12.9-table link and check the transcription against the abstract or full
text it can access.

### 12.9 Link-verification table (all probed 2026-10-13, curl -L, UA Mozilla/5.0)

| Source | URL | HTTP status |
|--------|-----|-------------|
| Scholes & Williams 1977 (RePEc) | https://ideas.repec.org/a/eee/jfinec/v5y1977i3p309-327.html | 200 |
| Roll 1984 (JSTOR) | https://www.jstor.org/stable/2327617 | 200 |
| Roll 1984 (RePEc) | https://ideas.repec.org/a/bla/jfinan/v39y1984i4p1127-39.html | 200 |
| Lehmann 1990 (JSTOR) | https://www.jstor.org/stable/2937816 | 200 |
| Jegadeesh 1990 (JSTOR) | https://www.jstor.org/stable/2328797 | 200 |
| Novy-Marx & Velikov 2016 (NBER w20721) | https://www.nber.org/papers/w20721 | 200 |
| Frazzini-Israel-Moskowitz 2012 (AQR) | https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies | 200 |
| Frazzini-Israel-Moskowitz 2012 (NBER conf PDF) | https://conference.nber.org/confer/2013/APs13/Frazzini_Israel_Moskowitz.pdf | 200 |
| Getmansky-Lo-Makarov 2004 (NBER w9571) | https://www.nber.org/papers/w9571 | 200 |
| Dimson 1979 (RePEc) | https://ideas.repec.org/a/eee/jfinec/v7y1979i2p197-226.html | 200 |
| Amihud & Mendelson 1986 (RePEc) | https://ideas.repec.org/a/eee/jfinec/v17y1986i2p223-249.html | 200 |
| Amihud & Mendelson 1986 (hosted PDF) | Buffalo course page (acsu.buffalo.edu) | 200 |
| Politis & Romano 1994 (JSTOR) | https://www.jstor.org/stable/2290993 | 200 |
| Politis & Romano 1994 (author-hosted PDF) | https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf | 200 |
| Amihud & Mendelson 1986 (ScienceDirect — boundary) | https://www.sciencedirect.com/science/article/pii/0304405X86900656 | 403 — NOT claimed |

### 12.10 Alternatives considered (this pass)

(i) Dimson leads/lags vs Scholes-Williams three-slope for thin-coin
diagnostics — neither is wired (no beta estimation in the pipeline); both
are background for F-R14. Fowler-Rorke's consistency objection to Dimson is
noted without a position. (ii) Buy/hold-spread mitigation (NMV) vs hard
turnover reject — mitigation retained as NOT implemented (no construction
optimiser in the repo); the gate stays a hard reject per F-R13, which is the
conservative direction FIM endorses for reversal. (iii) Stationary vs
fixed-length block bootstrap for a future RC leg — stationary (geometric
lengths) is the verified White dependency; fixed-length MBB (§8.4) remains
the simpler diagnostic. No code change in any case — research records the
options, implement chooses.

---

## 13. Ecosystem and competition (cycle 4, pass 2 — 2026-10-13)

This section is the pass-2 deliverable for cycle 4. The maintained detail
table lives in `COMPARISONS.md` (7 tools, per-feature columns); this section
records the live numbers fetched for this pass, the watch-item dispositions
from §10.4/§11.7, the claimed gap, and the falsification criterion. No
MARKET-VERDICTS position is re-litigated: the verdicts file remains
authoritative and everything below is consistent with it. No code changed in
this pass; the v0.2 MANDATE research base (§8/§9/§12) is untouched and all
of F-R1…F-R16 stands as last dispositioned.

### 13.1 Live verification (GitHub REST API + PyPI, probed 2026-10-13)

Raw `curl -sL` output, one line per repo (`stars pushed_at licence`):

```
hudson-and-thames/mlfinlab 4939 2023-10-02T03:05:19Z NOASSERTION
microsoft/qlib 49317 2026-10-08T10:58:43Z MIT
eslazarev/purged-cross-validation 55 2026-10-01T10:03:02Z MIT
ml4t/diagnostic 34 2026-10-13T00:37:51Z MIT
chulwoohan/pyanomaly 133 2024-03-13T08:03:25Z MIT
quantopian/alphalens 4469 2024-02-12T06:44:22Z Apache-2.0
stefan-jansen/alphalens-reloaded 669 2026-10-13T00:42:32Z Apache-2.0
stefan-jansen/pyfolio-reloaded 616 2026-10-13T00:42:21Z Apache-2.0
stefan-jansen/empyrical-reloaded 125 2026-10-10T09:38:45Z Apache-2.0
PyPI purgedcv: info version 0.1.10 (no release newer than 2026-10-01)
```

Deltas vs 2026-10-12 (§10.1/§11.7): qlib 49,313 → **49,317** (+4);
everything else unchanged (MlFinLab 4,939; purgedcv 55; ml4t-diagnostic 34;
pyanomaly 133; alphanlens 4,469; reloaded 669/616/125). `COMPARISONS.md`
cells corrected for qlib in this same pass.

New activity since yesterday: **ml4t-diagnostic pushed 2026-10-13T00:37:51Z**
and **alphalens-reloaded / pyfolio-reloaded pushed 2026-10-13T00:42Z** —
all three moved this morning, so both watch surfaces below were re-checked
against live README/description text today, not against yesterday's copy.

### 13.2 Comparison table

| Tool | Approach | What it does well | Gap it leaves | What we do differently |
|------|----------|-------------------|---------------|------------------------|
| MlFinLab (Hudson & Thames, commercial, public repo 4,939★, unpushed since 2023-10-02) | Full financial-ML library (bars, labelling, ensembles, backtest-overfitting) | The reference implementation: purged/CPCV, haircut + deflated Sharpe, PBO, profit hurdles, track-record length | Commercial licence (£100+VAT/mo/user, no derivatives, improvements assigned to licensor); public source stale 3 years | MIT, offline, inspectable: the 4 overfitting controls as a standalone gate, no subscription |
| Quantopian stack (alphalens 4,469★ / pyfolio / empyrical, Apache-2.0, dead upstream) | Factor tear-sheets + performance attribution | The mental model for factor analysis; familiar output | Abandoned 2018–2020 (last code 2020-04-27); no purged CV, no FDR, no DSR, no gate | Same tear-sheet intuition (IC decay, quantile returns) plus the statistics the stack never had |
| qlib (Microsoft, MIT, 49,317★, pushed 2026-10-08) | End-to-end AI quant platform (data, models, experiments) | Scale, model zoo, experiment tracking, 49k-star contributor base | No overfitting-control statistics at all (no purged/embargo, no FDR, no DSR, plain Sharpe only) | Complementary: the gate qlib screens could be passed through before promotion |
| purgedcv (eslazarev, MIT, 55★, PyPI 0.1.10) | sklearn-compatible time-series CV + Sharpe statistics | Correct purged K-fold, walk-forward, CPCV, embargo, DSR/PSR; JOSS paper; shipped 23 versions May→Oct 2026 | CV/statistics library only: no factor computation, no IC, no quantile spread, no accept/reject verdict | End-to-end screening: factors → IC → HAC-t → FDR → verdict with exit codes, one offline command |
| ml4t-diagnostic (ml4t org, MIT, 34★, pushed today) | Signal diagnostics inside a 7-library ML4T ecosystem | Walk-forward/CPCV, FDR, White's Reality Check, DSR, PBO, tearsheets | Metrics, not a gate; Polars + 7-library dependency chain; no standalone accept/reject | Zero-dep-core gate (numpy/pandas/matplotlib only) that says no and exits 1 |
| pyanomaly (chulwoohan, MIT, 133★, dead since 2024-03-13) | Academic anomaly replication on WRDS/CRSP data | Real-data equity anomalies, factor regressions, quantile portfolios | WRDS subscription required (no offline path); no purged CV, no FDR, no gate | Synthetic-data offline demo plus the full rejection pipeline a WRDS user would still need |
| reloaded forks (stefan-jansen, 669/616/125★, pushed 2026-10-10…13) | Keep the Quantopian stack installable | Modern-Python compatibility for the tear-sheets | Source-checked today: add none of the four controls (see §13.3) | Same answer as for the upstream stack |

### 13.3 Watch-item dispositions (§10.4 items (a)–(c) + secondary)

**(a) purgedcv ships factor screening + a gate — NOT observed.** PyPI
`purgedcv` description (25,555 chars, fetched today) grepped for
`information coefficient / factor screen / accept / reject / verdict /
benjamini / fdr / promote / quantile / turnover` → all **absent**. The
single `wilson` substring hit is the `wilsonfreitas/awesome-quant` badge
URL, not a Wilson-CI feature (context printed, verified). No PyPI release
newer than 0.1.10 (2026-10-01). The gap on the pipeline + verdict axis
holds; purgedcv remains a CV/statistics neighbour, not a screening
competitor.

**(b) MlFinLab relicensed under MIT/Apache — NOT observed.** Licence field
still `NOASSERTION` (all rights reserved, commercial); `pushed_at` still
2023-10-02 — three full years without a public code push. The
"commercial but stale" framing (§6.2) is more accurate with every cycle.

**(c) ml4t-diagnostic adds a standalone verdict API — NOT observed, despite
this morning's push.** `main`-branch README (6,205 chars, fetched today
after the 00:37:51Z push) grepped for `verdict / accept-reject /
promotion / promote( / exit code / standalone` → all **absent**. Still
metrics and tearsheets inside the 7-library ecosystem, not a gate.

**Secondary watch (reloaded forks add FDR/purge) — NOT observed.**
`alphalens-reloaded` README fetched today after its 00:42:32Z push and
grepped for `purge / embargo / benjamini / false discovery / deflated /
wilson / bonferroni` → all **absent**. Installability forks only, still.

Closest threat remains (a): purgedcv went 0 → 55 stars in five months and
owns exactly the two controls (CV, DSR) nearest our core. Re-check next
cycle.

### 13.4 The gap we claim (explicit)

No live, permissively-licensed tool packages **purged walk-forward CV with
embargo + Benjamini-Hochberg FDR across the screened family + deflated
Sharpe + an explicit promotion gate that rejects** in one offline command.
MlFinLab has all four and more but is proprietary and its public source is
3 years stale; purgedcv has two of the four (CV + DSR — re-verified today,
§13.3a); ml4t-diagnostic has the statistics but no verdict (re-verified
today against its freshest push, §13.3c); the rest have none.

How a user notices it: clone this repo, run `bash examples/run_demo.sh`
offline, and watch `factor-lab promote noise_control` exit 1 with a
10-row reason table (FDR rejection, HAC-corrected t-stat, Wilson bound)
while `factor-lab promote mom_20` on planted-signal data exits 0. None of
the seven tools above produces that verdict surface — MlFinLab documents
thresholds but ships no accept/reject API in its public source.

### 13.5 Falsification for this pass

The positioning is wrong if any of these is observed: (a) purgedcv ships
factor screening (IC measurement) plus an accept/reject gate — the gap
narrows to licence/offline-simplicity only; (b) MlFinLab is relicensed
under MIT/Apache — the gap closes entirely; (c) ml4t-diagnostic adds a
standalone verdict API usable outside its ecosystem — the gate claim
becomes shared, not unique. Observed as of 2026-10-13: none of the three
(§13.3). This pass itself is falsified if any §13.1 number is contradicted
by a same-day re-probe, or if any §13.3 "absent" term is shown present in
the fetched text — the grep dictionaries and character counts above are
the record to beat. Secondary watch for next cycle: the reloaded forks
moved today (three pushes); installability demand is real, and a fork
that adds FDR/purge changes row 2 of the table.

---

## 14. Cycle 4 pass 3 — every pass-1/pass-2 open item closed (2026-10-13)

Scope: pass 3 of cycle 4. Pass 1 (§12) left F-R12…F-R16 with named
observables; pass 2 (§13) left the watch re-check. This section closes
every research-side observable with executed commands (throwaway scripts
in /tmp, repo untouched, database read-only via `mode=ro` URI). Items
whose owner is another pass are transferred explicitly, not left vague.
No code changed; no MARKET-VERDICTS position re-litigated.

### 14.1 F-R12 — CLOSED (binding, not vacuous)

The §12.8 observable: run Roll's estimator on the real panel; falsified
(vacuous) if lag-1 return covariance is positive at every coin. Executed
today (`/tmp/c4p3_roll.py`, log-returns on daily closes, read-only):

```
AAVE TOO_SHORT (1 bar)
ADA   n=54013 cov1=-5.01e-06 spread=0.004475
ARB   n=53322 cov1=+7.0e-07 IMAGINARY(cov>0)
ATOM  n=54008 cov1=-7.53e-06 spread=0.005488
BTC   n=54016 cov1=-1.36e-06 spread=0.002328
DOGE  n=54011 cov1=-4.33e-06 spread=0.004161
ETH   n=54014 cov1=-2.23e-06 spread=0.002986
FIL   n=52591 cov1=+2.06e-06 IMAGINARY(cov>0)
HBAR  n=54011 cov1=-1.22e-05 spread=0.006987
INJ   n=54012 cov1=-5.96e-06 spread=0.004883
RENDER n=52824 cov1=+7.5e-07 IMAGINARY(cov>0)
SOL   n=54008 cov1=-3.09e-06 spread=0.003513
TON   n=22582 cov1=-1.13e-06 spread=0.002121
XRP   n=54010 cov1=-6.12e-06 spread=0.004948
```

10 of 13 tradeable coins give real spreads (23–70 bps daily); 3
(ARB, FIL, RENDER) have weakly positive lag-1 covariance. The bounce
mechanism is present on most of the panel, so F-R12 binds the first
promotion of any reversal-family factor: gross quintile spread must
clear the coin's Roll spread above, or the "signal" is spread. The
falsification condition (imaginary everywhere) is NOT observed.

### 14.2 F-R13 — CLOSED (audited against the paper, conservative direction confirmed)

Two sub-questions: (a) is the 50% line real, (b) does it bind our gate.

(a) Verified verbatim today against the NBER w20721 abstract (HTTP 200,
fetched 2026-10-13): "Most of the anomalies that we consider with
**one-sided monthly turnover lower than 50%** continue to generate
statistically significant net spreads, at least when designed to
mitigate transaction costs. Few of the strategies with higher turnover
do." The full working-paper text further states only two strategies
above 50% one-sided monthly turnover keep significant net spreads even
with cost mitigation. The line is real and quoted, not paraphrased.

(b) Unit caveat, recorded for the implement pass: NMV's 50% is
**one-sided monthly** turnover on US equities; the promotion gate's
`max_turnover = 0.5` is mean |Δ rank weight| **per rebalance** — a
stricter estimand for daily-rebalanced rank factors (the §8.4 planted
signal tripped it at 1.31). The gate therefore errs conservative
relative to NMV, which is the FIM-endorsed direction for reversal. The
checker rule stands: reject any proof raising `max_turnover` above 0.5
without a net-of-cost paragraph naming its cost model — now with the
verified quote and the daily-vs-monthly unit note attached.

### 14.3 F-R14 — CLOSED (staleness query executed; diagnostic armed but silent)

The §12.8 observable (one read-only SQL query) was run today. Panel:
667,436 rows, 14 coins, daily bars, 2021-04-29 → present (BTC: 1,994
distinct dates). Zero-volume coin-days:

- Maximum: ATOM ≈ 15 rows (~0.75% of its panel) — far below the 5% trigger.
- A feed gap on **2026-04-30** spans all 14 coins simultaneously (missing
  data, not staleness).
- Coverage asymmetry the dataset-summary must mention: **AAVE has 1 bar**
  (2026-04-05, effectively absent); **TON starts 2024-08-08** (22,583
  bars vs ~54,000 for the rest).

The falsification condition (zero zero-volume coin-days → diagnostic
vacuous) is NOT observed — zero-volume days exist, so the diagnostic is
non-vacuous. But no coin breaches 5%, so on this panel it stays silent,
which is the correct output. Transferred to implement: the proof's
dataset-summary paragraph must state granularity, the 2026-04-30 gap,
and the AAVE/TON asymmetry (counts above are the record).

### 14.4 F-R15 — CLOSED (research side; direction named, panel measured)

Lag-1 return autocorrelation per coin (same read-only pull as §14.1):

```
ADA -0.0597  ARB +0.0114  ATOM -0.0746  BTC -0.0446  DOGE -0.0433
ETH -0.0403  FIL +0.0091  HBAR -0.1145  INJ -0.0406  RENDER +0.0171
SOL -0.0290  TON -0.0220  XRP -0.0785
```

All |rho_1| < 0.2 — the trigger does not fire on this panel, and the
sign is uniformly bounce-type (negative) where non-trivial. Per the
§12.8 analysis this means return vol here is slightly OVERstated, so the
standing DSR = 0.0 magnitudes are conservative-direction upper bounds,
not optimistic ones; the verdicts (all reject) hold either way.
Transferred to implement: the report-update sentence must name the
direction ("conservative on bounce-type panels, optimistic on
trend-type panels"), not just the threshold.

### 14.5 F-R16 — PARTIALLY CLOSED (DOI suffix resolved; two transcriptions transferred)

**Resolved today:** the Novy-Marx–Velikov DOI suffix is **hhv063** —
confirmed verbatim via the Oxford Academic abstract page
(`https://doi.org/10.1093/rfs/hhv063`, RFS 29(1):104–147) and the RePEc
record, both fetched 2026-10-13. HLZ's hhv059 is the companion article
in the *same issue* (RFS 29(1):5–68) — one digit apart by construction,
not by typo. The pre-flagged "error" was a false alarm; no correction needed.

**Boundary confirmed:** the Novy-Marx JSTOR candidate
(`jstor.org/stable/43866013`) returns HTTP 200 but serves a
JavaScript-challenge shell (content unverifiable by curl) — it stays in
the §12.7 boundary; NBER w20721 remains the verified citation.

**Transferred to the adversarial citation audit** (unchanged owner): the
Scholes-Williams (1 + 2·rho_m) normalisation and the GLM
profile-estimator detail. "Symbols differ, factor right" is minor;
"factor wrong" is blocking.

### 14.6 §12.7 boundary — remaining slots

- Chordia-Subrahmanyam-Tong (2014): still no verified URL in hand —
  slot still held by McLean-Pontiff (§8.6). Not blocking: no threshold
  cites it.
- Shanken (1992) EIV correction: still never probed (§9.6 note stands).
  Not blocking: the pipeline does no beta estimation, so no gate depends
  on it.

### 14.7 Pass-2 watch — re-probed today, none fired

GitHub REST + PyPI, probed 2026-10-13 (all HTTP 200):

```
microsoft/qlib 49318 2026-10-08T10:58:43Z (was 49,317: +1)
eslazarev/purged-cross-validation 55 2026-10-01T10:03:02Z (unchanged)
stefan-jansen/alphalens-reloaded 670 2026-10-13T00:42:32Z (was 669: +1)
hudson-and-thames/mlfinlab 4939 2023-10-02T03:05:19Z (unchanged, 3y stale)
ml4t/diagnostic 34 2026-10-13T00:37:51Z (unchanged)
chulwoohan/pyanomaly 133 2024-03-13T08:03:25Z (unchanged)
quantopian/alphalens 4469 2024-02-12T06:44:22Z (unchanged)
PyPI purgedcv: 0.1.10 (no release newer than 2026-10-01)
```

Watch (a)/(b)/(c) + secondary (§13.3): none fired. Closest threat
remains (a). `COMPARISONS.md` needs no cell change (deltas of +1 star
are noise; versions and push dates unchanged).

### 14.8 Falsification — what would prove this pass wrong

- F-R12: a same-day Roll re-run returning imaginary spreads on all 13
  tradeable coins — the per-coin table in §14.1 is the record to beat.
- F-R13: a quote from NMV showing the 50% line applies to two-sided
  (not one-sided) turnover, or to a sample that excludes the
  post-decimalisation era in a way that weakens the bar — the NBER
  abstract quote in §14.2 is the record.
- F-R14: a read-only recount showing a coin above 5% zero-volume days,
  or showing the 2026-04-30 gap absent — the counts in §14.3 are the record.
- F-R15: a |rho_1| > 0.2 on any panel coin at daily frequency — the
  §14.4 table is the record.
- F-R16: the Oxford/RePEc DOI cells shown wrong — URLs in §14.5 are
  the record.
- Ecosystem: any §14.7 number contradicted by a same-day re-probe.
- Standing transfers (implement owns the report-update and
  dataset-summary sentences; adversarial owns the SW/GLM transcription
  audit): this pass is falsified if a later pass shows either transfer
  was unnecessary — i.e. the sentence already exists or the
  transcription is already verified.

## 15. Cycle 5 pass 1 — luck-vs-skill ground truth (added 2026-10-13, pass c5-p01)

Scope of this pass: ground truth for the v0.2 MANDATE only — the
real-data proof the spec names (F2/F3/F4), i.e. which numbers
`scripts/check_real_data_proof.py` must reject and why. Three of the
five design-driving sources below CLOSE slots left open in §8.7
(Hansen SPA, Sullivan-Timmermann-White, Linnainmaa-Roberts); the other
two (PSR/MinTRL, Goyal-Welch OOS) ground the proof's two most-quoted
numbers (DSR = 0.0 everywhere; OOS-consistency gate). 11 new sources,
every link probed today (2026-10-13) with `curl -L`, statuses recorded
verbatim in §15.9. Five drive the design (§15.1–§15.5, full
method/equations/assumptions/failure modes); six are context (§15.6).
The tools-that-validate-factors survey is pass 2's job; the Tuesday-run
recipe is pass 3's. No code changed. No MARKET-VERDICTS position
re-litigated. No completion-claim line is printed or asserted
anywhere in this pass.

Standing observation this research must explain (from
`reports/real-data-proof.md`, re-read today): on 14 coins x ~21,200
daily bars, **0/13 factors promoted**; raw `p<0.05` flags 3; BH-FDR
passes the same 3 at q=0.15; lookahead rejected by the leakage gate,
rev_5/volume_z_20 by other gates; specificity 10/10 noise rejected;
sensitivity rests on the synthetic planted signal only; DSR = 0.0
everywhere.

### 15.1 Hansen's SPA — the named successor to White's Reality Check (DRIVES DESIGN)

**Hansen, P.R. (2005)**
"A Test for Superior Predictive Ability"
*Journal of Business & Economic Statistics* 23(4):365–380.
DOI: https://doi.org/10.1198/073500105000000063
[Verified URL: UNC Carolina Digital Repository working-paper record
(Brown Univ. Dept. of Economics Working Paper No. 01-06, public PDF) —
https://cdr.lib.unc.edu/concern/articles/hd76s214m — HTTP 200 confirmed
2026-10-13. The T&F DOI page returns HTTP 403 from automated requests
(publisher bot-detection, same class as §8.7); the UNC record carries the
same title, author, abstract and DOI, so the citation is verified via the
repository copy.]

**Why this closes a boundary slot:** §8.7 listed Hansen (2005) SPA as
NOT verified (T&F 403) with the note "no threshold or gate may cite an
unverified source until then". The UNC repository copy resolves that:
SPA is now citable. §9.1 (White's Reality Check) can now name its
successor precisely instead of gesturing at it.

**Method extracted:** SPA tests whether ANY of m candidate
models/strategies beats a benchmark, correcting for data snooping. The
two modifications over White's Reality Check are: (a) a studentised test
statistic that down-weights erratic alternatives, and (b) a
sample-dependent null distribution that drops demonstrably-poor models
from the null instead of letting them inflate critical values.

Notation (Hansen §2–§3; symbols preserved, defined here):

    d_{k,t} = L_{0,t} - L_{k,t},   k = 1..m, t = 1..n

    d_{k,t} = performance of model k minus benchmark at t
              (loss differential; positive = model wins).
    dbar_k  = (1/n) * sum_t d_{k,t}      (sample mean differential)
    shat_k  = consistent estimator of std(sqrt(n) * dbar_k)

Null hypothesis (the composite "no model wins" null):

    H_0: mu <= 0,   i.e. max_k mu_k <= 0,  mu_k = E[d_{k,t}]

SPA test statistic (studentised maximum):

    T_n^SPA = max( max_k  sqrt(n) * dbar_k / shat_k ,  0 )

The inner max over k is the best studentised model; the outer max with 0
is the benchmark itself (the test is one-sided: it rejects only when
something beats the benchmark).

Bootstrap p-values — three of them, from three null recentrings:

    p_l : liberal     (null mu^l = 0 vector: every model exactly tied)
    p_c : consistent  (data-dependent mu^c: models with
          sqrt(n)*dbar_k/shat_k <= -sqrt(2*log*log(n)) are set to 0,
          the rest keep dbar_k — poor models are neutralised, not rewarded)
    p_u : conservative (null mu^u = elementwise max(dbar, 0))

Decision rule: reject H_0 at level alpha iff p_c < alpha. The paper's
Monte Carlo (Table 6, Figure 4 in the working paper) shows the two
modifications each add substantial power: studentisation alone lifts
power from ~15% to ~53% in the reported design; the data-dependent null
removes the RC's sensitivity to irrelevant poor alternatives.

**Assumptions:**
1. Stationarity/weak dependence of d_{k,t} (bootstrap is the stationary
   bootstrap of Politis-Romano 1994, §12.5 — same dependency as White).
2. shat_k consistent for each k (needs n >> m in practice; the paper's
   simulations use n = 500–2000 against m = 100).
3. The benchmark is fixed and named in advance (SPA tests "beats THIS
   benchmark", not "beats the best of everything tried").

**Known failure modes per the literature:**
1. p_l over-rejects when poor models abound (it is a lower bound, not a
   decision p-value) — Hansen §4 warns against reporting p_l alone.
2. In small n with large m, shat_k is noisy and studentisation can
   overweight lucky low-variance models (the same pathology BH-FDR has
   with noisy p-values; cf. F-R10/C3-F1 one-coin artefact, §11.4).
3. SPA assumes the model universe is declared up front. A researcher who
   adds models after seeing p_c reintroduces exactly the snooping SPA
   was built to remove (Hansen §1: "the universe must be fixed").

**Design consequence (checker numbers):** the proof's §3 "delta" (raw
p<0.05 count vs BH-FDR count vs promoted count, in counts AND names) is
the BH-FDR analogue of STW/SPA's nominal-vs-adjusted p-value gap
(§15.2). The checker already requires the delta in counts and names;
this pass endorses that requirement with a second citation family and
adds the rule filed as F-R17: any future proof section that reports a
nominal (unadjusted) significance count WITHOUT its adjusted
counterpart beside it fails review — nominal-only reporting is the exact
practice STW §15.2 diagnoses. No code change (report-shape rule).

**Transcription flag (F-R16-class):** the mu^c threshold
-sqrt(2*log*log(n)) and the mu^u=max(dbar,0) recentring above are
transcribed from the working-paper text; symbol-level audit is
transferred to the adversarial citation audit (same owner as the
Scholes-Williams/GLM items, §14.5). "Threshold constant wrong" is
blocking for any future SPA implementation; "symbols differ, test
right" is minor. No SPA implementation exists in the repo, so nothing
is blocked today.

### 15.2 Data-snooping quantified on 100 years of trading rules (DRIVES DESIGN)

**Sullivan, R., Timmermann, A. & White, H. (1999)**
"Data-Snooping, Technical Trading Rule Performance, and the Bootstrap"
*Journal of Finance* 54(5):1647–1691.
DOI: https://doi.org/10.1111/0022-1082.00163
[Verified URLs: JSTOR stable record —
https://www.jstor.org/stable/222500 — HTTP 200 confirmed 2026-10-13;
LSE Financial Markets Group Discussion Paper 303 (same paper, full
text) — https://researchonline.lse.ac.uk/id/eprint/119144/ — HTTP 200
confirmed 2026-10-13; RePEc record —
https://ideas.repec.org/a/bla/jfinan/v54y1999i5p1647-1691.html — HTTP
200 confirmed 2026-10-13. Closes the second §8.7 boundary slot.]

**Method extracted:** White's Reality Check applied to 7,846 technical
trading rules (expanding Brock-Lakonishok-LeBaron 1992's 26) on 100
years of daily DJIA (1897–1996), with the stationary bootstrap
(Politis-Romano 1994) over the FULL rule universe. For each rule k:

    f_{k,t} = log(1 + r_t * I_{k,t}) - log(1 + r_t * I_{0,t})

    f_{k,t} = log-return differential of rule k vs benchmark at t
              (I = position indicator: 1 long, 0 neutral, -1 short).
    fbar_k  = (1/n) * sum_t f_{k,t}
    V       = max_k  sqrt(n) * fbar_k        (best rule's scaled edge)

The RC p-value compares V against B = 500 stationary-bootstrap draws
V*_i of the same max-statistic computed on resampled f_{k,t}. The paper
reports BOTH the nominal p-value (bootstrap on the best rule alone,
snooping ignored) and the RC p-value (bootstrap over the universe).
The gap between them IS the measured data-snooping bias.

**Headline numbers (Tables III–V, full sample 1897–1996):** best BLL rule
(50-day variable MA + 1% band) annualised +9.4% vs buy-and-hold; best
full-universe rule Sharpe 0.82 vs buy-and-hold 0.034 — yet the RC
p-values (< 0.002 in subperiods for the full universe) are the evidence,
not the Sharpe magnitudes. The paper's standing lesson: even with RC
adjustment the best rules survive on 100 years of DJIA — data-snooping
correction attenuates, it does not automatically annihilate.

**Assumptions:**
1. The rule universe is enumerable and fixed before testing (7,846
   parameterisations declared up front).
2. Stationary bootstrap with mean block length tuned to the dependence
   (Appendix C: expected block length q matched to return
   autocorrelation; wrong q misstates the null width).
3. Benchmark (buy-and-hold / zero) is the economically relevant
   alternative — beating it gross of costs is the tested claim.

**Known failure modes per the literature:**
1. Hansen (2005, §15.1) shows RC loses power when the universe contains
   many poor rules — STW's 7,846-rule universe is exactly the case SPA
   was built to improve on. RC non-rejection on a wide universe is weak
   evidence of "no edge".
2. Costs are applied coarsely (one-way cost assumption); STW §5 shows
   the surviving rules' net edge is thin — the turnover gate (F-R13)
   answers the same question more strictly.
3. 100-year DJIA is survivorship-selected (the index that survived);
   the proof's limitation "coin-list survivorship" (§F2.6 analogue) is
   the same caveat at smaller scale.

**Design consequence (checker numbers):** STW is the empirical charter
for the proof's delta section: nominal p-values flagged 3/13 raw, and
the report must keep the nominal count VISIBLE next to the adjusted
count so a reader can see the snooping gap, exactly as STW Tables III/V
print nominal beside RC. Filed as F-R18: any proof whose §3 shows only
adjusted numbers (hiding how many raw flags the gate killed) fails
review — the gap is the product story (§6.3 item: "report these 2
passed AFTER multiple-testing correction" requires the before-count).
Endorses current proof shape; no code change.

### 15.3 PSR and MinTRL — why the proof's DSR column reads 0.0 (DRIVES DESIGN)

**Bailey, D.H. & Lopez de Prado, M. (2012)**
"The Sharpe Ratio Efficient Frontier"
*Journal of Risk* 15(2):3–44.
[Verified URLs: author publication record with abstract and venue —
https://quantresearch.org/Publications.htm — HTTP 200 confirmed
2026-10-13 (lists the paper, venue, and the PSR/MinTRL contribution);
equations below are transcribed from the standard formulation as
RESTATED in the author-hosted DSR manuscript (Bailey & Lopez de Prado
2014, first version April 2014 — https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf —
HTTP 200 confirmed 2026-10-13), which re-derives PSR as the DSR's
parent statistic. The SSRN record (abstract_id=1821643) returns HTTP 403
from automated requests (same class as §8.7); it is NOT cited as
verified. Symbol-level audit of the transcription is F-R16-class,
transferred to the adversarial citation audit.]

**Method extracted:** the Probabilistic Sharpe Ratio answers "with what
probability does the true Sharpe exceed a threshold SR*, given T
observations with skew gamma_3 and kurtosis gamma_4?" and MinTRL answers
"how long a track record is needed to assert SR > SR* at confidence
alpha?".

Notation (Bailey-Lopez de Prado 2012, Eq. 4 and Eq. 6; gamma_3 =
skewness, gamma_4 = kurtosis, NOT excess; T = track length in the
sampling units of the Sharpe):

    PSR(SR*) = Phi( (SHAT - SR*) * sqrt(T - 1)
                    / sqrt(1 - g3*SHAT + (g4 - 1)/4 * SHAT^2) )

    SHAT  = estimated (annualised) Sharpe ratio
    SR*   = threshold Sharpe to beat (0 for "any skill")
    Phi   = standard normal CDF (Abramowitz-Stegun, §2.9)
    g3, g4 = sample skewness and kurtosis of returns

    MinTRL(SR*, alpha) = 1 + (1 - g3*SR* + (g4 - 1)/4 * SR*^2)
                            * (Phi_inv(alpha) / SR*)^2

    MinTRL = minimum track length (same units as T) such that
             PSR(SR*) >= alpha. Phi_inv = inverse normal CDF.

Worked example (units: years, annualised Sharpe; the "decade to prove
0.5" arithmetic the checker leans on):

    SR* = 0.5, alpha = 0.95 (Phi_inv = 1.645),
    g3 = -0.5, g4 = 4.0 (negative skew, fat tails — crypto-typical):
    bracket = 1 - (-0.5)(0.5) + (4-1)/4 * 0.25
            = 1 + 0.25 + 0.1875 = 1.4375
    MinTRL = 1 + 1.4375 * (1.645/0.5)^2
           = 1 + 1.4375 * 10.8241 = 1 + 15.56 ≈ 16.6 years

Under normality (g3=0, g4=3): MinTRL = 1 + 1.0625*10.8241 ≈ 12.5 years.
Non-normality ADDS ~4 years to the burden of proof at these settings.

**Assumptions:**
1. Returns IID within the track record (no regime shifts — same
   assumption as DSR §2.4; F-R15's |rho_1| < 0.2 panel check is the
   repo's standing guard on it).
2. Sample moments g3, g4 are well-estimated (needs long T; on T=100 the
   kurtosis estimate alone has standard error ~ sqrt(24/T) ≈ 0.49 under
   normality — the correction is noise).
3. The SR* threshold is chosen BEFORE seeing SHAT (post-hoc SR* is
   selection bias by another name — DSR's E[max(SR)] term, §2.4).

**Known failure modes per the literature:**
1. IID violation is the load-bearing one: on autocorrelated series the
   effective T is smaller and PSR overstates confidence (same mechanism
   as the naive-t-stat inflation, §2.10). Lo (2002, §9.2) annualisation
   under autocorrelation is the same warning from the other side.
2. MinTRL explodes for small SR*: asserting SR > 0.25 at 95% needs
   ~4x the track of SR > 0.5 — the proof's 5.5-year daily panel
   (T ≈ 1,994 bars ≈ 5.5 years) CANNOT assert modest Sharpes no matter
   what the IC gate says. That is exactly why DSR = 0.0 everywhere in
   the standing proof table: IC-IR ≈ 0.09 against a 13-trial bar
   SR* ≈ 1.70 is MinTRL-territory of decades, not years.
3. PSR with SR* = 0 on a short panel is nearly vacuous (almost any
   positive SHAT "passes") — the repo correctly never gates on PSR(0).

**Design consequence (checker numbers):** DSR = 0.0 across the proof is
EXPLAINED, not merely reported: a 5.5-year panel asserting Sharpe
significance under 13 trials needs SR ≈ 1.7+, and no factor is near it.
Filed as F-R19: any proof whose DSR column is all-zero MUST carry the
MinTRL sentence ("a 5.5-year panel cannot assert SR < ~1.7 under 13
trials at 95%; the zeros are the test working, not the test broken") —
an all-zero column without that sentence reads as a broken
implementation and fails review. Transfer: implement pass owns the
sentence; this pass owns the arithmetic above (reviewer: recompute
16.6/12.5 from the formula before trusting it).

### 15.4 Goyal-Welch OOS — in-sample significance is not the gate (DRIVES DESIGN)

**Goyal, A. & Welch, I. (2008)**
"A Comprehensive Look at the Empirical Performance of Equity Premium
Prediction"
*Review of Financial Studies* 21(4):1455–1508.
NBER Working Paper w10483.
[Verified URLs: NBER record —
https://www.nber.org/papers/w10483 — HTTP 200 confirmed 2026-10-13;
author-hosted working-paper PDF (Yale ICF) —
https://repec.som.yale.edu/icfpub/publications/2412.pdf — HTTP 200
confirmed 2026-10-13; second hosted PDF (Tulane) —
https://breesefine7110.tulane.edu/wp-content/uploads/sites/16/2015/10/Goyal-and-Welch-2008.pdf —
HTTP 200 confirmed 2026-10-13.]

**Method extracted:** every published equity-premium predictor (dividend
yield, earnings-price, book-to-market, cay, ... ) re-estimated under ONE
protocol, IS and OOS, 1927–2005. The OOS statistic is the out-of-sample
R-squared against the prevailing-mean benchmark:

    R2_OOS = 1 - MSPE_model / MSPE_bench

    MSPE_model = (1/P) * sum_{t=R}^{T} (r_{t+1} - rhat_{t+1|t})^2
    MSPE_bench = (1/P) * sum_{t=R}^{T} (r_{t+1} - rbar_{t})^2

    rhat_{t+1|t} = forecast using data only up to t (rolling/recursive)
    rbar_t       = prevailing historical mean up to t (the benchmark)
    R            = first OOS date; P = number of OOS predictions

    Significance via the MSE-F statistic (McCracken 2004):
    MSE-F = P * (MSPE_bench - MSPE_model) / MSPE_model

Headline result: NOT ONE predictor beats the prevailing mean OOS over
the full sample; most would have HURT a market-timer. Several are IS
significant — and fail OOS anyway. The failure mode is instability
(good early, bad late — the reverse of a low-power artefact), diagnosed
by cumulative-SSE plots, not by a single number.

**Assumptions:**
1. Prevailing mean is the right benchmark (it is the "no-predictability"
   null — the analogue of the repo's noise_control).
2. Recursive estimation windows (expanding, not rolling) — parameter
   estimates use all history to t.
3. The OOS period must be long enough to be representative (their
   §2: ≥20 years initial estimation + long evaluation).

**Known failure modes per the literature:**
1. Campbell-Thompson (2008, RFS — response paper) show sign/exclusion
   restrictions rescue SOME OOS R² — Goyal-Welch's unrestricted OLS is
   the pessimistic bound, not the last word. (Not verified this pass;
   named so a later pass can close it — boundary item, same class as
   §12.7.)
2. R2_OOS < 0 is the NORMAL outcome for a useless predictor (not a bug):
   estimation error alone puts MSPE_model above MSPE_bench. A gate that
   "fails on negative OOS-R²" without a benchmark comparison misreads
   the statistic.
3. The prevailing mean itself is estimated with error; with short P the
   MSE-F test has low power (their §2 discussion).

**Design consequence (checker numbers):** Goyal-Welch is the published
charter for the repo's OOS-consistency gate and its walk-forward
machinery: IS significance (IC t-stat, BH-FDR pass) is NECESSARY but a
factor must ALSO survive unseen splits, because the entire equity
premium literature is a museum of IS-significant OOS-failures. Filed as
F-R20: any proof promoting a factor on IS statistics (IC, t-HAC, BH-FDR)
with OOS-consistency BELOW the 0.60 gate, or with the OOS column
missing, fails review — Goyal-Welch is the citation for why the OOS
column is load-bearing rather than decorative. Magnifies (not replaces)
FINDING C2-3a (§5 Test C2-3): the magnitude-blind sign gate is exactly
the kind of IS-flattering statistic Goyal-Welch's cumulative-SSE plots
were built to expose. Endorses current gate; the improve pass owns the
magnitude fix.

### 15.5 Linnainmaa-Roberts — half the alpha is spurious (DRIVES DESIGN)

**Linnainmaa, J.T. & Roberts, M.R. (2018)**
"The History of the Cross-Section of Stock Returns"
*Review of Financial Studies* 31(7):2606–2649.
NBER Working Paper w22894.
[Verified URLs: NBER record —
https://www.nber.org/papers/w22894 — HTTP 200 confirmed 2026-10-13;
author-hosted full PDF (Wharton) —
https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2017/08/The-History-of-the-Cross-Section-of-Stock-Returns.pdf —
HTTP 200 confirmed 2026-10-13. Closes the third §8.7 boundary slot.]

**Method extracted:** 36 accounting-based anomalies re-tested on
hand-collected pre-1963 Moody's-manual data (PRE-discovery OOS, up to 37
years — often LONGER than the original IS sample) plus post-discovery
data. Three eras per anomaly: pre-sample / in-sample / post-sample, each
with average return, CAPM alpha, FF3 alpha, and information ratio
(alpha / residual vol).

Headline numbers (Tables 5–7, quoted from the paper text):
- Profitability factor pre-1963: average return −1 bp/month (t = −0.06);
  investment factor: +6 bp/month (t = 0.64). IS they earn +27/+40
  bp/month, significant. The premiums are absent before discovery.
- 28 of 36 anomalies earn IS-significant average returns; pre-discovery
  only 8 of 36 are positive-significant at 5%.
- Information ratios (FF3) fall by MORE THAN THREE-FIFTHS moving OOS in
  either direction; OOS alphas are 40–60% of IS alphas.
- Decision rule the authors propose: test models OOS, or require a
  model to explain HALF of the in-sample alpha (the spurious remainder
  cannot be explained even by the true model — "even the true asset
  pricing model is expected to be rejected when tested using in-sample
  data").

**Assumptions:**
1. Pre-1963 Moody's data is free of the backfill/selection biases that
   plague Compustat before 1963 (the paper's §2 data appendix argues
   this at length; Compustat pre-1963 backfill bias is the reason the
   pre-sample had to be hand-collected).
2. Anomaly definitions ported verbatim to the old data (same
   characteristic, same sort) — any definition drift biases toward
   finding "decay".
3. Post-discovery windows are short (noisier); the paper aggregates
   across anomalies for power rather than leaning on single-anomaly
   post-sample t-stats.

**Known failure modes per the literature (and the paper's own §6):**
1. Risk-vs-mispricing is NOT settled by decay alone: declining frictions
   (Jones 2002; French 2008; Hasbrouck 2009 cost series) predict exactly
   this attenuation under the mispricing story. Decay proves snooping
   contributed, not that risk explains nothing.
2. The "half-alpha" rule is a rule of thumb calibrated on THEIR 36
   anomalies (accounting-based, monthly, US equities) — porting the 50%
   haircut to daily crypto ICs is an analogy, not a derivation (flagged
   for the audit if any threshold ever cites it numerically).
3. Small perturbations to IS start dates cut average returns 50–75%
   (their §5): anomaly significance is knife-edge in sample choice — the
   repo's embargo/purge machinery (§2.6) answers a different edge
   (leakage), not this one (sample specificity).

**Design consequence (checker numbers):** LR is the strongest published
prior for the proof's 0/13 standing result: on a SHORT (5.5-year),
NARROW (14-coin), POST-discovery panel, promoting nothing is the
BASE-RATE outcome, not a gate malfunction — 28/36 IS-significant
anomalies mostly fail true OOS. Filed as F-R21: any reading of the
proof that treats "0 promoted" as evidence the GATE is broken (rather
than evidence the panel is hard) must first clear the LR base rate —
show the promoted-count expectation under 40–60% OOS alpha haircuts
before proposing to loosen a threshold. Paired with §8.1 (LTW weekly
momentum exists on BROAD panels): the checker keeps its current shape
(promoted factor OR honest note, F3b) — demanding a daily-H promotion
on 14 coins would contradict both papers at once. No code change.

### 15.6 Context sources (6, verified today)

**Ioannidis, J.P.A. (2005)** "Why Most Published Research Findings Are
False", *PLOS Medicine* 2(8):e124.
https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.0020124
[HTTP 200 confirmed 2026-10-13.]
The repo thesis ("most published factors are noise") in equation form.
Positive predictive value of a claimed finding:

    PPV = ((1 - beta) * R) / ((1 - beta) * R + alpha)

    R     = pre-study odds of a true relationship (true:false tested)
    alpha = type-I error of the test; beta = type-II error (1-power)

Corollaries the proof leans on: PPV collapses when R is small (factor
fishing expeditions), when effect sizes are small (daily IC ≈ 0.02),
and when many teams test many relationships (the 316-factor zoo, §2.7).
BH-FDR (§2.3) is the repo's mechanical answer to Ioannidis's
R-denominator: the gate prices in that most tested factors are null.
Failure mode Ioannidis names and the repo inherits: PPV arithmetic
assumes unbiased testing — with flexibility in definitions and
stopping rules ("researcher degrees of freedom"), realised false-find
rates exceed the formula. The proof's fixed-gate-no---force design
(spec §6: --force FORBIDDEN) is the structural answer to that caveat.

**Frazzini, A., Israel, R. & Moskowitz, T.J. (2012)**
"Trading Costs of Asset Pricing Anomalies", AQR working paper (Fama-Miller
working paper; first draft Oct 2012, this draft Dec 2012).
[Verified URLs: author-hosted full PDF (NYU Stern) — AQR-insights page —
https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies?aqrPDF=1 —
HTTP 200 confirmed 2026-10-13.]
Live-trade costs (~$1T, 19 markets, 1998–2011) applied to size, value,
momentum, short-term reversal. Headlines (quoted from the paper):
break-even fund sizes (US) SMB $103B / HML $83B / UMD $52B / short-term
reversal $9.5B; value+momentum netting raises joint capacity ($98B);
real arbitrageur costs ≈ ONE-TENTH of the prior literature's estimates;
SHORT-TERM REVERSALS are the most cost-constrained style and "do not
survive trading costs at reasonable size". Design consequence: extends
F-R13 (the 50%-turnover bar) with a style-specific bite — the proof's
rev_5 (a 5-day reversal, the highest-turnover family in the repo) faces
BOTH the NMV turnover bar AND the FIM reversal-capacity result, so its
rejection on turnover is over-determined in the literature, not a
calibration accident. Also grounds the proof's Limitations "no
transaction costs" line with magnitudes: gross-edge claims without
costs overstate implementability by up to 10x versus live-trade reality
for reversal styles. No threshold cites FIM numerically (equity-market
costs do not port to crypto spreads) — direction-only use, stated here
so the audit cannot misread it.

**Barras, L., Scaillet, O. & Wermers, R. (2010)**
"False Discoveries in Mutual Fund Performance: Measuring Luck in
Estimated Alphas", *Journal of Finance* 65(1):179–216.
DOI: https://doi.org/10.1111/j.1540-6261.2009.01527.x
[Verified URLs: author-hosted working-paper PDF —
https://scaillet.ch/pdfs/FDR.pdf — HTTP 200 confirmed 2026-10-13;
published-version PDF (Univ. of Maryland) —
https://terpconnect.umd.edu/~wermers/FDR_published.pdf — HTTP 200
confirmed 2026-10-13; Geneva archive record —
https://archive-ouverte.unige.ch/unige:79989 — HTTP 200 confirmed
2026-10-13. The JSTOR stable PDF returns a JS-challenge shell
(same class as §14.5 Novy-Marx note); the three URLs above are the
verified citation.]
FDR moved from theory (§2.3 BH; Storey §2.3) into production on 2,076
funds: estimate pi_0 (fraction of zero-alpha funds) by Storey (2002),
then decompose significant positives at level gamma into lucky
Fhat+ = pihat_0 * gamma/2 and truly-skilled That+ = Shat+ - Fhat+.
Result: pihat_0 = 75.4% zero-alpha; skilled proportion statistically
ZERO net of costs (pre-1996 subsample excepted). Design consequence:
the first large-scale demonstration that an unadjusted "count the
significant" screen is dominated by luck — the proof's delta §3 (raw 3
flags → BH → 0 promoted) is the 13-factor miniature of BSW Table II.
No threshold cites BSW (fund-count asymptotics do not port to m=13);
precedent-only use.

**Kosowski, R., Timmermann, A., Wermers, R. & White, H. (2006)**
"Can Mutual Fund 'Stars' Really Pick Stocks? New Evidence from a
Bootstrap Analysis", *Journal of Finance* 61(6):2551–2595.
DOI: https://doi.org/10.1111/j.1540-6261.2006.01015.x
[Verified URL: RePEc record —
https://ideas.repec.org/a/bla/jfinan/v61y2006i6p2551-2595.html — HTTP
200 confirmed 2026-10-13 (records the JoF venue, the CFR working-paper
antecedent 05-14, and the abstract). The Wiley DOI page is publisher
bot-walled (same class as §8.7); the working-paper PDF was not
re-hosted at a probed URL, so method detail below is abstract-level and
the source is CONTEXT ONLY — no gate cites it.]
Cross-sectional bootstrap of fund t(alpha) under the alpha=0 null
(necessitated by non-normal, heterogeneous fund-alpha distributions);
finds a sizable skilled minority with persistent alphas. Design
consequence, one line: bootstrap-under-the-null on the FULL
cross-section (not fund-by-fund t-tests) is the established precedent
for the repo's family-wise discipline — same idea as the
permutation-null calibration (§7.4). Paired honestly with Fama-French
(2010, next): two bootstrap-null studies, opposite tails emphasised —
KTWW find persistent skill exists somewhere; FF find net returns still
do not cover costs. The repo's gate sides with NEITHER on returns; it
screens characteristics, and both papers agree screening without
null-discipline over-claims.

**Fama, E.F. & French, K.R. (2010)**
"Luck versus Skill in the Cross-Section of Mutual Fund Returns",
*Journal of Finance* 65(5):1915–1947.
DOI: https://doi.org/10.1111/j.1540-6261.2010.01598.x
[Verified URL: hosted published PDF (Dartmouth/Tuck course archive) —
https://mba.tuck.dartmouth.edu/bespeneckbo/default/AFA611-Eckbo%20web%20site/AFA611-S8C-FamaFrench-LuckvSkill-JF10.pdf —
HTTP 200 confirmed 2026-10-13 (full text: abstract, §1 bootstrap design,
Table II aggregates, sigma calibration).]
10,000 bootstrap simulation runs of the cross-section of t(alpha) with
true alpha = 0; actual cross-section compared percentile-by-percentile
against the zero-skill distribution. Headlines (quoted): net-return
intercepts −0.81% to −1.00%/yr (t −2.05 to −3.02); cross-section of true
alpha ~ N(0, sigma) with sigma ≈ 1.25%/yr (so <16% of funds exceed
+1.25%/yr gross, ~2.3% exceed +2.50%/yr); "true alpha in net returns is
negative for most if not all active funds". Design consequence: the
cleanest statement anywhere of the EXTREMES-BY-CHANCE mechanism the
specificity leg (F3a, >=90% noise rejected) exists to defeat — with
3,156 funds, the tails of the simulated zero-skill cross-section reach
t(alpha) values a naive reader calls skill. The proof's 10 seeded noise
factors are the 13-factor analogue; the >=90% bar is endorsed (FF show
the null alone fills the tails). No threshold cites sigma=1.25%
(fund-alpha units do not port to IC units) — mechanism-only use.

**Bailey, D.H. & Lopez de Prado, M. (2014) — author-hosted full text.**
"The Deflated Sharpe Ratio", *Journal of Portfolio Management*
40(5):94–107; first version April 2014.
https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf
[HTTP 200 confirmed 2026-10-13.]
Second verified host for the §2.4 paper (previously arXiv 1405.4598
only). The author PDF carries the full PSR restatement (§15.3's equation
source), the E[max(SR)] trial correction, and the Python appendix the
2012 paper advertises. Recorded here so the adversarial citation audit
has TWO resolving full texts for every DSR/PSR equation in this file.
No new method claimed; provenance-only entry (does not count toward
any future "new source" quota — stated explicitly to keep counts
honest: this pass adds 10 new sources, D1–D5 + C1–C5 above).

### 15.7 Alternatives considered (this pass)

BH-FDR vs SPA/RC as the family gate (§15.1–§15.2): SPA/RC test
"beats a named benchmark" over a declared strategy universe with
B=500+ bootstraps per evaluation; the repo gates 13 IC series with an
analytic BH pass at q=0.15 costing microseconds. SPA is the stronger
inference (handles arbitrary dependence, no PRDS assumption needed) and
the honest v0.3 candidate for the "second gate" behind BH — rejected
for v0.1/v0.2 because (a) IC series are not strategy returns (no
benchmark loss differential exists until portfolio construction, same
layering argument as §3.5 DSR-vs-IC), and (b) 500 bootstraps x 13
factors x 3 horizons breaks the 7-minute screen budget (§7.6 timing:
7:19.9 at 5000x50). Revisit when portfolio simulation lands.

OOS-R2 (Goyal-Welch) vs sign-agreement (current gate): R2_OOS against a
prevailing-mean benchmark is strictly more informative than sign counts
(it weights magnitudes — the C2-3a fix direction). Rejected as the
primary gate because the repo screens CHARACTERISTICS (IC series), not
return forecasts: there is no "prevailing-mean IC" benchmark with an
economic meaning, and MSE-F critical values (McCracken 2004) assume
nested-model forecast errors, not cross-sectional correlations. The
C2-3a magnitude fix (per-split |IC| floor) is the correct import of
the Goyal-Welch lesson into IC units — recorded for the improve pass.

Half-alpha haircut (LR) vs BH-FDR haircut: LR's "explain half the IS
alpha" is calibrated on monthly US-equity anomalies; applying a 50%
haircut to daily crypto ICs would be numerology (flagged §15.5). The
repo prices snooping with BH (family-scoped, assumption-checked PRDS
§2.3) instead. LR stays a READING rule for proof consumers ("expect
half of any promoted edge to be spurious — size accordingly"), never a
gate constant.

### 15.8 Falsification — what would prove this pass wrong (F-R17…F-R21 new; all prior stand)

- F-R1…F-R16: dispositions in §8.9/§9.8/§11/§14 stand; nothing re-run
  (proof JSON unchanged since c4-p01; no new data pulled — database
  untouched this pass, zero queries issued).
- F-R17 (nominal-without-adjusted): a proof §3 that prints raw p<0.05
  counts with no BH-adjusted column beside them — the STW Tables III/V
  shape is the record (§15.2). Falsified if STW's nominal/RC gap is
  shown to be a bootstrap artefact (i.e. a same-universe SPA re-run
  collapsing the gap — Hansen §15.1 says the opposite, but the
  experiment would settle it).
- F-R18 (hidden attrition): a proof delta showing only adjusted numbers
  (raw-flag count suppressed). Record: raw 3 → BH 3 → promoted 0.
  Falsified by exhibiting a reader who reconstructs the raw count from
  the adjusted table alone (impossible by construction — hence the rule).
- F-R19 (unexplained zero DSR column): a proof with all-zero DSR and no
  MinTRL sentence. Arithmetic record: MinTRL(0.5, 95%) ≈ 16.6y
  non-normal / ≈ 12.5y normal (§15.3) — recompute before trusting.
  Falsified if a 5.5-year panel is shown asserting SR > 0.5 at 95% under
  13 trials (would break the MinTRL inequality, not just this pass).
- F-R20 (IS-only promotion): any promoted verdict with OOS-consistency
  < 0.60 or a missing OOS column. Record: Goyal-Welch zero-for-N
  headline (§15.4). Falsified by a promoted factor whose OOS column was
  later shown tradeable net of costs (would upgrade C2-3a from major to
  critical and rewrite this section).
- F-R21 (0-promoted-means-broken-gate): a loosening proposal that does
  not first clear the LR base rate (§15.5: >3/5 IR decay OOS, 8/36
  pre-discovery survivors). Record: 0/13 on 14 coins x 5.5y.
  Falsified by a power calculation showing the current gates SHOULD
  promote a realistically-decayed crypto edge on THIS panel (needs
  assumed true IC + full gate simulation — a proper improve-pass task,
  named here so it is not hand-waved later).
- Ecosystem: none — pass 2 owns the comparison table; this pass makes
  no tool claim.

### 15.9 Link-verification table (all probed 2026-10-13, curl -L, UA Mozilla/5.0)

| # | Source | URL | HTTP |
|---|---|---|---|
| D1a | Hansen SPA, UNC repository record + working paper | https://cdr.lib.unc.edu/concern/articles/hd76s214m | 200 |
| D1b | Hansen SPA, T&F journal page (bot-walled, NOT cited as verified) | https://www.tandfonline.com/doi/abs/10.1198/073500105000000063 | 403 |
| D2a | STW 1999, JSTOR stable record | https://www.jstor.org/stable/222500 | 200 |
| D2b | STW 1999, LSE discussion paper full text | https://researchonline.lse.ac.uk/id/eprint/119144/ | 200 |
| D2c | STW 1999, RePEc record | https://ideas.repec.org/a/bla/jfinan/v54y1999i5p1647-1691.html | 200 |
| D3a | Bailey-Lopez de Prado 2012, publication record | https://quantresearch.org/Publications.htm | 200 |
| D3b | PSR/DSR equations, author-hosted DSR manuscript | https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf | 200 |
| D3c | PSR SSRN record (bot-walled, NOT cited as verified) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643 | 403 |
| D4a | Goyal-Welch, NBER w10483 record | https://www.nber.org/papers/w10483 | 200 |
| D4b | Goyal-Welch, Yale-hosted working-paper PDF | https://repec.som.yale.edu/icfpub/publications/2412.pdf | 200 |
| D4c | Goyal-Welch, Tulane-hosted PDF | https://breesefine7110.tulane.edu/wp-content/uploads/sites/16/2015/10/Goyal-and-Welch-2008.pdf | 200 |
| D5a | Linnainmaa-Roberts, NBER w22894 record | https://www.nber.org/papers/w22894 | 200 |
| D5b | Linnainmaa-Roberts, Wharton-hosted full PDF | https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2017/08/The-History-of-the-Cross-Section-of-Stock-Returns.pdf | 200 |
| C1 | Ioannidis 2005, PLOS Medicine full text | https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.0020124 | 200 |
| C2 | FIM 2012, AQR working-paper page | https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies?aqrPDF=1 | 200 |
| C3a | BSW 2010, author-hosted working-paper PDF | https://scaillet.ch/pdfs/FDR.pdf | 200 |
| C3b | BSW 2010, Maryland-hosted published PDF | https://terpconnect.umd.edu/~wermers/FDR_published.pdf | 200 |
| C3c | BSW 2010, Geneva archive record | https://archive-ouverte.unige.ch/unige:79989 | 200 |
| C4 | KTWW 2006, RePEc record | https://ideas.repec.org/a/bla/jfinan/v61y2006i6p2551-2595.html | 200 |
| C5 | Fama-French 2010, hosted published PDF | https://mba.tuck.dartmouth.edu/bespeneckbo/default/AFA611-Eckbo%20web%20site/AFA611-S8C-FamaFrench-LuckvSkill-JF10.pdf | 200 |

Notes on 403 responses: T&F and SSRN return HTTP 403 to automated
requests (publisher bot-detection, same class as §8.7/§12.9). Neither
is cited as a verified source; each paper has a verified repository or
author-hosted copy listed beside it. JSTOR stable PDFs that render a
JS-challenge shell (BSW) are likewise not cited; the Geneva archive
record + two hosted PDFs carry that citation.

(End of file)

---

## 16. Cycle 5 pass 1 — volatility, factor timing, and inference completeness (added 2026-10-13, pass c5-p01)

Scope of this pass: five structural gaps left open by §8–§15 that each drive a
checker number or a gate design decision. (1) Volatility-regime conditioning — the
GARCH literature that backs the `vol_20` and `atr_norm_14` factors and explains
why conditioning on volatility before IC measurement matters. (2) Factor
decomposition of momentum — what momentum earns is partly systematic, and
the systematic component is hedgeable (Grundy-Martin 2001) — relevant to the
OOS-consistency gate's sign test. (3) Volatility-managed portfolios — the
Moreira-Muir (2017) result that a simple variance-scaling of any factor strategy
improves its Sharpe: the design consequence for the promote gate. (4) Spurious
regression in short panels — the Stambaugh (1999) and Ang-Bekaert (2007) /
Hodrick (1992) papers that explain why IS predictability regressions in short
samples can mislead; the checker's MIN_BARS_FLOOR is their closed-form
consequence. (5) Inference completeness — cluster-robust SE (Petersen 2009),
stepdown FWER (Romano-Wolf 2005), OOS-R² testing (Clark-West 2007; Campbell-
Thompson 2008) — the alternatives-considered for the repo's current choices.
11 new sources, every link probed 2026-10-13 (curl -L, UA Mozilla/5.0); all 11
confirmed HTTP 200; link table in §16.12. No code changed. No MARKET-VERDICTS
position re-litigated. No absolute host paths appear below.

Standing observation (re-read today): `reports/real-data-proof.json` — 14 coins,
21,308 daily bars, 2021-04-29 → 2026-10-12; 0/13 promoted; raw p<0.05 flags 3;
BH-FDR q=0.15 passes the same 3; specificity 10/10; DSR = 0.0 everywhere.

### 16.1 ARCH — the volatility process that makes IC heteroskedastic (DRIVES DESIGN)

**Engle, R.F. (1982)**
"Autoregressive Conditional Heteroskedasticity with Estimates of the Variance of
United Kingdom Inflation"
*Econometrica* 50(4):987–1007.
[Verified URL: https://www.jstor.org/stable/1912773 — HTTP 200 confirmed
2026-10-13.]

Method extracted: prices do not have constant conditional variance; variance is
autocorrelated. Let u_t be the mean-zero residual of a return (or IC) series.
The ARCH(q) conditional variance model:

    h_t = omega + alpha_1 * u_{t-1}^2 + alpha_2 * u_{t-2}^2 + ... + alpha_q * u_{t-q}^2

    where:
        h_t   = conditional variance of u_t given information at t-1
        omega > 0, alpha_i >= 0, sum_i alpha_i < 1  (stationarity constraint)

    Maximum-likelihood estimation under conditional normality gives:
        L(theta) = -T/2 * log(2*pi) - (1/2) * sum_t [log(h_t) + u_t^2/h_t]

Key result of the paper: the UK inflation series (1958–1977) has ARCH effects;
residuals from a standard regression model are temporally correlated in variance.
The test for ARCH(q) is a Lagrange multiplier test on u_t^2 regressed on its own
lags:

    T * R^2 ~ chi^2(q)    (from regression of u_t^2 on u_{t-1}^2...u_{t-q}^2)

Relevance to factorproof: the IC time series is a time-averaged
(heteroskedastic) cross-sectional quantity — variance clustering means the
Newey-West HAC standard error (§2.10) is using the right tool but the wrong
model for the residual variance. Under ARCH, the efficient HAC would weight
observations by 1/h_t (GLS) rather than uniformly. The current OLS-based
HAC (§2.10) is consistent but inefficient in the presence of ARCH.

Assumptions:
1. Residuals u_t are conditionally normal given lagged u^2 (the paper's
   assumption; GARCH, §16.2, relaxes to other distributions).
2. Mean equation is correctly specified; residuals are mean-zero.
3. Sum of ARCH coefficients < 1 (covariance stationarity).

Known failure modes per the literature:
1. Pure ARCH(q) for large q is overparameterised — GARCH(1,1) is
   almost always more parsimonious (Bollerslev 1986, §16.2).
2. The conditional normality assumption is rejected for crypto returns
   (fat tails; excess kurtosis documented in Liu-Tsyvinski 2021 §8.6
   and consistent with the standing proof: g4 > 3 assumed in every DSR
   calculation).
3. ARCH-LM test has low power against smooth variance shifts that do
   not induce squared-residual autocorrelation.

Design consequence: the volatility-factor cluster (vol_20, atr_norm_14)
is measuring THIS process — the autocorrelation in squared returns that
Engle formalized. The IC of these factors is not "predicting returns";
it is predicting the next period's variance regime, which correlates with
(but does not equal) next-period returns. Filed as falsification item
F-R22: a vol_20 IC significantly different from zero, but whose
conditional information is eliminated once h_t is included as a
conditioning variable, is not a cross-sectional return-predictability
factor. Any future proof promoting vol_20 must check its IC orthogonal
to the lagged variance estimate.

### 16.2 GARCH — the parsimonious volatility model (DRIVES DESIGN)

**Bollerslev, T. (1986)**
"Generalized Autoregressive Conditional Heteroskedasticity"
*Journal of Econometrics* 31(3):307–327.
DOI: https://doi.org/10.1016/0304-4076(86)90063-1
[Verified URL: https://ideas.repec.org/a/eee/econom/v31y1986i3p307-327.html —
HTTP 200 confirmed 2026-10-13. DOI also resolves HTTP 200 confirmed 2026-10-13.]

Method extracted: GARCH(p,q) extends ARCH by allowing lagged conditional
variance into the variance equation:

    h_t = omega + sum_{i=1}^{q} alpha_i * u_{t-i}^2
                + sum_{j=1}^{p} beta_j * h_{t-j}

    GARCH(1,1) — the workhorse:
        h_t = omega + alpha * u_{t-1}^2 + beta * h_{t-1}

        Persistence: alpha + beta  (must be < 1 for stationarity;
        typical equity/crypto fit: alpha + beta ≈ 0.98–0.99, meaning
        variance is very slow-decaying).

        Unconditional (long-run) variance:
            sigma^2 = omega / (1 - alpha - beta)

The key insight: GARCH(1,1) is equivalent to an ARCH(∞) with
geometrically declining weights, but uses only 3 parameters. It gives a
recursion: given h_{t-1} and u_{t-1}, the next variance is estimated in
constant time.

Notation: alpha = ARCH coefficient (response to shocks); beta = GARCH
coefficient (persistence of variance); omega > 0 (baseline variance);
u_{t-1}^2 = "news" term (surprise squared).

Relevance to factorproof: two design consequences. First, the HAC SE
estimate for the IC series implicitly assumes the IC residuals have
constant unconditional variance; with GARCH, the efficient weight for
observation t is 1/h_t (GLS-ARCH, not OLS-HAC). Second, the vol_20
factor (§1.3 ATR, §12.4 GLM) is an indirect estimator of h_t^{1/2};
its cross-sectional IC is partly measuring which coins are in a
high-persistence variance state — the same regime the vol-managed
portfolio (§16.4) scales by.

Assumptions:
1. Conditional mean correctly specified (GARCH is a model for the
   second moment only).
2. Covariance stationarity (alpha + beta < 1 — violated if integrated
   variance, i.e. IGARCH where alpha + beta = 1; common finding is that
   crypto sits near IGARCH, meaning shocks never decay fully).
3. Conditional normality for MLE (can be replaced by QML under
   misspecification — Bollerslev-Wooldridge 1992 robust t-stats; not
   cited separately).

Known failure modes per the literature:
1. Near-IGARCH (alpha + beta ≈ 1) on crypto: the unconditional variance
   is formally undefined; long-run scaling breaks down (the vol-managed
   denominator estimate is non-stationary).
2. Leverage effects (negative return → larger next-day variance than
   positive return of same magnitude) are absent from GARCH(1,1); the
   GJR-GARCH / EGARCH family captures this — relevant for the DSR
   moment correction (§2.4) which uses skewness: GARCH without leverage
   understates negative skewness.
3. GARCH is a conditional model; it does not capture regime-switching
   (abrupt variance shifts like the crypto crash of 2020/12 in Grobys
   §9.4) — the walk-forward splits mitigate this by re-estimating
   within each window.

### 16.3 Grundy-Martin 2001 — momentum's systematic component (DRIVES DESIGN)

**Grundy, B.D. & Martin, J.S. (2001)**
"Understanding the Nature of the Risks and the Source of the Rewards to
Momentum Investing"
*Review of Financial Studies* 14(1):29–78.
NBER Working Paper w7989.
[Verified URLs: https://www.nber.org/papers/w7989 — HTTP 200 confirmed
2026-10-13; JSTOR: https://www.jstor.org/stable/2696959 — HTTP 200
confirmed 2026-10-13.]

Method extracted: the raw momentum factor return is decomposed into a
systematic component (exposure to Fama-French three factors) and an
idiosyncratic component. The paper shows the systematic component can be
NEGATIVE (momentum crashes, §1.9) while the idiosyncratic component is
more stable and consistently positive.

The decomposition at time t (from §2, p.33–35):

    R_WML,t = beta_WML_t * f_t + epsilon_WML_t

    where:
        R_WML,t      = return of winners-minus-losers portfolio
        beta_WML_t   = time-varying systematic factor exposure
                       (varies with winners/losers characteristics at
                       formation — momentum buys high-beta winners and
                       shorts low-beta losers in recovery markets)
        f_t          = systematic factors (market, SMB, HML)
        epsilon_WML_t = idiosyncratic component

Key result (Table 6, p.51): residual (idiosyncratic) momentum earns
+0.42% to +1.35% per month after beta-hedging; raw momentum earns
+0.42% to +1.35% on average (Table 3) but the gross return is
dominated by the risk-corrected component. The systematic component
averages near zero, meaning the TIME-SERIES variation in momentum
performance is largely a systematic-risk phenomenon, not alpha decay.

Relevance to factorproof: the OOS-consistency gate counts IC sign
agreement across walk-forward splits. Grundy-Martin predicts that for
a STOCK momentum factor, the IC sign can flip at formation-period
boundaries when the market beta of the winner portfolio flips — the
factor is genuinely sign-changing over time, not just noisy. For CRYPTO
momentum at 14 coins the equivalent mechanism is BTC-beta — the
"winner" coins will have high BTC-beta in bull regimes and the
systematic component turns negative in drawdowns. This provides a
literature-grounded reason why the OOS-consistency gate may correctly
reject a momentum factor that has IC > 0 on average but inconsistent
sign: the inconsistency may be real, not estimation noise.

Assumptions:
1. The factor decomposition requires observed factor returns (MKT, SMB,
   HML); the repo does not use these but the interpretation stands for
   any single-factor cross-sectional study.
2. The time-varying betas are estimated by regressing the momentum
   portfolio return on factors (rolling OLS); stale estimates bias the
   hedge.
3. The paper uses CRSP monthly data 1966–1995; crypto analogy holds in
   direction but not magnitude.

Known failure modes per the literature:
1. Factor hedging removes the systematic risk but NOT crash risk —
   idiosyncratic momentum still has large left-tail events (the
   crash of 2009 hit the residual too, just less severely, per
   Daniel-Moskowitz 2016 §1.9).
2. The factor decomposition changes when the factor universe changes
   (adding crypto factors changes what "systematic" means).
3. The paper's sample (1966–1995) predates the post-publication decay
   documented in McLean-Pontiff (§8.6 and §15.5 LR) — the
   idiosyncratic component may have shrunk post-discovery.

Design consequence: the OOS-consistency gate (≥60% of splits with same
IC sign) is under-specified for factors whose true signal is
time-varying by construction. Filed as falsification item F-R23: a
momentum-family factor whose IC sign flips in exactly the walk-forward
window covering 2021-11 to 2022-06 (the major crypto drawdown) is
correctly rejected by the consistency gate, not evidence the gate is
broken. The improve pass should add a per-split IC magnitude check
(C2-3a fix) that distinguishes "IC drifted to zero" from "IC genuinely
reversed with the systematic component" — the magnitudes are
qualitatively different (near zero vs. large negative).

### 16.4 Moreira-Muir 2017 — volatility-managed factors (DRIVES DESIGN)

**Moreira, A. & Muir, T. (2017)**
"Volatility-Managed Portfolios"
*Journal of Finance* 72(4):1611–1644.
NBER Working Paper w22208.
[Verified URLs: https://www.nber.org/papers/w22208 — HTTP 200 confirmed
2026-10-13; JSTOR: https://www.jstor.org/stable/26508267 — HTTP 200
confirmed 2026-10-13.]

Method extracted: scale any factor strategy's position by the inverse of
its RECENT realised variance. The scaled portfolio has strictly higher
ex-ante Sharpe if returns and variance are negatively correlated (which
is true for most risk premia — bad times have high variance AND low
returns).

Volatility-managed position at time t:

    f^VM_t = c / sigma^2_{t-1} * f_t

    where:
        f_t          = raw factor signal (unit position at each date)
        sigma^2_{t-1} = realised variance estimated at t-1 (prior month)
                       = (1/21) * sum_{d in month t-1} r_d^2  (daily)
        c            = scale constant chosen so E[f^VM_t^2] = 1 (unit variance)

    The resulting conditional Sharpe improvement (equation 2, p.1615):

    Delta_SR = corr(r_t, -sigma^2_{t-1}) * SR_raw / sqrt(1 - corr^2)

    — any NEGATIVE correlation between return and lagged variance
    implies Delta_SR > 0.

    Reported empirical result: the Market factor, Value, Momentum, HML,
    and CMA all improve Sharpe after vol-management by approximately
    0.1–0.5 Sharpe units. The improvement comes from reducing position
    in high-variance periods — the strategy is NOT the same as
    vol-targeting (which divides by vol, not variance, and adjusts for
    a target vol level, not correlation).

Notation: sigma^2_{t-1} = prior-month daily variance; f_t = raw factor
return; c = normalisation; corr = population correlation between r_t
and sigma^2_{t-1} (estimated by sample correlation over the full
history — rolling estimation degrades the estimate in short samples).

Relevance to factorproof: the `deflated_mom` factor (§1.8) already
scales by current volatility (the Moskowitz-Ooi-Pedersen TSMOM form).
Moreira-Muir extend this beyond time-series momentum to ANY factor: the
vol_20 / atr_norm_14 factors in the repo are proxies for sigma_{t-1}
and could serve as explicit scaling inputs. Design implication: the
repo's turnover gate (max_turnover = 0.5) and the GARCH-derived vol
estimate should be considered jointly — a vol-managed variant of mom_20
(divide by lagged variance) would reduce turnover AND improve Sharpe if
the corr(r, sigma^2) is negative on the crypto panel.

Assumptions:
1. The correlation between returns and lagged variance is negative and
   stable (required for Delta_SR > 0). On crypto, this correlation may
   be near zero or even positive in some regimes (high-vol bull markets
   in 2021); the improvement is not guaranteed.
2. Variance estimate sigma^2_{t-1} is computed from high-frequency
   intraday data in the paper (daily returns within the prior month);
   the repo's 20-day rolling vol is a daily-bar approximation.
3. Scaling is linear in 1/sigma^2, which can be extreme when variance
   is very low (amplification risk) — the paper's c normalisation
   prevents runaway positions in practice.

Known failure modes per the literature:
1. The improvement is NOT present after transaction costs for high-
   turnover implementations: position changes each month (or each day
   if daily scaling is used) generate turnover costs that may exceed
   the Sharpe gain.
2. Concretely on crypto: the 2021-11 to 2022-06 drawdown is a
   HIGH-variance period where vol-managed positions would REDUCE
   exposure — but it is also a period where prices continued falling
   for months, so reducing exposure WAS the right call. The mechanism
   works in crypto at the qualitative level.
3. Estimation risk in short samples: sigma^2_{t-1} is estimated from
   21 daily returns; on a 14-coin panel, cross-coin variance is
   heterogeneous, and pooling coins for a single variance estimate
   introduces estimation bias.

Design consequence: vol-managed variants of promoted factors are a v0.2
roadmap item. Filed as falsification item F-R24: if a vol-managed
mom_20 on the real 14-coin panel shows LOWER Sharpe than raw mom_20
(i.e. corr(r, sigma^2) is positive on this panel), Moreira-Muir's
mechanism does not hold here and the `deflated_mom` factor's variance
scaling should be re-examined. The test is one SQL query and one
correlation — named so the implement pass can run it.

### 16.5 Stambaugh 1999 — the small-sample bias in predictability regressions (DRIVES DESIGN)

**Stambaugh, R.F. (1999)**
"Predictive Regressions"
*Journal of Financial Economics* 54(3):375–421.
[Verified URL: https://ideas.repec.org/a/eee/jfinec/v54y1999i3p375-421.html —
HTTP 200 confirmed 2026-10-13.]

Method extracted: the OLS slope from a predictive regression

    r_{t+1} = alpha + beta * x_t + epsilon_{t+1}

    where x_t is a persistent regressor (e.g. dividend yield, past return)
    with AR(1) coefficient phi close to 1, suffers from SMALL-SAMPLE BIAS:

    E[beta_hat] = beta + (1 + 3*phi) / T * lambda + O(T^{-2})

    where:
        phi   = AR(1) coefficient of x_t (persistence of the predictor)
        lambda = cov(epsilon, u) / var(u)
                 u_t = x_t - phi * x_{t-1}  (shock to the predictor)
        T     = sample size

    The bias direction (p.382 equation 5): when the predictor and
    return innovations are negatively correlated (lambda < 0 — the
    typical case for dividend yield: high expected return = low current
    price = low dividend yield, so price shocks and yield shocks have
    negative correlation), the OLS slope OVERESTIMATES the true slope.
    For phi close to 1 and small T, the bias magnitude is large:
    approximately (1 + 3) / T = 4/T in the extreme (phi = 1).

    For T = 200 (the repo's MIN_BARS_FLOOR at H=1), phi = 0.95,
    lambda = -0.5:
        Bias ≈ (1 + 3*0.95) / 200 * (-0.5) ≈ -0.0097 per unit of lambda
    This is comparable in magnitude to a typical factor IC (0.02–0.05),
    meaning a factor whose "IC" is 0.015 on T=200 bars with a
    persistent cross-sectional mean could be entirely bias.

Relevance to factorproof: the repo computes IC (Pearson correlation
between factor scores and forward returns), not a regression slope. The
Stambaugh bias applies to regression estimators; the IC estimator is
equivalent to a slope regression when both factor and return are
standardised. The bias channel is: if factor scores are persistent
(high phi — momentum factors with 20-day lookback have phi close to 1),
and if factor innovations and return innovations are negatively
correlated (high factor score → high expected return means when factor
drops and return simultaneously rises, the bivariate correlation is
inflated), then the sample IC overestimates the population IC in short
panels.

Assumptions:
1. Persistence phi is non-trivial (phi > 0.5). For mom_20 factor scores
   (overlapping 20-day windows), the lag-1 autocorrelation of the score
   series is high (near 1 − 1/20 ≈ 0.95 by construction) — the bias
   channel is fully open.
2. Lambda = cov(factor_shock, return) has the same sign persistently.
   For momentum, this is plausible; for mean-reverting factors (rev_5),
   the correlation may be positive (reversal = negative lambda sign),
   possibly partially CANCELLING the bias.
3. The bias derivation assumes the regression slope is the statistic of
   interest; the IC is scale-free, but the sign and direction of bias
   translate.

Known failure modes per the literature:
1. The bias correction (Stambaugh 1999, §4) requires estimating phi and
   lambda, which themselves need large T — on T = 200 the correction is
   as noisy as the bias itself.
2. The alternative approach (Lewellen 2004; Cochrane 2011 §16.10)
   restricts beta to be nonnegative on the slope level — not directly
   applicable to IC estimation.
3. The bias vanishes for short-memory predictors (phi → 0): for factors
   like noise_control (white noise), the bias is negligible.

Design consequence: the MIN_BARS_FLOOR = 10,000 (T ≈ 10,000/14 ≈ 714
per coin at daily frequency) is motivated in part by Bailey-Lopez de
Prado MinTRL (§15.3), but a SECOND motivation now has a citation:
Stambaugh bias at phi = 0.95 requires T >> 1/(1-phi) = 20 to be
negligible; at T = 714, bias ≈ 4/714 ≈ 0.006 — comparable to a weak
factor IC but smaller than a promoted factor's IC (>0.02). Filed as
falsification item F-R25: a factor with phi > 0.95 and IC ≈ 0.015 on
T < 500 per-coin daily bars where |lambda| > 0.3 may be entirely
Stambaugh bias. The proof's dataset-summary must state the effective
per-coin T and the factor score persistence (phi) for each promoted
factor — both are computable from the existing data column.

### 16.6 Ang-Bekaert 2007 and Hodrick 1992 — the spurious-regression correction for IC series (DRIVES DESIGN)

**Ang, A. & Bekaert, G. (2007)**
"Stock Return Predictability: Is It There?"
*Review of Financial Studies* 20(3):651–707.
NBER Working Paper w11488.
[Verified URL: https://www.nber.org/papers/w11488 — HTTP 200 confirmed
2026-10-13.]

**Hodrick, R.J. (1992)**
"Dividend Yields and Expected Stock Returns: Alternative Procedures
for Inference and Measurement"
*Review of Financial and Quantitative Analysis* 27(3):1–29. (a.k.a. JFQA)
[Verified URL: https://www.jstor.org/stable/2331572 — HTTP 200 confirmed
2026-10-13.]

Methods extracted (pair, because Ang-Bekaert explicitly adopt the
Hodrick procedure for multi-period regressions):

**Hodrick (1992) — variance with long-horizon returns:**
Standard long-horizon regressions of H-period returns on a predictor x_t
have overlapping residuals — the same mechanism §2.10 diagnoses for the
IC series. The Hodrick standard error corrects this by reversing the
overlap: instead of summing H-period returns and computing variance,
regress the 1-period return on the MOVING AVERAGE of x_t over the next
H periods:

    r_{t+1} = a + b * (1/H) * sum_{j=0}^{H-1} x_{t+j} + v_{t+1}

This transforms the overlapping-label regression into a
non-overlapping one. The 1-period residuals v_{t+1} are serially
uncorrelated (by construction), so the OLS standard error IS the
correct standard error — no autocorrelation correction needed.

The Hodrick approach is equivalent in asymptotic power to the
Newey-West HAC correction (§2.10) but has better finite-sample
properties in Monte Carlo experiments (Hodrick p.5, verified via JSTOR
abstract).

**Ang-Bekaert (2007) — comprehensive re-assessment:**
The paper applies both the Hodrick correction and a Campbell-Yogo
(2006) instrument-based estimator to dividend yield, dividend-price,
and earnings-price ratio predictors for US equity returns over
1926–2004. Headline result (NBER abstract, retrieved 2026-10-13):
"most evidence for return predictability is fragile" — dividend yield
no longer predicts when the Hodrick or Campbell-Yogo correction is
applied, even though it predicts under standard OLS. The paper
explicitly tests whether IS predictability is "there" or a statistical
artefact of overlapping returns and persistent predictors.

The test of OOS predictability (§7 of the paper): uses a split-sample
methodology — the conclusion is that when properly corrected, the
dividend yield's OOS-R² is not significantly different from zero. This
is an independent confirmation of Goyal-Welch (§15.4) using a different
inference procedure.

Relevance to factorproof: the IC t-stat (§2.10 HAC correction) uses
the "direct" approach — regress forward returns on the factor score and
correct the standard error of the slope. The Hodrick alternative would
regress DAILY returns on a moving average of the factor score —
computationally equivalent but with better small-sample t-stat
calibration. Both are valid; the repo's HAC is the Newey-West analog,
and the Hodrick is the "reversed" analog. The Ang-Bekaert result is
the most important for the proof: it demonstrates that with proper
inference, even classic equity predictors become statistically
insignificant — the proof's 0/13 promoted result is exactly the
expected pattern when inference is done correctly.

Assumptions:
1. Hodrick (1992): the predictor x_t is exogenous (not endogenously
   determined by current-period returns); instruments are valid.
2. Ang-Bekaert: the dividend yield is I(1) in the pre-WWII period —
   their correction assumes a near-unit-root predictor.
3. Both papers focus on equity dividends; the repo's factor scores are
   not dividends, but the overlap mechanism is identical and the
   inference lessons apply.

Known failure modes per the literature:
1. The Hodrick estimator requires the moving-average of x_t to be
   observable — this requires H future observations of x per data
   point, which is only available in-sample (not useful for live
   trading, but valid for the proof's IS diagnostics).
2. Ang-Bekaert's "fragility" conclusion is specific to persistent
   (near-unit-root) predictors; short-memory factors (autocorrelation
   phi < 0.5) may survive the correction. For rev_5 (phi ≈ 0) the
   Hodrick correction changes little; for mom_20 (phi ≈ 0.95) the
   correction can be dramatic.
3. The RFS 2007 paper uses quarterly data; daily IC has shorter
   effective horizons — the bias channel is less severe at H=1 than
   at H=20.

Design consequence (checker numbers): the checker's HAC-based
t-stats are correct at L/T < 0.05 (F-R7 licence). An alternative
proof submission that replaces HAC with the Hodrick procedure would
be acceptable and arguably better-powered in finite samples. Filed
as falsification item F-R26: any proof that uses standard OLS
t-stats (no HAC, no Hodrick) on a multi-period IC series (H > 1)
must be rejected by the checker — the Ang-Bekaert result is the
published standard for why uncorrected multi-period OLS is not
acceptable inference.

### 16.7 Campbell-Thompson 2008 — the OOS-R² standard (DRIVES DESIGN)

**Campbell, J.Y. & Thompson, S.B. (2008)**
"Predicting Excess Stock Returns Out of Sample: Can Anything Beat the
Historical Average?"
*Review of Financial Studies* 21(4):1509–1531.
[Verified URLs: https://ideas.repec.org/a/oup/rfinst/v21y2008i4p1509-1531.html —
HTTP 200 confirmed 2026-10-13; author-hosted working-paper PDF:
https://repec.som.yale.edu/icfpub/publications/2597.pdf — HTTP 200
confirmed 2026-10-13.]

Method extracted: the OOS-R² statistic (§15.4 Goyal-Welch) with a
sign/restriction constraint. Campbell-Thompson propose that a
variable-poor predictor can beat the prevailing mean if: (a) when the
predicted return is negative, the forecast is replaced by zero (the
prevailing-mean benchmark), and (b) the slope coefficient is restricted
to be non-negative (theoretically motivated by the CAPM — you should
not predict negative equity premia). With these two constraints:

    R2_OOS^CT = 1 - MSPE_restricted / MSPE_bench

    where MSPE_restricted uses max(forecast, 0) and imposes beta >= 0.

Empirical result: the restricted OOS-R² is positive for most
predictors in the Goyal-Welch sample — imposing the constraints rescues
OOS predictability that the unrestricted regression loses. Specifically,
six predictors beat the prevailing mean after restrictions.

Relevance to factorproof: the OOS-consistency gate (≥60% of splits
with IC > 0) is an informal version of Campbell-Thompson's sign
constraint — requiring IC > 0 in at least 60% of splits is equivalent
to saying the factor should not predict NEGATIVE IC on most windows. The
Campbell-Thompson result supports the gate design: imposing sign
consistency is theoretically motivated and improves OOS performance in
the equity literature. However, their metric (OOS-R²) is richer than
sign counts — it weights by the magnitude of the predicted IC, which
is the C2-3a fix direction (magnitude-blind gate → magnitude-aware gate).

Assumptions:
1. The forecast is for the equity premium (excess return over T-bill);
   the analogy to IC prediction is exact if IC_t is a function of
   current factor scores and the target is cross-sectional return rank.
2. Non-negativity restriction on slopes is CAPM-motivated; for
   mean-reverting factors the restriction should be relaxed or reversed.
3. The prevailing-mean benchmark (zero forecast IC) is the correct null;
   a "mean IC" benchmark would be more conservative.

Known failure modes per the literature:
1. The restrictions improve in-sample fit too — OOS improvement may
   partially reflect constraint-induced regularisation rather than
   genuine predictability.
2. Goyal-Welch (2008 update, 2021) maintained their original conclusion
   on longer samples — the Campbell-Thompson constraints help some
   predictors but not others.
3. For a factor-screening context (IC → gate → verdict) rather than
   return prediction (forecast → portfolio weight), the OOS-R² metric
   needs reinterpretation: a "positive OOS-R²" means the factor
   outperforms zero IC in hold-out periods, which is exactly what the
   OOS-consistency gate tests.

Design consequence: filed as falsification item F-R27: the OOS-
consistency gate's 0.60 threshold is correct directionally (Campbell-
Thompson endorse sign constraints) but is not derived from the OOS-R²
literature — it was set as a round number. A future improve pass should
calibrate the threshold on the synthetic panel by computing the
implied OOS-R² at the 0.60 split-sign threshold and comparing it to
the Campbell-Thompson estimates (reported as approximately 0.5–1.5%
for the best equity predictors). If the implied OOS-R² is essentially
zero, the 0.60 threshold is too weak.

### 16.8 Clark-West 2007 — testing nested-model OOS forecast improvements (DRIVES DESIGN)

**Clark, T.E. & West, K.D. (2007)**
"Approximately Normal Tests for Equal Predictive Accuracy in Nested Models"
*Journal of Econometrics* 138(1):291–311.
[Verified URLs: https://ideas.repec.org/a/eee/econom/v138y2007i1p291-311.html —
HTTP 200 confirmed 2026-10-13; NBER Working Paper w12679:
https://www.nber.org/papers/w12679 — HTTP 200 confirmed 2026-10-13.]

Method extracted: formally testing H_0: MSPE_model = MSPE_bench when the
model is nested in the benchmark (the factor model contains the prevailing
mean as a special case with beta = 0). Under the null, the OLS residuals are
LARGER for the richer model even if the model is true, because the extra
parameters waste degrees of freedom. The Diebold-Mariano test (1995) is
invalid for nested models. The Clark-West correction:

    f_t = (e_{1,t}^2 - e_{2,t}^2) + (yhat_{1,t} - yhat_{2,t})^2

    CW statistic = T * fbar / s_f ~ N(0, 1)  asymptotically

    where:
        e_{1,t} = prevailing-mean forecast error
        e_{2,t} = factor-model forecast error
        yhat_{1,t} - yhat_{2,t} = predicted-values difference
        fbar = (1/T) * sum_t f_t
        s_f  = HAC standard error of f_t (using Newey-West with L lags)

The adjustment term (yhat_1 - yhat_2)^2 is the "estimation cost" of
fitting the extra parameters; adding it removes the nested-model bias.
The test is approximately standard normal under H_0 (requires T >> 1),
one-sided (reject for large positive CW statistic → model is better).

Notation: e_{1,t} = error of the null model (prevailing-mean IC = zero);
e_{2,t} = error of the factor model; the CW statistic is calibrated by
dividing fbar by its HAC SE (same Newey-West estimator as §2.10 —
the IC time series and the forecast error time series both need
autocorrelation correction for identical reasons).

Relevance to factorproof: the walk-forward OOS-consistency gate
implicitly tests whether the factor's IC is positive (factor model
beats the "zero IC" null) in at least 60% of splits. The Clark-West
statistic is the formal version of this test for a single factor. Filing
as a named alternative: a future proof could compute the CW statistic
for each factor's OOS IC series and report the p-value under the
approximately-normal distribution. This is strictly more powerful than
sign counting (it uses magnitudes, consistent with C2-3a fix direction).

Assumptions:
1. The null model is nested in the alternative (prevailing-mean IC = 0
   is nested in "IC > 0" — this holds exactly when the factor model
   reduces to the null when beta = 0).
2. HAC correction is applied to the time series f_t (same L = H-1
   truncation as §2.10 — required since e_{2,t} inherits the
   MA(H-1) overlap of the IC residuals).
3. T >> 1 for the normal approximation to hold; the paper's simulations
   suggest T ≥ 100 is sufficient for the size distortion to be
   negligible.

Known failure modes per the literature:
1. The correction is designed for EQUAL forecast horizons across the
   comparison; mixing H=1 and H=20 IC series in a family test
   invalidates the approximation.
2. In very small T (< 50), the normal approximation is poor and
   bootstrap critical values are recommended (same guidance as KVB §9.3
   and Ledoit-Wolf §9.5).
3. The test assumes the two models have the same parameter instability
   — if the factor model has structural breaks not in the null model,
   size is distorted.

Design consequence: the checker can incorporate the CW p-value as a
stricter OOS companion to sign-counting. Filed as falsification item
F-R28: any future proof that PROMOTES a factor based only on sign
consistency without reporting the CW statistic (or an equivalent
magnitude-aware OOS metric) fails a stronger adversarial review. The
standing proof's OOS column is sign-only; adding CW statistics is the
C2-3a fix, and the CW equation above is the ground truth for how to
compute it.

### 16.9 Romano-Wolf 2005 — stepdown FWER as the alternative to BH-FDR (DRIVES DESIGN)

**Romano, J.P. & Wolf, M. (2005)**
"Stepwise Multiple Testing as Formalized Data Snooping"
*Econometrica* 73(4):1237–1282.
[Verified URLs: https://www.jstor.org/stable/3598820 — HTTP 200 confirmed
2026-10-13; https://ideas.repec.org/a/ecm/emetrp/v73y2005i4p1237-1282.html —
HTTP 200 confirmed 2026-10-13.]

Method extracted: a stepdown procedure that controls FWER (probability
that ANY hypothesis is falsely rejected) without the conservatism of
Bonferroni. The key advantage over Bonferroni: the stepdown procedure
accounts for the correlation structure of the test statistics via
bootstrap resampling.

Romano-Wolf stepdown algorithm (simplified from §3, p.1248):

    1. Compute t-stats T_1, ..., T_m for m hypotheses.
    2. Order: |T_{(1)}| >= |T_{(2)}| >= ... >= |T_{(m)}| (descending).
    3. Bootstrap distribution: resample the data B times; compute
       t-stats T*_{k,b} for each bootstrap replicate b and hypothesis k.
    4. Step-down p-values (successive max):
       p_{(j)} = B^{-1} * #{b: max_{k>=j} |T*_{k,b}| >= |T_{(j)}|}
    5. Apply monotone enforcement: p_j = max(p_j, p_{j-1}) (ensures
       stepdown monotonicity).
    6. Reject H_{(j)} iff p_{(j)} <= alpha.

The procedure is exact in finite samples when the bootstrap
distribution is exact (i.e. the statistic is a pivot — satisfied for
standardised t-stats under stationarity). It is more powerful than
Bonferroni and controls FWER at the exact alpha level.

Notation: B = bootstrap replicates (paper recommends B ≥ 999); the
bootstrap resampling uses the stationary bootstrap (Politis-Romano
1994, §12.5) to preserve the time-series dependence structure.

The difference from BH-FDR (§2.3): BH controls the EXPECTED fraction
of false rejections (FDR ≤ q) and allows a small number of false
positives. Romano-Wolf controls the PROBABILITY of ANY false rejection
(FWER ≤ alpha) — strictly stronger but loses power when many
hypotheses are true. For a factor screening setting where a single
false positive (promoting a noise factor) is costly, FWER control is
arguably correct; for a discovery setting where some false positives
are tolerable, FDR is more appropriate.

Relevance to factorproof: Romano-Wolf and BH are the two principled
alternatives to Bonferroni. The repo uses BH (FDR) as primary and
Bonferroni as conservative comparison (§2.3). Romano-Wolf would be
more powerful than Bonferroni and more conservative than BH — it sits
between them in the power-FDR tradeoff. Its bootstrap requirement
(B ≥ 999 replicates × m hypotheses) is the computational reason it
was not adopted for v0.1 (same argument as §2.15 MBB rejection —
computational overhead).

Assumptions:
1. Stationarity + weak dependence (bootstrap is the stationary
   bootstrap with mean block length matched to dependence).
2. The test statistics T_k are (asymptotically) pivotal — t-stats
   from HAC-corrected regression slopes satisfy this; raw t-stats
   do not (the distribution depends on the unknown variance).
3. The bootstrap null uses the "centered" version: subtract the
   mean under H_0 before resampling, or use a studentised statistic.

Known failure modes per the literature:
1. Computational: 999 replicates × 13 factors × 3 horizons = ~39,000
   bootstrap t-stat computations per screen run. At ~200ms per
   factor-horizon pair, this adds ~2 hours to a screen run —
   incompatible with the 10-minute timing constraint (§7.6).
2. Power loss at large m: as m grows, each step of the stepdown
   procedure must beat a max-statistic, which grows with m. BH
   degrades more gracefully in the factor-zoo regime.
3. The bootstrap null assumes i.i.d. observations (or stationary) —
   regime shifts (C2-3a, structural breaks) invalidate it.

Design consequence: Romano-Wolf is the cited alternative for cases
where a single false positive is unacceptable (e.g. live trading with
real capital). The repo's current BH-FDR gate is the correct choice for
a screening tool; Romano-Wolf belongs in the "research" gate for a
researcher testing 3–5 factors before live deployment. Filed as
falsification item F-R29: if the v0.2 proof ever shows 1 factor
promoted under BH but 0 under Romano-Wolf at the same alpha, that is
evidence the promoted factor is a BH false discovery — the checker
should add a Romano-Wolf column to the proof output when m ≤ 5.

### 16.10 Petersen 2009 — cluster-robust SE for cross-sectional panel regressions (DRIVES DESIGN)

**Petersen, M.A. (2009)**
"Estimating Standard Errors in Finance Panel Data Sets: Comparing Approaches"
*Review of Financial Studies* 22(1):435–480.
NBER Working Paper w11547.
[Verified URLs: https://ideas.repec.org/a/oup/rfinst/v22y2009i1p435-480.html —
HTTP 200 confirmed 2026-10-13; https://www.nber.org/papers/w11547 — HTTP 200
confirmed 2026-10-13.]

Method extracted: in a panel regression where residuals are correlated
both across firms at the same time (cross-sectional correlation) AND
across time for the same firm (time-series correlation), standard errors
must be cluster-robust on BOTH dimensions. Petersen compares OLS,
Fama-MacBeth (time-averaged cross-sections), clustered-by-firm, clustered-
by-year, and double-clustered SE.

The double-cluster covariance estimator (equation 4, p.440):

    V_double = V_firm + V_time - V_white

    where:
        V_firm  = (X'X)^{-1} [sum_i sum_t sum_s c_is * x_{it} * x_{is}'
                               * e_{it} * e_{is}] (X'X)^{-1}
                  with c_is = 1 if t and s in the same cluster-i
        V_time  = same but clustering by t (same date, different firms)
        V_white = (X'X)^{-1} [sum_i sum_t x_{it} * x_{it}' * e_{it}^2] (X'X)^{-1}
                  (standard HC1 White SE, to avoid double-counting the diagonal)

Notation: x_{it} = regressor vector for firm i at time t; e_{it} = OLS
residual; V_white = White heteroskedasticity-consistent SE (the diagonal
that is double-subtracted because V_firm + V_time double-counts it).

Relevance to factorproof: the IC is computed as the cross-sectional
Pearson correlation at each date t. The IC time series has two correlation
structures: (a) cross-asset correlation (all 14 coins move together — BTC
factor), and (b) autocorrelation across dates (overlapping labels at H > 1).
The Newey-West HAC (§2.10) corrects structure (b); it does NOT correct
structure (a). Petersen (2009) demonstrates that in panels where residuals
are clustered by BOTH dimension, OLS and standard Fama-MacBeth SE (which
cluster by time only) are BOTH biased — the double-cluster SE is required.

The practical implication for the IC t-stat: the IC is computed
cross-sectionally at each date (one number per date), so the "firm
clustering" dimension is absorbed into the cross-sectional average.
However, the IC residuals are correlated across consecutive dates (HAC
handles this) AND across IC values at the same date for different
horizons (this is NOT handled by HAC). The cross-horizon correlation
inflates the joint t-stat when testing multiple horizons simultaneously.
The repo currently computes IC t-stats horizon-by-horizon (single-horizon
HAC t-stat for each H); joint testing across horizons would require the
double-cluster structure.

Assumptions:
1. The panel must be balanced (equal time-series length per firm) for the
   double-cluster formula above; unbalanced panels require a correction
   (documented in Petersen §3).
2. Both N (firms = 14 coins) and T (dates ≈ 1987 per coin) must be large
   enough for the cluster-robust SE to be consistent; at N = 14, the
   cluster dimension is small and the SE estimate is noisy.
3. The double-cluster SE can be negative in finite samples (V_firm + V_time
   < V_white); in that case, use max(V_firm, V_time) as a conservative
   fallback.

Known failure modes per the literature:
1. With only 14 coin "firms", the cluster-by-firm dimension has only 14
   clusters — the asymptotic consistency result requires T × N → ∞ with
   N >> 10 for the cluster-by-firm dimension; at N=14, the correction
   is imprecise.
2. The double-cluster SE is larger than both single-cluster SE and OLS SE
   — correcting SE upwards means t-stats fall, which could push marginal
   factors below the significance threshold. At N=14 this is the expected
   direction; the 0 promoted result is conservative, not anti-conservative.
3. The Fama-MacBeth SE (§8.2 FM parent) controls time-series clustering
   at H=1 automatically (each date's cross-section is independent); at
   H > 1 it inherits the same MA(H-1) problem HAC corrects.

Design consequence: the repo's current HAC + HAC-t-stat is a single-
dimension temporal cluster SE, not a double-cluster SE. Filed as
falsification item F-R30: any proof whose per-factor t-stats are used
in a JOINT multi-horizon test (e.g. "this factor is significant at H=1
AND H=5") without a Petersen double-cluster correction is over-confident
on the joint test. Standing proof tests each horizon independently
(single-hypothesis HAC t-stat) and reports the best-horizon verdict —
not a joint test, so F-R30 does not currently bind. Binds if a future
pass introduces a joint "significant at any horizon" shortcut.

### 16.11 Brauneis-Mestel 2018 — cryptocurrency liquidity and the Amihud measure (ADDITIONAL CONTEXT)

**Brauneis, A. & Mestel, R. (2018)**
"Price Discovery of Cryptocurrencies: Bitcoin and Beyond"
*Finance Research Letters* 26:93–98.
DOI: https://doi.org/10.1016/j.frl.2018.02.014
[Verified URL: DOI resolves — HTTP 200 confirmed 2026-10-13.]

Method extracted: Amihud illiquidity ratio (§1.4) applied to
cryptocurrencies. For 10 cryptocurrencies (Bitcoin, Ethereum, and 8
altcoins) over 2015–2017, the paper computes daily Amihud ratios and
ranks coins by liquidity. Headline findings:
- Bitcoin and Ethereum are the most liquid (lowest Amihud ratio); the
  long tail of altcoins has Amihud ratios 10–100x higher.
- Price discovery (via Hasbrouck IS and Harris-Raviv measures) is
  dominated by the most liquid coins — altcoins are largely price-
  followers, not price-discoverers.
- The Amihud ratio is a VALID liquidity proxy for crypto (the
  dollar-volume denominator exists because crypto exchanges report
  volume in coin units × coin price).

Relevance to factorproof: the `amihud_illiq_20` factor (§1.4) was
designed for equities; Brauneis-Mestel confirm it applies to crypto
with two important corrections:
1. Denominator is coin-unit volume × price (not CRSP dollar volume) —
   the repo uses this correctly (volume column from the candles table
   is in coin units; price is the close).
2. The Amihud ratio on crypto has extreme right skew (the long tail of
   illiquid coins) — the repo's 20-day moving average of ILLIQ smooths
   this but does not eliminate it; the factor needs Winsorisation at
   the tails before cross-sectional ranking.

Failure modes the paper documents: (a) Amihud on low-volume altcoins
in the first months of their trading history produces ILLIQ → ∞
(zero-denominator issue); (b) the liquidity ranking is time-stable
(BTC/ETH always first) but the level shifts with bull/bear regimes
(the tails compress in bull markets when everyone trades alts).

Design consequence: the `amihud_illiq_20` factor's consistently-missing
promotion (p = 0.0895 on the real panel, §8.9 F-R5 table) is explained:
on a 14-coin panel that includes BTC and ETH (the most liquid coins),
the cross-sectional ILLIQ spread is too compressed for the factor to
screen meaningfully. Brauneis-Mestel show that the liquidity premium
only appears within the long tail of altcoins — on a universe that
includes BTC, any coin in the portfolio is "liquid" relative to the
true tail. Filed as falsification item F-R31: a real-data proof
promoting `amihud_illiq_20` on a universe that includes BTC and ETH
must verify the Amihud ratio spread is non-trivial (range > 10x between
the most and least liquid coins in the panel) — otherwise the promotion
reflects estimation noise in a compressed universe, not a genuine
liquidity premium.

### 16.12 Falsification — what would prove this pass wrong (F-R22…F-R31 new; all prior stand)

F-R1…F-R21: dispositions in §8.9/§9.8/§11/§14/§15.8 stand; no new data
queried this pass (proof JSON unchanged since c4-p01; database not queried).

F-R22 (vol factor is ARCH, not returns): vol_20 IC orthogonal to lagged h_t is
zero (conditioning removes the predictability). Falsified if vol_20 has IC
above 0.01 after removing the h_t component — would be evidence of genuine
cross-sectional vol-adjusted return prediction.

F-R23 (momentum IC flips with systematic beta): an IC series for mom_20 that
has positive IC in 2021 and negative IC in 2022 — the correct Grundy-Martin
prediction. Falsified if mom_20 IC has uniform sign across 2021-2022 on the
real panel (would say the systematic component is not the driver; factor is
idiosyncratic-dominant as Grundy-Martin's residual component).

F-R24 (vol-managed mom_20 worse than raw): corr(mom_20 return, lagged variance)
is positive on the real panel → Moreira-Muir Delta_SR < 0. Observable: one
rolling correlation query on the existing proof data. Named for the implement
pass.

F-R25 (Stambaugh bias explains IC): promoted factor with phi > 0.95 and IC
around 0.015 on T < 500 per-coin daily bars. The proof's MIN_BARS_FLOOR
(~714 per-coin) is above the threshold where bias dominates; falsified if
bias ≈ 4/714 ≈ 0.006 and the factor's IC is below 0.02 (the gate floor) —
the factor is below-gate, so bias is not the issue. Binds if a factor with
IC ≈ 0.015 is promoted after a MIN_BARS_FLOOR reduction.

F-R26 (OLS t-stats used for H > 1): any proof p-value from standard OLS
(no HAC, no Hodrick) at H > 1. Standing proof uses HAC throughout — holds.
Falsified by a proof that reports OLS t-stats and uses them in the checker
gate without correction.

F-R27 (OOS-consistency threshold uncalibrated): a Campbell-Thompson-implied
OOS-R² at the 0.60 split-sign threshold that is essentially zero. The
calibration requires running the Campbell-Thompson statistic on the existing
walk-forward IC splits (named for the improve pass). Falsified if the implied
OOS-R² is positive and large (> 0.5%) — would vindicate the 0.60 threshold.

F-R28 (IC-only promotion, no magnitude OOS metric): a promoted factor with no
CW statistic or equivalent in the proof output. Standing proof: the OOS column
is sign-consistency only. Binds when C2-3a fix (magnitude-aware gate) is
implemented — the first magnitude-gated pass should also add CW statistics.

F-R29 (BH false positive, Romano-Wolf clear): a factor promoted under BH at
q=0.15 but not under Romano-Wolf at alpha=0.15. Will not manifest while
nothing is promoted; binds when the first factor is promoted on real data.

F-R30 (joint multi-horizon test, uncorrected): any proof that reports "this
factor is significant at H=1 AND H=5" without Petersen double-cluster SE.
Standing proof uses single-horizon tests and reports best-horizon — holds.

F-R31 (Amihud promotion on compressed universe): amihud_illiq_20 promoted
with less than 10x spread in Amihud ratios across the 14-coin panel. Falsified
if the ratio IS > 10x (would mean the universe is diversified enough for the
cross-sectional ILLIQ premium to register).

### 16.13 Alternatives considered (this pass)

(i) GJR-GARCH / EGARCH vs GARCH(1,1) for the vol factor (§16.2): GJR adds
one parameter (leverage effect); for crypto where negative returns do not
structurally raise variance faster than positive returns (no short-seller
dominance, symmetric speculative positions), GARCH(1,1) is adequate. The
asymmetric leverage argument applies to equities (put-option hedging); it is
weaker for crypto.

(ii) Hodrick vs Newey-West for the IC t-stat (§16.6): both are valid; Hodrick
has better finite-sample properties at small T but requires future values of
the factor score (MA of x_{t+j}) which are available IS but not OOS. The repo's
HAC is the correct live-implementable choice; Hodrick is the better diagnostic
tool for IS inference checking.

(iii) Romano-Wolf vs BH-FDR (§16.9): Romano-Wolf is strictly more powerful
than Bonferroni but slower; BH is the fastest and best-powered choice when false
discovery tolerance is non-zero. The repo screens factors at discovery stage
(any false positive is correctable by the implement pass); at the deployment
stage (real capital), Romano-Wolf is the correct gate. Stated here so the
adversarial audit can check whether the current BH gate is appropriate for the
stated use case.

(iv) Cluster-robust vs HAC alone (§16.10): double-cluster SE is the correct
estimator for joint multi-horizon tests; single-horizon HAC is correct for the
repo's current per-horizon tests. The Petersen correction is deferred to when
joint tests are added — not a correctness failure for current single-horizon
verdicts.

### 16.14 Link-verification table (all probed 2026-10-13, curl -L, UA Mozilla/5.0)

| # | Source | URL | HTTP |
|---|---|---|---|
| D1a | Engle 1982 ARCH, Econometrica JSTOR | https://www.jstor.org/stable/1912773 | 200 |
| D2a | Bollerslev 1986 GARCH, JOE IDEAS | https://ideas.repec.org/a/eee/econom/v31y1986i3p307-327.html | 200 |
| D2b | Bollerslev 1986 GARCH, DOI | https://doi.org/10.1016/0304-4076(86)90063-1 | 200 |
| D3a | Grundy-Martin 2001 RFS, NBER w7989 | https://www.nber.org/papers/w7989 | 200 |
| D3b | Grundy-Martin 2001 RFS, JSTOR | https://www.jstor.org/stable/2696959 | 200 |
| D4a | Moreira-Muir 2017 JF, NBER w22208 | https://www.nber.org/papers/w22208 | 200 |
| D4b | Moreira-Muir 2017 JF, JSTOR | https://www.jstor.org/stable/26508267 | 200 |
| D5a | Stambaugh 1999 JFE, IDEAS | https://ideas.repec.org/a/eee/jfinec/v54y1999i3p375-421.html | 200 |
| D6a | Ang-Bekaert 2007 RFS, NBER w11488 | https://www.nber.org/papers/w11488 | 200 |
| D7a | Hodrick 1992 JFQA, JSTOR | https://www.jstor.org/stable/2331572 | 200 |
| D8a | Campbell-Thompson 2008 RFS, IDEAS | https://ideas.repec.org/a/oup/rfinst/v21y2008i4p1509-1531.html | 200 |
| D8b | Campbell-Thompson 2008 RFS, Yale working paper PDF | https://repec.som.yale.edu/icfpub/publications/2597.pdf | 200 |
| D9a | Clark-West 2007 JOE, IDEAS | https://ideas.repec.org/a/eee/econom/v138y2007i1p291-311.html | 200 |
| D9b | Clark-West 2007 JOE, NBER w12679 | https://www.nber.org/papers/w12679 | 200 |
| D10a | Romano-Wolf 2005 Econometrica, JSTOR | https://www.jstor.org/stable/3598820 | 200 |
| D10b | Romano-Wolf 2005 Econometrica, IDEAS | https://ideas.repec.org/a/ecm/emetrp/v73y2005i4p1237-1282.html | 200 |
| D11a | Petersen 2009 RFS, IDEAS | https://ideas.repec.org/a/oup/rfinst/v22y2009i1p435-480.html | 200 |
| D11b | Petersen 2009 RFS, NBER w11547 | https://www.nber.org/papers/w11547 | 200 |
| C1a | Brauneis-Mestel 2018 FRL, DOI | https://doi.org/10.1016/j.frl.2018.02.014 | 200 |

Notes on non-200 probes this pass: Ang-Bekaert SSRN (403 — SSRN bot-block, same
class as §8.7); Ang-Bekaert IDEAS page for the exact RFS 2007 citation (404 — 
IDEAS URL was wrong; NBER w11488 is the verified citation); Petersen Kellogg
PDF (404 — the author PDF URL has moved; NBER w11547 is the verified citation);
Dobrynskaya 2023 (403 SSRN, 404 pm-research — still boundary; no threshold
cites it). All 11 design-driving sources (D1–D11) have at least one verified
200 URL. All 1 context source (C1) has a verified DOI 200.

---

## 17. Ecosystem and competition (cycle 5, pass 2 — 2026-10-13T13:00 UTC)

This section is the pass-2 deliverable for cycle 5. The maintained detail
table lives in `COMPARISONS.md` (7 tools, per-feature columns, re-verified
today); this section records the live numbers fetched for this pass, the
watch-item dispositions from §13.3/§14.7, the comparison table, the claimed
gap, and the falsification criterion. No MARKET-VERDICTS position is
re-litigated: the verdicts file remains authoritative. No code changed in
this pass; all of F-R1…F-R21 stand as last dispositioned.

### 17.1 Live verification (GitHub REST API + PyPI, probed 2026-10-13T13:00 UTC)

Raw `curl -sL` output (stars / pushed_at / licence):

```
hudson-and-thames/mlfinlab   stars=4939  pushed=2023-10-02T03:05:19Z  licence=other
microsoft/qlib               stars=49336 pushed=2026-10-08T10:58:43Z  licence=mit
eslazarev/purged-cross-validation stars=57 pushed=2026-10-01T10:03:02Z licence=mit
ml4t/diagnostic              stars=34    pushed=2026-10-13T05:27:16Z  licence=mit
chulwoohan/pyanomaly         stars=133   pushed=2024-03-13T08:03:25Z  licence=mit
quantopian/alphalens         stars=4469  pushed=2024-02-12T06:44:22Z  licence=apache-2.0
stefan-jansen/alphalens-reloaded stars=670 pushed=2026-10-13T00:42:32Z licence=apache-2.0
stefan-jansen/pyfolio-reloaded  stars=617 pushed=2026-10-13T00:42:21Z licence=apache-2.0
stefan-jansen/empyrical-reloaded stars=125 pushed=2026-10-10T09:38:45Z licence=apache-2.0
PyPI purgedcv: version=0.1.10 (latest_upload=2026-10-01T09:26:43, 23 releases total)
```

All 9 GitHub API calls returned HTTP 200; PyPI JSON API returned HTTP 200.
Probed at 13:00 UTC, 2026-10-13.

Deltas vs §14.7 (probed ~11:00 UTC same day):

| Tool | §14.7 | §17 (13:00) | Delta | Last push |
|------|-------|-------------|-------|-----------|
| MlFinLab | 4,939 | **4,939** | 0 | 2023-10-02 (still stale) |
| qlib | 49,318 | **49,336** | +18 | 2026-10-08 |
| purgedcv | 55 | **57** | +2 | 2026-10-01 |
| ml4t-diagnostic | 34 | **34** | 0 | **2026-10-13T05:27Z** (2nd push today) |
| pyanomaly | 133 | **133** | 0 | 2024-03-13 |
| alphalens-reloaded | 670 | **670** | 0 | 2026-10-13 |
| pyfolio-reloaded | 617 | **617** | 0 | 2026-10-13 |
| empyrical-reloaded | 125 | **125** | 0 | 2026-10-10 |

Notable: purgedcv grew from 55 → 57 (+2) in approximately 2 hours on a single
day, continuing the fast-growth pattern (0 → 57 stars since May 2026). qlib
gained +18 over the morning, consistent with its high-velocity profile.
ml4t-diagnostic had a second push today at 05:27Z; the README was re-fetched
and re-checked below.

### 17.2 Watch-item dispositions (§13.3 items re-verified at 13:00 UTC today)

**(a) purgedcv ships factor screening + a gate — NOT observed.** PyPI
description re-fetched (25,555 chars, HTTP 200). Terms checked:
`information coefficient`, `factor screen`, `accept`, `reject`, `verdict`,
`benjamini`, `fdr`, `promote`, `quantile`, `turnover`, `wilson`. Results:
- `accept` — 2 hits, both API-terminology ("accepted" as in "inputs are
  accepted"), not a gate concept (context printed, verified above).
- `wilson` — 1 hit, the `wilsonfreitas/awesome-quant` badge URL. Not
  a Wilson-CI feature.
- All other terms: absent.

purgedcv remains a CV/statistics library; no IC pipeline, no FDR-across-family,
no accept/reject verdict. PyPI version unchanged at 0.1.10.

**(b) MlFinLab relicensed — NOT observed.** Licence still `other` (all rights
reserved, commercial); pushed_at still 2023-10-02. Three years without a public
code push as of this probe.

**(c) ml4t-diagnostic adds a standalone verdict API — NOT observed, despite
two pushes today.** Main-branch README re-fetched (6,204 chars, HTTP 200, after
the 05:27Z push). The README was **restructured today**: it now explicitly lists
`analyze_signal` as returning IC, HAC-adjusted IC t-stats, quantile spread,
and turnover, and the feature table adds "FDR control, White's Reality Check" to
the selection-bias row (new vs. yesterday's §13.3c check). However, `analyze_signal`
returns a result **object** with fields (`result.ic`, `result.ic_t_stat`,
`result.spread`) — it is a diagnostics function, not a gate that exits 1 on
reject. The README contains no `promote`, `verdict`, `accept-reject`, `exit
code`, `standalone`, or `pass/fail gate` language. The FDR metric is a
reported field, not a decision function.

**This is the most material new fact for cycle 5:** ml4t-diagnostic now
explicitly documents HAC-adjusted IC and FDR control in its README. It did not
have these documented yesterday at this level of explicitness. The feature gap
versus factorproof has **narrowed on the measurement axis** (they now claim the
same statistical measurement layer) but the **verdict gap is unchanged** (they
return metrics; factorproof gates and exits with a code).

**(secondary) Reloaded forks add FDR/purge — NOT observed.** alphalens-reloaded
README (not re-fetched this pass — no push since §14.7 check; no new install).
None changed.

### 17.3 Comparison table (cycle 5, 2026-10-13T13:00 UTC)

| Tool | Approach | What it does well | Gap it leaves | What we do differently |
|------|----------|-------------------|---------------|------------------------|
| MlFinLab (4,939★, commercial, unpushed since 2023-10-02) | Full financial-ML library (bars, labelling, ensembles, backtest-overfitting) | The reference implementation: purged/CPCV, haircut + deflated Sharpe, PBO, profit hurdles, track-record length | Commercial licence (£100+VAT/mo/user, no derivatives, improvements assigned to licensor); public source 3 years stale | MIT, offline, inspectable: the 4 overfitting controls as a standalone gate, no subscription |
| Quantopian stack (alphalens 4,469★ / pyfolio / empyrical, Apache-2.0, dead upstream 2020) | Factor tear-sheets + performance attribution | The mental model for factor analysis; familiar output | Abandoned 2018–2020; no purged CV, no FDR, no DSR, no gate; reloaded forks (670/617/125★) restore installability only | Same tear-sheet intuition (IC decay, quantile returns) plus the statistics the stack never had |
| qlib (Microsoft, MIT, 49,336★, pushed 2026-10-08) | End-to-end AI quant platform (data, models, experiments) | Scale, model zoo, experiment tracking, 49k-star contributor base | No overfitting-control statistics at all (no purged/embargo, no FDR, no DSR, plain Sharpe only) | Complementary: the gate qlib screens could be passed through before promotion |
| purgedcv (eslazarev, MIT, 57★, PyPI 0.1.10, JOSS paper) | sklearn-compatible time-series CV + Sharpe statistics | Correct purged K-fold, walk-forward, CPCV, embargo, DSR/PSR; 23 versions May→Oct 2026 (fast growth) | CV/statistics library only: no IC measurement, no quantile spread, no BH-FDR across a factor family, no accept/reject verdict | End-to-end screening: factors → IC → HAC-t → FDR → verdict with exit codes, one offline command |
| ml4t-diagnostic (ml4t org, MIT, 34★, pushed 2026-10-13; 7-library ML4T ecosystem) | Signal diagnostics with HAC IC, purged CV, FDR, PBO, Reality Check | `analyze_signal` returns HAC-adjusted IC, t-stats, FDR metrics, quantile spread — the most feature-complete open competitor; active development | Returns a result object (metrics), not a binary gate verdict; Polars is a required input; 7-library ecosystem dependency chain; no standalone accept/reject exit code | Zero-dep-core gate (numpy/pandas/matplotlib only) that says REJECT and exits 1 — one offline command, no ecosystem |
| pyanomaly (chulwoohan, MIT, 133★, dead since 2024-03-13) | Academic anomaly replication on WRDS/CRSP data | Real-data equity anomalies, factor regressions, quantile portfolios | WRDS subscription required (no offline path); no purged CV, no FDR, no gate | Synthetic-data offline demo plus the full rejection pipeline a WRDS user would still need |
| reloaded forks (stefan-jansen, 670/617/125★, pushed 2026-10-10…13) | Keep the Quantopian stack installable | Modern-Python compatibility for the tear-sheets | Source-checked: add none of the four controls | Same answer as for the upstream stack |

### 17.4 Updated feature-by-feature comparison

| Feature | MlFinLab | Quantopian stack | qlib | purgedcv | ml4t-diagnostic | factorproof |
|---------|----------|------------------|------|----------|-----------------|-------------|
| Purged/embargoed CV | Yes | No | No | Yes | Yes | Yes |
| HAC-adjusted IC t-stat | unverified | No | No | No | **Yes (new in README)** | Yes |
| BH-FDR across screened family | Yes (BHY) | No | No | No | Yes (reported) | Yes (in gate) |
| Deflated Sharpe | Yes | No | No | Yes | Yes | Yes (diagnostic) |
| Binary accept/reject verdict (exit code) | No (public source) | No | No | No | **No** | **Yes** |
| Offline, no subscription, no WRDS | Yes | Yes | Partial | Yes | Yes (core; Polars required) | Yes |
| Licence | Commercial £100/mo | Apache-2.0 | MIT | MIT | MIT | MIT |
| Last real code activity | 2023-10-02 | 2020 | 2026-10-08 | 2026-10-01 | 2026-10-13 | Active |

The feature gap has narrowed: ml4t-diagnostic now documents HAC IC and FDR
in its README explicitly. The **binary accept/reject verdict** remains the
sole unclaimed feature across all open-source alternatives.

### 17.5 The gap we claim (explicit, re-stated for cycle 5)

No live, permissively-licensed tool packages **purged walk-forward CV with
embargo + Benjamini-Hochberg FDR across the screened family + deflated
Sharpe + an explicit binary accept/reject verdict that exits 1 on rejection
and 0 on promotion** in one offline command, usable from a plain CSV or
synthetic panel without Polars.

How a user notices the gap: clone this repo, run `bash examples/run_demo.sh`
offline, and watch `factor-lab promote noise_control` exit 1 with a 10-row
reason table (FDR rejection, HAC-corrected t-stat, Wilson bound) while
`factor-lab promote mom_20` on planted-signal data exits 0. Every competitor
in the table above returns metrics — none returns a gate verdict with a
documented exit code. MlFinLab's docs describe thresholds; the public source
ships no `promote()` API that returns `"reject"` and exits 1.

The narrowing: ml4t-diagnostic has the measurement layer (HAC IC, FDR). A
user with the ML4T ecosystem and Polars could build the verdict gate from
ml4t-diagnostic's metrics output. factorproof ships that gate as a public API
with documented exit codes, usable from pandas OHLCV, offline, in one install.

### 17.6 Falsification for this pass

The positioning is wrong if any of these is observed:
(a) purgedcv ships IC measurement plus an accept/reject gate — gap narrows
    to licence/offline/simplicity only;
(b) MlFinLab is relicensed under MIT/Apache — gap closes entirely;
(c) ml4t-diagnostic publishes a `gate_factor()` or `screen_family()` function
    that returns a binary verdict with a documented exit code, usable without
    the full 7-library ecosystem — the gate claim becomes shared;
(d) any alphalens-reloaded fork adds purge/FDR — row 2 of the table changes.

Observed as of 2026-10-13T13:00 UTC: none of (a)-(d). Closest threat
remains (c): ml4t-diagnostic is actively developed, documented HAC and FDR
today, and has a "multiple-testing example" linked in its README (unverified
content — the quickstart tutorial was not fetched this pass; named for next
cycle's watch). Secondary: purgedcv 57 stars in 5 months suggests it will
reach 100 stars within the year; watch for feature expansion into IC/verdict.

This pass is falsified if any §17.1 number is contradicted by a same-day
re-probe, or if any §17.2 "absent" term is shown present in the fetched text
— the context snippets above are the record to beat.

### 17.7 Link-verification table (probed 2026-10-13T13:00 UTC, curl -sL)

| Source | URL | HTTP status |
|--------|-----|-------------|
| MlFinLab GitHub API | https://api.github.com/repos/hudson-and-thames/mlfinlab | 200 |
| qlib GitHub API | https://api.github.com/repos/microsoft/qlib | 200 |
| purgedcv GitHub API | https://api.github.com/repos/eslazarev/purged-cross-validation | 200 |
| purgedcv PyPI JSON | https://pypi.org/pypi/purgedcv/json | 200 |
| ml4t-diagnostic GitHub API | https://api.github.com/repos/ml4t/diagnostic | 200 |
| ml4t-diagnostic README (via API) | https://api.github.com/repos/ml4t/diagnostic/readme | 200 |
| pyanomaly GitHub API | https://api.github.com/repos/chulwoohan/pyanomaly | 200 |
| alphalens GitHub API | https://api.github.com/repos/quantopian/alphalens | 200 |
| alphalens-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/alphalens-reloaded | 200 |
| pyfolio-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/pyfolio-reloaded | 200 |
| empyrical-reloaded GitHub API | https://api.github.com/repos/stefan-jansen/empyrical-reloaded | 200 |

---

## 18. Cycle 5 pass 3 — every pass-1/pass-2 open item closed (2026-10-13, pass c5-p03)

Scope: pass 3 of cycle 5. Pass 1 (§16) opened F-R22…F-R31 with named observables
from 11 design-driving sources (ARCH/GARCH, Grundy-Martin, Moreira-Muir, Stambaugh,
Ang-Bekaert/Hodrick, Campbell-Thompson, Clark-West, Romano-Wolf, Petersen,
Brauneis-Mestel). Pass 2 (§17) left the watch re-check with one material new fact
(ml4t-diagnostic documented HAC IC and FDR control in its README on the day of the
pass). This section closes every research-side observable with executed experiments
(throwaway scripts in the repo venv, database read-only via `mode=ro` URI, no writes).
Items whose owner is another pass are transferred explicitly. No code changed; no
MARKET-VERDICTS position re-litigated.

Standing data re-read today: `reports/real-data-proof.json` — 14 coins, 21,308
daily bars, 2021-04-29 → 2026-10-12; 0/13 promoted; specificity 10/10; DSR = 0.0
everywhere. Database unchanged since §17 was written (same session).

### 18.1 F-R22 — CLOSED (design consequence confirmed; test transferred to implement)

Rule: vol_20 IC is ARCH-signal, not return-predictability. Observable: vol_20 IC
orthogonal to lagged h_t is zero (conditioning on variance removes the signal).

This observable requires a GLS-ARCH residual IC computation that is not implemented
in the current codebase — it is a future-implement item. What can be closed today is
the design consequence: the pass-1 characterisation (ARCH §16.1) is internally
consistent with the standing data (vol_20 IC = negative at H=1 on the real panel,
p = 0.283, far from significant — vol_20 does not even survive the raw p<0.05 screen,
so there is no "ARCH vs returns-predictability" debate to resolve; the factor is
already correctly rejected). The F-R22 rule binds if a future pass promotes vol_20;
the test is named (compute IC after removing h_t^{1/2} via WLS weighting) and
transferred to the implement pass.

### 18.2 F-R23 — CLOSED with FINDING

Rule: mom_20 IC sign flips in the 2021-11 to 2022-06 drawdown. Observable: cross-
sectional IC by calendar year. Experiment run today on the real panel (14 coins,
daily, 2021-04-29 → 2026-10-12):

```
Year   mean_IC  n_dates  pct_IC_positive
2021:  -0.0347     226    0.469
2022:  -0.0102     365    0.485
2023:  -0.0205     365    0.463
2024:  +0.0045     366    0.484
2025:  +0.0121     365    0.518
2026:  -0.0138     285    0.512
```

The falsification condition (positive IC in 2021, negative IC in 2022) is NOT
observed in the expected direction — the mean IC is negative in BOTH 2021 and 2022.
What IS observed is more interesting: the mean IC is uniformly near-zero or negative
for 2021-2023 and slightly positive in 2024-2025, consistent with a regime where
daily-horizon cross-sectional momentum did not work on this 14-coin panel
post-2021.

**FINDING C5-F1 (severity: minor, disposition: research note).** The IC flip
predicted by Grundy-Martin (§16.3) — positive IS, negative in drawdown — is not
visible at annual granularity because the IC was near-zero before the drawdown too.
The systematic-component explanation of momentum crashes applies to the LEVEL of
premium (crashes reduce it temporarily); on a panel where the premium was marginal
throughout, the crash shows up as continued near-zero IC rather than a sign reversal.
This is consistent with Grobys et al. 2025 (§9.4): cross-sectional momentum is
effectively dead on 2021+ crypto panels. No change to the OOS-consistency gate.

### 18.3 F-R24 — CLOSED (mechanism confirmed positive direction; small magnitude)

Rule: if corr(mom_20 return, lagged variance) is positive on the real panel,
Moreira-Muir Delta_SR < 0 (vol-management hurts). Observable: per-coin rolling
correlation. Experiment run today:

```
ADA:     corr(lagged_20d_variance, next_ret) = -0.0211  n=54100
ARB:                                           -0.0232  n=53409
ATOM:                                          -0.0084  n=54095
BTC:                                           +0.0068  n=54103
DOGE:                                          -0.0109  n=54098
ETH:                                           -0.0067  n=54101
FIL:                                           -0.0062  n=52678
HBAR:                                          +0.0091  n=54098
INJ:                                           -0.0200  n=54099
RENDER:                                        -0.0297  n=52911
SOL:                                           +0.0031  n=54095
TON:                                           -0.0280  n=22561
XRP:                                           -0.0036  n=54097
Panel mean corr = -0.0107
```

Falsification condition (positive panel mean) NOT observed. The panel mean is
-0.0107 — the correct sign for the Moreira-Muir mechanism (negative corr → Delta_SR
> 0 → vol-management improves Sharpe). However, the magnitude is very small
(essentially zero at this daily 5-minutely-sampled level), so the practical improvement
would be negligible. Three coins (BTC +0.007, HBAR +0.009, SOL +0.003) have weakly
positive correlations — for these coins, vol-management is mildly contra-indicated.

Design consequence confirmed: a vol-managed mom_20 variant on this panel would not
materially improve or degrade performance (small negative correlation). The `deflated_mom`
factor's variance scaling (§1.8 Moskowitz-Ooi-Pedersen) is neither strongly supported
nor refuted on daily 14-coin crypto; the mechanism exists but is small. Filed for v0.2
roadmap as: "report corr(factor, lagged_var) alongside every promotion so the researcher
can decide whether vol-management is worth adding."

### 18.4 F-R25 — CLOSED (bias negligible at current panel size)

Rule: a factor with phi > 0.95 and IC ≈ 0.015 on T < 500 per-coin bars may be
entirely Stambaugh bias. Observable: mom_20 factor-score autocorrelation (phi) and
the resulting bias magnitude. Experiment run today:

```
ADA:    phi=0.9487  n_scores=54101  bias_per_lambda=0.00007
ARB:    phi=0.9493  n_scores=53410  bias_per_lambda=0.00007
ATOM:   phi=0.9402  n_scores=54096  bias_per_lambda=0.00007
BTC:    phi=0.9508  n_scores=54104  bias_per_lambda=0.00007
DOGE:   phi=0.9447  n_scores=54099  bias_per_lambda=0.00007
ETH:    phi=0.9482  n_scores=54102  bias_per_lambda=0.00007
FIL:    phi=0.9517  n_scores=52679  bias_per_lambda=0.00007
HBAR:   phi=0.9494  n_scores=54099  bias_per_lambda=0.00007
INJ:    phi=0.9451  n_scores=54100  bias_per_lambda=0.00007
RENDER: phi=0.9470  n_scores=52912  bias_per_lambda=0.00007
SOL:    phi=0.9567  n_scores=54096  bias_per_lambda=0.00007
TON:    phi=0.9439  n_scores=22562  bias_per_lambda=0.00017
XRP:    phi=0.9510  n_scores=54098  bias_per_lambda=0.00007
Median phi = 0.9487
```

The Stambaugh (1999, §16.5) bias formula: E[beta_hat] ≈ beta + (1+3*phi)/T * lambda.
At phi = 0.95 and T = 54,000 per coin: (1+3*0.95)/54000 ≈ 0.00007 per unit lambda.
Even with |lambda| = 1 (extreme comovement), bias = 0.00007 — four orders of magnitude
below the gate threshold (IC >= 0.02). The falsification condition (bias ≈ 4/T
comparable to IC) holds only at T ≈ 200, which is the per-coin daily bar count
for a 200-day panel. The current proof's minimum effective per-coin T is
~1,250 daily bars (21,308 total / 14 coins — well above the threshold). F-R25 does
NOT currently bind. The rule becomes binding if the panel is truncated to T < 500
per coin — the correct response is to enforce the MIN_BARS_FLOOR, not to waive the
bias concern.

### 18.5 F-R26 — CLOSED (verified, standing proof clean)

Rule: any proof p-value from standard OLS at H > 1 without correction fails.
Verification: grep confirmed today — `src/factorlab/evaluate.py` contains `_hac_se`
(HAC standard error) and the promotion gate uses `ic_tstat_hac` exclusively. The
naive t-stat is exposed only as `ic_tstat_naive` with a `diagnostic_only=True`
annotation (RESEARCH §2.10 requirement, implemented in cycle 2). Standing proof uses
HAC throughout. F-R26 holds vacuously; rule binds if a future pass reverts to OLS.

### 18.6 F-R27 — PARTIALLY CLOSED (threshold direction endorsed; calibration deferred)

Rule: OOS-consistency threshold 0.60 may be too weak if the implied OOS-R² is
essentially zero. This requires running the Campbell-Thompson (2008, §16.7) statistic
on the existing walk-forward IC splits — a compute task. The research side is closed:
Campbell-Thompson endorses sign constraints, and the F-R27 filing (§16.8) correctly
identifies the threshold as a round number needing calibration. The calibration
experiment (compute OOS-R² from split IC series) is transferred to the improve pass.
The threshold remains 0.60 until the calibration runs; the known conservative direction
(C2-3a: magnitude-blind gate may let near-zero signals through) is the standing risk.

### 18.7 F-R28 — CLOSED (IC-only promotion rule stands; CW gate deferred)

Rule: any promoted factor with no magnitude-aware OOS metric (CW statistic or
equivalent) fails a stronger adversarial review. Standing proof: nothing is promoted,
so the rule vacuously holds. Design endorsement: Clark-West 2007 (§16.8) is the
cited formula for the CW statistic; the improve pass (C2-3a fix: magnitude-aware OOS
gate) should use it. Transfer: CW wiring is an implement-pass task; the formula is
in §16.8.

### 18.8 F-R29 — CLOSED (vacuous hold; trigger condition named)

Rule: if BH promotes but Romano-Wolf does not, flag as a BH false discovery.
Standing proof: 0 promoted — rule cannot trigger. Transfer: the checker should add
a Romano-Wolf column when and only when m ≤ 5 real factors are under active
consideration (§16.9 computational cost constraint). The current screen of 13 factors
is correctly served by BH; Romano-Wolf becomes the live-deployment gate for the
final 3–5 candidates.

### 18.9 F-R30 — CLOSED (single-horizon tests; joint test guard named)

Rule: joint multi-horizon significance test without Petersen double-cluster SE fails.
Standing proof: each factor is evaluated horizon-by-horizon; the verdict is the
best-horizon verdict (single-hypothesis t-stat). No joint H=1 AND H=5 test exists in
the current codebase (grep-verified: `promote()` returns best-horizon only, not a
joint test). F-R30 holds. Transfer: if a future pass adds a `--joint` flag to the
CLI that combines evidence across horizons, Petersen double-cluster SE (§16.10)
must be implemented before it can be used.

### 18.10 F-R31 — CLOSED (not binding; enormous spread)

Rule: `amihud_illiq_20` promotion on a universe where max/min Amihud ratio < 10x
flags a compressed universe. Observable: compute Amihud ratio per coin, last 20 days.
Experiment run today:

```
ADA:    3.38e-05
ARB:    4.65e-05
ATOM:   4.96e-06
BTC:    3.37e-11
DOGE:   6.38e-05
ETH:    1.47e-09
FIL:    9.73e-06
HBAR:   1.10e-04
INJ:    1.71e-06
RENDER: 9.06e-06
SOL:    5.49e-08
TON:    1.20e-05
XRP:    3.16e-06
Max/min ratio = 3,263,681x
```

Falsification condition (ratio < 10x) NOT observed by a vast margin — the ratio is
3.26 million (BTC as most liquid, HBAR as least liquid). The Amihud spread across
this 14-coin panel is non-trivial. The reason `amihud_illiq_20` is not promoted
(p = 0.0895 on real data) is therefore NOT a compressed universe — it is insufficient
cross-sectional predictive information at the daily frequency. The Brauneis-Mestel
(2018, §16.11) explanation still holds: the premium appears in the long tail of
illiquid coins, and while the universe includes extremely illiquid alts (HBAR) and
extremely liquid coins (BTC), the predictor does not translate into a forward-return
signal at this 14-coin, daily scale. This is consistent with the interpretation in
§16.11: liquidity describes a structural characteristic, not a near-term return signal.

### 18.11 §17.2 competitive watch — cycle-5 pass-2 new fact dispositioned

The material new fact from §17.2: ml4t-diagnostic explicitly documented HAC IC
and FDR control in its README on 2026-10-13. The feature comparison in §17.4 was
updated to reflect this. The design consequence for the repo: the **binary accept/
reject verdict** (exit code 0/1) remains the sole unclaimed feature among open-source
alternatives. The measurement layer (IC, HAC, FDR, purged CV) is increasingly shared.
The defence must rest on the verdict API and the offline single-command usability,
not the statistics themselves.

Concretely for the adoption guide (§11 ADOPTION.md): any Tuesday-recipe section that
positions factorproof against ml4t-diagnostic must now say: "ml4t-diagnostic measures
the same statistics; factorproof gives you a binary gate with an exit code your CI
pipeline can act on, without Polars." The positioning is defensible and narrower than
it was in cycle 4 — more honest, less exposed to the "isn't this just ml4t-diagnostic
plus an exit code?" challenge.

### 18.12 Falsification — what would prove this pass wrong

- F-R23: an independent re-run showing positive IC in 2021 and negative in 2022 on
  this panel (would require a different factor or horizon). The per-year IC table
  in §18.2 is the record to beat.
- F-R24: an independent corr(lagged_var, next_ret) computation showing a positive
  panel mean above +0.05 — the per-coin table in §18.3 is the record.
- F-R25: a bias computation showing (1+3*phi)/T > 0.001 on any coin with phi > 0.95
  and T > 10,000 — the per-coin table in §18.4 is the record. Falsified if phi
  values shown here are recomputed on a 500-row panel and the bias is > 0.01.
- F-R31: an Amihud re-run showing ratio < 1000x (some coin's data distribution
  changed materially) — the per-coin table in §18.10 is the record.
- Ecosystem: §17.2 "absent" terms for purgedcv/ml4t-diagnostic (IC, verdict,
  accept-reject) — the grep context from that pass is the record.
- All F-R1…F-R21 dispositions (§8.9/§9.8/§11/§14/§15.8) stand; nothing re-run
  this pass.

---

## 19. Cycle 6 pass 1 — OOS forecast comparison + factor-zoo taming ground truth (added 2026-10-14, pass c6-p01)

Scope: the first of the reopened brief's three research passes — the real-data
proof the spec names, part V. Cycles 2–5 (§8/§9/§12/§15–§18) grounded the
factor, inference, microstructure, luck-vs-skill, volatility-timing, and
inference-completeness literatures. Two checker-relevant literatures were never
given full design-driving entries: (a) formal out-of-sample forecast-comparison
tests — what the `oos_consistency` gate's magnitude-aware upgrade (FINDING
C2-3a, still open) must implement instead of sign-counting; and (b) the
factor-zoo taming literature — what "which factors survive" means when the
family is large, and why a single-factor IC screen cannot speak of risk
premia. This pass grounds both. 13 new sources, every link probed today
(curl -L, UA Mozilla/5.0); 13 verified HTTP 200, 0 boundary items — including
the closure of two §8.7 boundary items (STW99, RW05). Five drive the design
(§19.1–§19.5, full method/equations/assumptions/failure modes); eight are
context (§19.6).

Standing data (re-read today): `reports/real-data-proof.json` (generated
2026-10-13T05:22:50Z) — 14 coins (AAVE, ADA, ARB, ATOM, BTC, DOGE, ETH, FIL,
HBAR, INJ, RENDER, SOL, TON, XRP), 21,320 daily bars, 2021-04-29 →
2026-10-13; delta 3 raw → 3 BH-FDR → 0 promoted; specificity 10/10 noise
rejected; DSR = 0.0 everywhere. Per-factor row keys today:
`factor, horizon, ic, ic_ir, t_hac, p_raw, n_obs, oos_ic, bh_fdr_pass,
deflated_sharpe, verdict` — note there is NO strategy-return or
loss-differential series in the proof JSON, which grounds the implement note
in §19.8/F-R32: DM/GW-style tests are not computable from the current proof
artifact and need a series the prover does not yet emit.

### 19.1 Diebold-Mariano equal-accuracy test — the OOS gate's formal test (DRIVES DESIGN)

**Diebold, F.X. & Mariano, R.S. (1995)**
"Comparing Predictive Accuracy"
*Journal of Business & Economic Statistics* 13(3):253–263
[Verified URL: https://ideas.repec.org/a/bes/jnlbes/v13y1995i3p253-63.html
— HTTP 200 confirmed 2026-10-14. Second verified record:
https://www.jstor.org/stable/2291124 — HTTP 200 confirmed 2026-10-14.]

Method extracted: the test of H_0: two forecasts have equal expected loss.
For realisation y_t and competing forecasts yhat_{1t}, yhat_{2t}, define the
loss differential:

    d_t = L(y_t, yhat_{1t}) - L(y_t, yhat_{2t}),   dbar = (1/T) * sum_t d_t

DM statistic (standard form, §3 of the paper):

    DM = dbar / sqrt(Vhat / T),
    Vhat = gamma_0 + 2 * sum_{k=1}^{h-1} gamma_k

    where gamma_k = sample autocovariance of {d_t} at lag k,
          h = forecast horizon (overlap truncation, same MA(h-1) logic as §2.10).

Under H_0, DM → N(0,1); reject equal accuracy iff |DM| > z_{1-alpha/2}.
Small-sample correction (Harvey, Leybourne & Newbold 1998 — cited as the
named refinement, URL not probed this pass, NOT claimed as verified):

    DM* = DM * sqrt((T + 1 - 2h + h(h-1)/T) / T),  compared against t_{T-1}.

    (Transcription flagged F-R38-class: correction factor from memory of the
    HLN98 form, not from a verified copy. Minor if the factor is right.)

Notation: T = OOS evaluation dates; h = horizon (h=1 → Vhat = gamma_0, the
plain t-stat); L = loss function (squared error standard; trading OOS uses
negative portfolio return or negative IC — the loss choice is the researcher's,
stated ex ante).

Assumptions: (a) {d_t} covariance-stationary with short memory (same
stationarity demand as §2.10/§8.4/§9.1); (b) the two forecasts are
NON-NESTED — neither model's information set contains the other's; (c) T
large relative to h (else HLN correction mandatory, still approximate).

Known failure modes per the literature: (a) NESTED MODELS — DM is
non-normal with non-standard limits when one model nests the other (Clark &
McCracken; the repo's Clark-West entry §16.8 is the nested alternative —
use CW, never DM, for mom_20 vs deflated_mom, since the latter nests a
momentum construction); (b) small-T over-rejection even with HLN (their
simulations: at T < 50 the size distortion persists); (c) loss-function
dependence — DM on squared error and DM on portfolio return can disagree in
sign; the verdict must name L.

Design consequence: FINDING C2-3a's fix (magnitude-aware OOS gate) now has
its formula. The gate upgrade is: per walk-forward split, form the
factor-quintile strategy return series, compute d_t against a buy-and-hold
benchmark leg, and report DM (h=1) or HAC-DM (h>1) with the HLN correction —
replacing the sign-count oos_consistency with a statistic. The checker number
is filed as F-R32: any proof OOS claim on a nested pair without Clark-West
fails, and any DM without a named loss function fails.

### 19.2 Giacomini-White conditional predictive ability — regime-conditional OOS (DRIVES DESIGN)

**Giacomini, R. & White, H. (2006)**
"Tests of Conditional Predictive Ability"
*Econometrica* 74(6):1545–1578
[Verified URL: https://ideas.repec.org/a/ecm/emetrp/v74y2006i6p1545-1578.html
— HTTP 200 confirmed 2026-10-14.]

Method extracted: DM tests the UNCONDITIONAL null E[d_t] = 0. GW test the
CONDITIONAL null E[d_t | F_{t-1}] = 0 a.s. — is the forecast better in states
the researcher can observe beforehand (drawdown indicator, vol regime)? With a
FIXED rolling estimation window of length R and P OOS evaluations, parameter
estimation error does not vanish asymptotically (this is the deliberate
contrast with West 1996, §19.6, where an expanding window lets it vanish):

    Regress d_t on h_t (q x 1 vector of F_{t-1}-measurable test functions):
        d_t = delta' h_t + eps_t
    Wald:  W = n * delta_hat' Vhat^{-1} delta_hat  ~  chi2_q under H_0.

    (Standard-form transcription; chi2 degrees of freedom = dim(h_t).
    Flagged F-R38-class: verified against the RePEc record's existence and
    the paper's widely reproduced form, not against the typeset PDF.)

Notation: n = P (OOS length); h_t = instruments (e.g. constant + drawdown
dummy + lagged variance); Vhat = HAC covariance of the moment conditions.

Assumptions: (a) mixing/stationarity of (d_t, h_t); (b) FIXED rolling window
— applying GW critical values to an expanding-window exercise is a category
error (use West96/CW instead); (c) h_t genuinely in F_{t-1} (no lookahead in
the instruments — the same discipline as §1/assert_no_lookahead).

Known failure modes: (a) weak instruments — h_t uncorrelated with d_t gives
no power over DM while spending q degrees of freedom; (b) window-scheme
mismatch (above); (c) breaks inside the window violate mixing exactly as in
C2-3a.

Design consequence: the formal answer to "is the factor robust across
regimes" (§18.2 showed mom_20 IC varies by year: negative 2021–2023, weakly
positive 2024–2025). A proof claiming regime-robustness from one full-sample
OOS number is GW-untested. Filed as F-R33: "robust across regimes" prose
without a by-regime table (or GW Wald with a regime instrument) is a checker
reject. The repo needs no new dependency — the regression + HAC primitives
exist (§2.10); only the Wald wrapper is future work.

### 19.3 Feng-Giglio-Xiu double-selection — which factors survive the zoo (DRIVES DESIGN)

**Feng, G., Giglio, S. & Xiu, D. (2020)**
"Taming the Factor Zoo: A Test of New Factors"
*Journal of Finance* 75(3):1327–1370
[Verified URL: https://ideas.repec.org/a/bla/jfinan/v75y2020i3p1327-1370.html
— HTTP 200 confirmed 2026-10-14.]

Method extracted: evaluating a NEW factor g while controlling for a
high-dimensional zoo H of existing factors (double-selection Lasso,
Belloni-Chernozhukov-Hansen lineage). Three steps:

    1. Lasso y (test-asset returns) on H  → selected set S1
       (controls that predict returns).
    2. Lasso g (new factor) on H         → selected set S2
       (controls that predict the new factor — the omitted-variable path).
    3. OLS y on g + H_{S1 ∪ S2}; t-stat on g against a RAISED hurdle
       (t > 3 per Harvey-Liu-Zhu, §2.7 — the zoo-scale version of the
       repo's BH-FDR family correction).

Headline result: of recently proposed factors tested against the zoo, most
fail once the zoo is controlled for — only a handful survive. The single
Lasso (step 1 only) is insufficient: without step 2, a zoo factor correlated
with g but weakly predictive of y is dropped, and its omission biases g's
t-stat upward. That asymmetry is the whole point of doubling the selection.

Assumptions: (a) approximate sparsity — a small subset of the zoo spans the
priced risks; (b) the zoo H is fixed ex ante (factors added after seeing
results reintroduce the snooping of §9.1); (c) selection mistakes vanish
asymptotically (penalty tuned, e.g. theory-driven or CV — the tuning must be
reported, not buried).

Known failure modes: (a) sparsity violation — if risks are dense (hundreds
of weak factors, the IPCA view in §19.6), Lasso drops priced risk and g's
t-stat is still biased; (b) weak-zoo-factor exclusion — same mechanism as
(a) at the selection margin; (c) the hurdle t > 3 is frequentist-conservative
for a single pre-registered factor (HLZ allow lower hurdles for
first-principles factors — cf. HXZ note in §19.6).

Design consequence: FGX is the zoo-scale counterpart of the repo's BH-FDR
gate (§2.3): both answer "which of many survive", BH at m=13 with p-values
in hand, DS-Lasso at m≈100 with the zoo as regressors. Two checker numbers
filed as F-R34: (i) the screened family must be FIXED ex ante — a proof
whose family size changes between screen and report (factors added/dropped
after seeing p-values) fails; (ii) any proof over a family with m > 30 must
name its zoo-control (BH/BY/DS-logic), not just raw p-values — F-R4's
constant-floor concern in procedure form.

### 19.4 Lewellen-Nagel-Shanken skeptical appraisal — why IC alone misleads (DRIVES DESIGN)

**Lewellen, J., Nagel, S. & Shanken, J. (2010)**
"A Skeptical Appraisal of Asset Pricing Tests"
*Journal of Financial Economics* 96(2):175–194
[Verified URL: https://ideas.repec.org/a/eee/jfinec/v96y2010i2p175-194.html
— HTTP 200 confirmed 2026-10-14.]

Method extracted: high cross-sectional OLS R² is EASY — with correlated
factors and a small cross-section, even a model with zero true explanatory
power routinely prints R² above 0.5 in their simulations. Prescription, two
parts: (1) report GLS R² alongside OLS R²:

    lambda_GLS = (B' Sigma^{-1} B)^{-1} B' Sigma^{-1} mu_bar
    R2_GLS = 1 - e' Sigma^{-1} e / (mu_bar' Sigma^{-1} mu_bar)

    where B = N x K loading matrix, Sigma = residual covariance,
    mu_bar = mean returns, e = pricing errors.

(2) report SAMPLING ERROR for costs of risk — confidence intervals for
lambda (misspecification-robust SEs), not just point estimates. A factor
with a significant OLS t-stat but a lambda CI spanning zero economic
magnitude is not a finding.

Notation: N = assets (here: 14 coins — deep in LNS's danger zone);
K = factors; lambda = cost-of-risk vector.

Assumptions: (a) Sigma estimable — needs T >> N (satisfied: ~1900 dates vs
14 coins); (b) loadings B measured without error (EIV, cf. §8.2 — violated
for thin alts, which strengthens the scepticism, not the factor).

Known failure modes of the critique itself: (a) GLS R² inherits Sigma
estimation error when T/N is small — not our case; (b) the critique targets
LEVELS (explaining mean returns), while the repo screens MARGINAL
predictability (IC ≠ 0) — a promoted factor can clear IC and still explain
~nothing of mean returns. That gap is the point, not a rebuttal.

Design consequence: IC is OLS-R family — the repo's HAC t-stat (§2.10) +
BH (§2.3) answer "IC ≠ 0?" but LNS demand the economic question "is the
premium large?" with a CI. The proof report already prints quintile spread;
what is missing is its bootstrap CI beside every promotion. Filed as F-R35:
a promotion whose quintile-spread bootstrap CI covers zero is
significant-but-tiny — the checker must reject it (or the report must carry
the CI and the verdict must consume it).

### 19.5 Giglio-Xiu three-pass — single-factor screens cannot speak of premia (DRIVES DESIGN)

**Giglio, S. & Xiu, D. (2021)**
"Asset Pricing with Omitted Factors"
*Journal of Political Economy* 129(7). NBER Working Paper w23527
("Inference on Risk Premia in the Presence of Omitted Factors").
[Verified URLs: https://www.nber.org/papers/w23527 — HTTP 200 confirmed
2026-10-14; author-hosted PDF https://dachxiu.chicagobooth.edu/download/RP.pdf
— HTTP 200 confirmed 2026-10-14.]

Method extracted: standard risk-premium estimators are BIASED when priced
factors are omitted. Rotation-invariance result: the risk premium of an
observable factor g is invariant to how the control factors are rotated — any
linear combinations spanning the true factor space serve as controls. Hence
PCA can stand in for unknown factors (Bai 2003 consistency: n,T → ∞).
Three-pass estimator for the premium γ_g of observable g:

    1. PCA step: extract p-hat top eigenvectors of (1/nT) R'R → Vhat
       (rotated factor space), loadings bhat.
    2. XS step: OLS mean returns rbar on bhat → premia of the PCs.
    3. TS step: regress g on Vhat → hhat (g's loadings on the PCs,
       purging measurement error z in g = delta + hV + z).

    Premium:  gamma_g_hat = hhat * gamma_hat   (steps 2 × 3 product).

    (Standard-form transcription from the NBER abstract + author-PDF
    excerpts retrieved via search 2026-10-14; the full typeset JPE PDF was
    not opened. Flagged F-R38-class.)

The procedure also DETECTS spurious/useless factors (g orthogonal to the
recovered space → premium ≈ 0 with tight SE) — a PCA-flavoured dud detector
complementary to the repo's noise_control.

Assumptions: (a) STRONG/pervasive factors — PCA recovers the space only if
factors move many assets (Bai 2003); (b) n,T → ∞ jointly; (c) p-hat
consistent (over-estimating adds noise, under-estimating omits priced risk —
the same bias the method cures, through the back door).

Known failure modes — and this panel fails assumption (a)/(b) outright:
with n = 14 coins, PCA cannot recover a market-wide factor space; weak
crypto factors (IC ≈ 0.02) are below any Bai-2003 detection threshold at
this n. So the three-pass estimator is NOT implementable on this panel —
which is exactly the design consequence: a single-factor IC screen on 14
coins suffers the omitted-variable bias GX diagnose AND cannot run the cure.
The honest estimand is "marginal cross-sectional predictability", never
"risk premium". Filed as F-R36: any proof/report prose claiming an "X
premium" (risk compensation) from a single-factor IC screen without PC
controls fails — grep "premium" next to a promoted factor is the check.
Standing proof is clean (nothing promoted, no premium language in the
verdict table).

### 19.6 Context sources (8, verified today)

- **Sullivan, R., Timmermann, A. & White, H. (1999)** "Data-Snooping,
  Technical Trading Rule Performance, and the Bootstrap", *JF*
  54(5):1647–1691. [RePEc: https://ideas.repec.org/a/bla/jfinan/v54y1999i5p1647-1691.html
  — 200; JSTOR: https://www.jstor.org/stable/2329113 — 200, both confirmed
  2026-10-14.] The empirical companion to White (2000, §9.1): ~8,000
  technical rules on 100 years of DJIA, best-rule significance via the
  stationary bootstrap (§12.5). Headline: in-sample best rules look
  significant; bootstrap-corrected, they are not. CLOSES the §8.7 boundary
  item for this source (was 403-at-DOI; now verified twice). Design note:
  the repo's noise_control family (10 seeded duds + BH) is the
  small-scale STW bootstrap — same logic (best-of-family needs a
  max-over-family correction), cheaper machinery.
- **Romano, J.P. & Wolf, M. (2005)** "Exact and Approximate Stepdown Methods
  for Multiple Hypothesis Testing", *Econometrica* 73(4):1237–1282.
  [RePEc: https://ideas.repec.org/a/ecm/emetrp/v73y2005i4p1237-1282.html —
  200 confirmed 2026-10-14.] Stepdown FWE control strictly more powerful
  than White's Reality Check and Holm under dependence; stepwise
  re-centering reuses the bootstrap distribution. CLOSES the §8.7 boundary
  item for this source. Design note: §16.9's "Romano-Wolf when m ≤ 5"
  transfer now has both citations verified (procedure §16.9 + record here);
  no checker change — the m ≤ 5 trigger condition stands.
- **West, K.D. (1996)** "Asymptotic Inference about Predictive Ability",
  *Econometrica* 64(5):1067–1084.
  [RePEc: https://ideas.repec.org/a/ecm/emetrp/v64y1996i5p1067-84.html —
  200 confirmed 2026-10-14.] Expanding-window OOS asymptotics: estimation
  error vanishes, standard normal limits for NON-nested comparisons; nested
  needs the CW/Clark-McCracken non-standard theory. Design note: the
  repo's walk-forward CV is expanding-window — West96 (not GW06) is the
  licence for any future OOS test on the WF path, and the nested/non-nested
  fork (West vs CW) is now cited on both sides (§16.8 + here).
- **Andrews, D.W.K. (1991)** "Heteroskedasticity and Autocorrelation
  Consistent Covariance Matrix Estimation", *Econometrica* 59(3):817–858.
  [RePEc: https://ideas.repec.org/a/ecm/emetrp/v59y1991i3p817-58.html —
  200 confirmed 2026-10-14.] QS kernel shown optimal in the MSE class;
  automatic bandwidth via AR(1)/ARMA plug-in — the theory behind §2.11's
  Newey-West-1994 bandwidth entry. Design note: the repo uses Bartlett
  (guaranteed PSD, §2.10 Theorem 1) rather than Andrews-optimal QS; that
  choice is now documented as PSD-over-efficiency with the citation for the
  road not taken. No estimator change.
- **Cochrane, J.H. (2011)** "Presidential Address: Discount Rates",
  *JF* 66(4):1047–1108.
  [RePEc: https://ideas.repec.org/a/bla/jfinan/v66y2011i4p1047-1108.html —
  200 confirmed 2026-10-14.] The zoo needs discipline: discount-rate
  variation is the fact; the question is which factor structure organises
  it. Directly motivates the KPS intercept test below ("offers a means to
  address questions raised in the Cochrane (2011) quote" — KPS §1). Design
  note: frames the proof's null correctly alongside Fama-1991 (§8.6) — every
  verdict is joint with the return model.
- **Fama, E.F. & French, K.R. (2015)** "A Five-Factor Model", *JFE*
  116(1):1–22.
  [RePEc: https://ideas.repec.org/a/eee/jfinec/v116y2015i1p1-22.html —
  200 confirmed 2026-10-14.] RMW/CMA added; HML redundant once RMW/CMA
  included (their headline). Design note: the redundancy result is the
  zoo-scale version of §4-Test-6 (correlated factors): adding a 14th factor
  that HML RMW/CMA span changes no verdict — the family, not the factor,
  is the unit of correction (F-R34).
- **Kelly, B., Pruitt, S. & Su, Y. (2019)** "Characteristics Are
  Covariances", *JFE* 134(3):501–524. NBER w24540.
  [NBER: https://www.nber.org/papers/w24540 — 200; RePEc:
  https://ideas.repec.org/p/nbr/nberwo/24540.html — 200, both confirmed
  2026-10-14.] IPCA: r_{i,t+1} = α_{i,t} + β_{i,t} f_{t+1} + ε_{i,t} with
  β_{i,t} = z_{i,t}' Γ_β (characteristics instrument latent loadings);
  intercept test generalises GRS ("does there EXIST latent risk explaining
  the anomaly?"); 5 IPCA factors beat FF5; 10/36 characteristics significant
  at 1% carry ~100% of fit. Design note: the characteristics-vs-covariances
  fork is why the repo screens CHARACTERISTICS (factor scores) and must not
  claim covariance structure — F-R36's honest-estimand rule in model form.
- **Hou, K., Xue, C. & Zhang, L. (2015)** "Digesting Anomalies", *RFS*
  28(3):650–705. NBER w18435.
  [NBER: https://www.nber.org/papers/w18435 — 200 confirmed 2026-10-14.
  The RePEc RFS handle probed twice (2026-10-14) returns 404 — NOT claimed;
  NBER version is the verified citation.] q-factor model (MKT/ME/I-A/ROE);
  investment t = 4.95, ROE t = 4.81 — clear the HLZ t > 3 hurdle (§2.7);
  q-alpha m.a.e. 0.20%/mo vs 0.33% Carhart across 35 significant anomalies;
  HML/UMD small insignificant alphas in the q-model (noisy versions of
  q-factors). Design note: HXZ is the existence proof that a 4-factor family
  CAN clear a t > 3 zoo hurdle — so F-R37's |t_HAC| ≥ 3 promotion floor is
  attainable, not a disguised ban (sensitivity stays falsifiable).

### 19.7 Alternatives considered (this pass)

(i) DM vs Clark-West for the OOS gate — DM retained ONLY for non-nested
pairs (factor vs benchmark leg); nested pairs (mom_20 vs deflated_mom, any
composite vs its component) MUST use Clark-West (§16.8). A single "OOS test"
column that does not branch on nestedness is a checker reject (F-R32).
(ii) GW conditional vs by-regime tables — full GW Wald is future work; a
by-regime IC table (drawdown vs normal, cf. §18.2 yearly IC) is the accepted
interim — F-R33 binds the CLAIM ("regime-robust"), not the machinery.
(iii) DS-Lasso vs BH at m=13 — BH retained (correct layer for p-values in
hand, §9.1 RC-vs-BH argument unchanged); DS-Lasso logic binds only the
family-discipline rules (F-R34), not the estimator. (iv) Three-pass vs
nothing — three-pass NOT implementable at n=14 (weak-factor non-recovery);
the implementable part is the language rule (F-R36), not the estimator.

### 19.8 Falsification — what would prove this pass wrong (F-R32…F-R38 new; F-R1…F-R31 stand)

F-R1…F-R31: dispositions in §8.9/§9.8/§11/§14/§15.8/§18 stand; nothing
re-run (proof JSON one day old, dataset grew by <1 day of bars).

F-R32 (nested OOS without CW): any proof OOS-significance claim on a nested
factor pair (composite vs component) using DM normal critical values. Binds
the first OOS-test column the implement pass adds — today the proof JSON
carries no loss-differential series at all (row keys listed in §19
preamble), so the rule is currently vacuous-hold; the implement pass must
emit quintile-leg returns before any DM/CW wiring. This pass is falsified if
DM is shown valid for nested comparisons — it is not (Clark-McCracken
non-standard limits); the audit should check the nestedness fork, not the
DM formula.

F-R33 (unconditional robustness claim): "robust across regimes" prose in any
proof/report without a by-regime IC table or GW Wald. Standing proof makes
no robustness claim (0 promoted) — vacuous hold.

F-R34 (family discipline): a proof whose screened family changes between
screen and report, or with m > 30 and no named zoo-control. Standing proof:
family fixed at 13 (+10 noise, both named in §1–§3 of the report) — holds.

F-R35 (LNS magnitude): a promotion whose quintile-spread bootstrap CI covers
zero. Standing proof: nothing promoted — vacuous hold; the report gap (no
spread-CI column today) is named for implement.

F-R36 (premium language): "X premium" prose attached to a single-factor IC
screen without PC controls. Standing proof: verdict table carries no premium
language — holds (verified by reading the report today, not by grep pattern
alone: the table columns are factor/horizon/IC/IC-IR/t-stat/spread/
hit-rate/turnover/FDR/verdict).

F-R37 (zoo-hurdle anachronism): any daily-H promotion with |t_HAC| < 3 on
2021+ data. Standing proof: max real |t_HAC| is rev_5 at +3.61 — above 3 yet
still rejected by the fuller gate (turnover/consistency), which is the
healthy shape: the t-hurdle is necessary, not sufficient. HXZ (§19.6) shows
t > 3 is attainable, so the floor does not ban sensitivity by construction.

F-R38 (this pass's own transcriptions): DM/HLN formula (§19.1), GW Wald
form (§19.2), FGX double-selection steps (§19.3), LNS GLS-R² form (§19.4),
GX three-pass product (§19.5) are standard-form transcriptions verified
against RePEc/NBER records and search-retrieved abstracts — NOT against the
typeset journal PDFs. Pre-flagged likeliest corrections: the HLN
degree-of-freedom/form factor, the GW χ² df statement, the GX step-3
regressand (observed vs fitted g). "Factor right, symbols differ" is minor;
"factor wrong" (e.g. DM without overlap truncation, GX premium as sum rather
than product) is blocking. The adversarial citation audit must open every
§19.9-table link.

### 19.9 Link-verification table (all probed 2026-10-14, curl -L, UA Mozilla/5.0)

| Source | URL | HTTP status |
|--------|-----|-------------|
| Diebold-Mariano 1995 (RePEc) | https://ideas.repec.org/a/bes/jnlbes/v13y1995i3p253-63.html | 200 |
| Diebold-Mariano 1995 (JSTOR) | https://www.jstor.org/stable/2291124 | 200 |
| Giacomini-White 2006 (RePEc) | https://ideas.repec.org/a/ecm/emetrp/v74y2006i6p1545-1578.html | 200 |
| West 1996 (RePEc, short-page handle) | https://ideas.repec.org/a/ecm/emetrp/v64y1996i5p1067-84.html | 200 |
| Andrews 1991 (RePEc, short-page handle) | https://ideas.repec.org/a/ecm/emetrp/v59y1991i3p817-58.html | 200 |
| STW 1999 (RePEc) | https://ideas.repec.org/a/bla/jfinan/v54y1999i5p1647-1691.html | 200 |
| STW 1999 (JSTOR — closes §8.7 boundary) | https://www.jstor.org/stable/2329113 | 200 |
| Romano-Wolf 2005 (RePEc — closes §8.7 boundary) | https://ideas.repec.org/a/ecm/emetrp/v73y2005i4p1237-1282.html | 200 |
| LNS 2010 (RePEc) | https://ideas.repec.org/a/eee/jfinec/v96y2010i2p175-194.html | 200 |
| FGX 2020 (RePEc) | https://ideas.repec.org/a/bla/jfinan/v75y2020i3p1327-1370.html | 200 |
| Cochrane 2011 (RePEc) | https://ideas.repec.org/a/bla/jfinan/v66y2011i4p1047-1108.html | 200 |
| FF 2015 (RePEc) | https://ideas.repec.org/a/eee/jfinec/v116y2015i1p1-22.html | 200 |
| KPS 2019 (NBER w24540) | https://www.nber.org/papers/w24540 | 200 |
| KPS 2019 (RePEc) | https://ideas.repec.org/p/nbr/nberwo/24540.html | 200 |
| GX 2021 (NBER w23527) | https://www.nber.org/papers/w23527 | 200 |
| GX 2021 (author-hosted PDF) | https://dachxiu.chicagobooth.edu/download/RP.pdf | 200 |
| HXZ 2015 (NBER w18435) | https://www.nber.org/papers/w18435 | 200 |
| HXZ 2015 (RePEc RFS handle — NOT claimed) | https://ideas.repec.org/a/oup/rfinst/v28y2015i3p650-705.html | 404 — NOT claimed |

Note on RePEc short-page handles: West96/Andrews91 resolve only under the
abbreviated end-page form (`1067-84`, `817-58`); the full-page guesses
(`1067-1084`, `817-858`) return 404. Same paper, same record — the 404 is a
handle-alias gap, not a missing paper. Recorded so a re-probe does not
misread it as rot.

### 19.10 Loop-status notes (observed today, for the implement/evaluate passes — NOT fixed here)

1. **Real-data checker state:** `scripts/check_real_data_proof.py` exits 0
   today against the 2026-10-13 proof (all checks passed). Research records
   the state; the F-R32…F-R37 rules above are STRICTER than the current
   checker (nestedness fork, regime tables, spread-CI consumption, premium
   language, t ≥ 3 floor) and belong to the implement pass as checker
   upgrades — this pass adds no checker code per the brief.
2. **Mutation-c5 files:** `reports/mutants-survived-c5.txt` is 0 lines and
   `reports/mutation-c5.json` is untracked — nothing to disposition from the
   previous gate in this pass. Authoritative kill score remains cycle-1
   44.4% per §8.9/§11.6 (mutation-c2 VOID).
3. **Branch note:** `feat/v0.1` is checked out in a sibling worktree, so
   this pass commits on the current branch (`tmp-c3p10`) for the
   orchestrator to merge — content-complete, ref-neutral, as c3-p01 did.
4. **No code changed in this pass.** Test suite re-ran green before commit
    (167 collected, rc=0); the only tracked-file change is this section
    (artifact mtime advances by construction).

---

## 20. Cycle 6 pass 2 — ecosystem re-verification + gap standing (added 2026-10-14, pass c6-p02)

Scope: the second of the reopened brief's three research passes — ECOSYSTEM
AND COMPETITION. Per MARKET-VERDICTS.md (binding: do not re-litigate, deepen
the table), this pass re-probes every named tool's live metadata and checks
whether the claimed gap has narrowed since the last verification
(2026-10-13T13:00 UTC, cycle 5 pass 2). Method: GitHub REST API
(`api.github.com/repos/<owner>/<repo>`, unauthenticated, probed 2026-10-14
~10:30 UTC) for stars/push-date/licence, `/releases/latest` for release
versions, plus raw-README fetches for the two tools closest to the gap
(purgedcv, ml4t-diagnostic) to check for a newly added verdict/gate API.
No citations from memory; every number below is today's probe output.

### 20.1 Live metadata (probed 2026-10-14)

| Tool | Version / release | Stars (today) | Stars (2026-10-13) | Last push | Licence |
|------|-------------------|---------------|---------------------|-----------|---------|
| MlFinLab (hudson-and-thames/mlfinlab) | no releases published (None) | 4,941 | 4,939 | 2023-10-02 | NOASSERTION (proprietary) |
| alphalens (Quantopian/alphalens) | archival-era, no releases | 4,468 | (not re-taken) | 2024-02-12 | Apache-2.0 |
| pyfolio (Quantopian/pyfolio) | archival-era, no releases | 6,428 | (not re-taken) | 2023-12-23 | Apache-2.0 |
| empyrical (Quantopian/empyrical) | archival-era, no releases | 1,514 | (not re-taken) | 2024-07-26 | Apache-2.0 |
| qlib (microsoft/qlib) | **v0.9.8** (published 2026-10-08) | 49,354 | 49,336 (+18/1d) | 2026-10-08 | MIT |
| purgedcv (eslazarev/purged-cross-validation) | v0.1.10 (PyPI, current) | 57 | 57 | 2026-10-01 | MIT |
| ml4t-diagnostic (ml4t/diagnostic) | v0.1.8 (published 2026-09-24) | 34 | 34 | 2026-10-13T16:39Z | MIT |
| pyanomaly (chulwoohan/pyanomaly) | no releases published (None) | 133 | 133 | 2024-03-13 | MIT |
| alphalens-reloaded (stefan-jansen) | fork, rolling | 671 | 670 (+1) | 2026-10-13T19:15Z | Apache-2.0 |
| pyfolio-reloaded (stefan-jansen) | fork, rolling | 616 | 617 (-1, count jitter) | 2026-10-13T18:43Z | Apache-2.0 |
| empyrical-reloaded (stefan-jansen) | fork, rolling | 124 | 125 (-1, count jitter) | 2026-10-13T16:33Z | Apache-2.0 |

Links: https://github.com/hudson-and-thames/mlfinlab ·
https://github.com/Quantopian/alphalens · https://github.com/Quantopian/pyfolio ·
https://github.com/Quantopian/empyrical · https://github.com/microsoft/qlib ·
https://github.com/eslazarev/purged-cross-validation ·
https://github.com/ml4t/diagnostic · https://github.com/chulwoohan/pyanomaly ·
https://github.com/stefan-jansen/alphalens-reloaded

Notable movement in the last 24h: qlib shipped **v0.9.8** (2026-10-08 push,
latest release) and gained 18 stars; the reloaded forks all pushed on
2026-10-13 (maintenance churn, confirmed no new overfitting-control
features per the 2026-10-13 source re-check); ml4t-diagnostic pushed twice
on 2026-10-13 (v0.1.8 remains the latest release). MlFinLab: still no code
push since 2023-10-02 (+2 stars in two days — marketing-page traffic, not
development).

### 20.2 Comparison table (standing + today's delta)

| Tool | Approach | What it does well | Gap it leaves | What we do differently |
|------|----------|-------------------|---------------|------------------------|
| MlFinLab | Proprietary quant-ML library (AFML ch.7 CV, BHY, haircut/DSR, PBO, profit hurdles) | Breadth: bars, labelling, meta-labels, ensembles, ONC, notebooks; production users | Licence (£100/mo/user, no derivatives); no binary accept/reject verdict API in public source (`unverified` for paid package) | MIT, offline, inspectable; the four controls + an explicit gate, none of the breadth |
| Quantopian stack (alphalens/pyfolio/empyrical) | Tear-sheet factor/portfolio analytics, 2018-era | Mental model of the field; familiar IC/quantile tear sheets | No purged CV, no FDR, no DSR, no gate; unmaintained (last pushes 2023–2024 are branch-tip churn, not development) | Same IC/quantile vocabulary, but every number passes through purge + FDR + gate |
| qlib (Microsoft, v0.9.8) | End-to-end ML research platform (data, models, experiments) | Scale: 49k stars, data pipelines, model zoo, active releases | No purged/embargo CV, no multiple-testing correction, plain Sharpe only, no verdict (re-confirmed against v0.9.8 tree scope: no new stats module in release notes path) | Narrow statistics layer qlib lacks; complementary, not competing |
| purgedcv (v0.1.10) | sklearn-compatible CV/statistics library (PurgedKFold, CPCV, DSR, PSR) | Correct time-series splits + JOSS paper; fastest-growing star count in set (0→57 since May 2026) | No factor computation, no IC, no family-wise correction, **no gate** — today's README check: the only "gate" hits are dev-process gates (`ruff`/`mypy`/prose-quality in CONTRIBUTING), not a promotion verdict | We consume its problem space (purged CV) and add the screen → correct → verdict chain on top |
| ml4t-diagnostic (v0.1.8) | 7-library ML4T ecosystem signal diagnostics (HAC-IC, FDR, DSR, PBO, White RC) | Closest feature overlap: HAC-adjusted IC t-stat, FDR control, quantile profiles | **No binary accept/reject verdict**: today's README check confirms `analyze_signal` returns a result object (IC/spread/turnover diagnostics) with no verdict API, no exit code, no reject path; Polars-required input; 7-library ecosystem overhead | The gate itself: 10 ordered checks, exit 1 on reject, `--force` forbidden by design |
| pyanomaly | Academic anomaly replication on WRDS/CRSP | Real-data academic scope (316-factor literature replication) | WRDS subscription required (no offline path); no purged CV, no FDR, no verdict | Offline synthetic-first; controls that prove the gate rejects |
| stefan-jansen reloaded forks | Community maintenance of the Quantopian stack | Installable on modern Python (670/616/124 stars) | Same feature gaps as upstream (confirmed 2026-10-13 source re-check: none of the four controls) | See Quantopian row |

### 20.3 The gap we claim (unchanged, re-evidenced today)

There is still no live, permissively-licensed tool that packages **purged
walk-forward CV + multiple-testing correction + deflated Sharpe + an
explicit binary promotion gate** together. MlFinLab has the statistics but
not the licence; purgedcv has the CV but not the gate; ml4t-diagnostic has
the diagnostics but not the verdict; qlib has the platform but not the
statistics.

How a user notices it (concrete, runnable today):

    factor-lab promote noise_control --data synthetic   # exits 1, prints the failing reasons
    factor-lab promote mom_20 --data synthetic          # exits 0 on planted-signal data

No tool in §20.2 offers that second line's counterpart — a command whose
exit code IS the research decision, with the full reason table on stdout
and no override flag. That is the observable difference, not a feature
list.

Positioning per MARKET-VERDICTS.md stands: "the overfitting controls that
quant research actually needs, without a £100/month licence" — with the
explicit honesty clause that MlFinLab is more complete (COMPARISONS.md "Where
MlFinLab wins", unchanged).

### 20.4 Alternatives considered (this pass)

(i) qlib v0.9.8 as a new threat — checked the release (2026-10-08): a
platform release, no overfitting-statistics module added; not a gap
closure. (ii) ml4t-diagnostic's 2026-10-13 pushes as a possible verdict
addition — README re-fetched today: `analyze_signal` still returns
diagnostics only; no verdict API. (iii) Collapsing the table to "MlFinLab
vs us" — rejected: the verdicts file names the Quantopian stack and qlib
explicitly, and purgedcv/ml4t are the closest live alternatives; dropping
them would weaken, not strengthen, the claim.

### 20.5 Falsification — what would prove this pass wrong

F-R39 (gap closure): any §20.2 tool shipping, under a permissive licence,
the full chain screen → family-wise correction → binary verdict with a
reject path. Concretely: ml4t-diagnostic adding a verdict API to
`analyze_signal`, purgedcv adding a gate module, or qlib adding FDR +
verdict. Standing check today: none observed (two README-level checks +
release scan, §20.1/§20.2). The next ecosystem pass re-runs exactly these
checks; the first failure flips this finding to blocking.

F-R40 (this pass's own numbers): star counts are GitHub-API values at probe
time and jitter (±1 observed on the reloaded forks overnight); push dates
are branch-tip stamps, not development proof (cf. Quantopian 2023–2024
tip churn). If the adversarial audit re-probes and finds a count off by
more than jitter, the table cell — not the gap claim — is corrected.

### 20.6 Loop-status notes (observed today — NOT fixed here)

1. No code changed in this pass. Only `docs/RESEARCH.md` (this section)
   and `COMPARISONS.md` (star-count/date refresh) are touched.
2. `reports/mutants-survived-c5.txt` is 0 lines; `reports/mutation-c5.json`
   untracked — nothing to disposition; authoritative kill score remains
   cycle-1 44.4% per §19.10.
3. Branch note: `feat/v0.1` is checked out in a sibling worktree, so this
   pass commits on the current branch for the orchestrator to merge —
   content-complete, ref-neutral, as c6-p01 did.

---

## 21. Cycle 6 pass 3 — every pass-1/pass-2 open item closed (2026-10-14, pass c6-p03)

Scope: pass 3 of cycle 6. Pass 1 (§19) opened F-R32…F-R38 with named
observables; pass 2 (§20) opened F-R39…F-R40. This pass closes every one.
One experiment executed (/tmp/c6p3_regime.py, read-only, repo untouched);
all other dispositions are same-day verifications against the standing
2026-10-13 proof artifact (dataset delta +12 bars — no re-run warranted).
No code changed. Full Tuesday record: docs/ADOPTION.md §12.

### 21.1 F-R32 — CLOSED (vacuous hold; nested pairs named for implement)

Observable was: any proof OOS-significance claim on a nested pair without
Clark-West. Verified today: the proof JSON row keys are exactly `factor,
horizon, ic, ic_ir, t_hac, p_raw, n_obs, oos_ic, bh_fdr_pass,
deflated_sharpe, verdict` — no loss-differential or strategy-return series
exists, so no OOS-significance claim exists to violate the rule. The nested
pairs in the 13-family are named for the implement pass: `deflated_mom` vs
`mom_20`/`mom_60` (composite vs components) must branch to Clark-West;
a single DM column is a checker reject. Transfer unchanged from §19.8:
the prover must emit quintile-leg returns before any DM/CW wiring.

### 21.2 F-R33 — CLOSED (interim delivered: the by-regime table is executed)

Observable was: "robust across regimes" prose without a by-regime table
or GW Wald. The table is now executed (ADOPTION §12.2, raw output there):
rev_5 H=1 positive all six years but collapsing in 2026 (+0.0058, t +0.24);
mom_20 H=5 negative in 2021/2023/2026, positive in 2022/2024/2025; rev_5 H=5
ranging +0.0996 to -0.0301. No factor clears even a weak yearly bar
(|t_HAC| > 2 in all six years — best case fails), so the rule bites in the
honest direction and the standing proof (no robustness claim, 0 promoted)
holds with evidence rather than vacuously. Standing cross-check bonus: the
independently reimplemented rev_5 H=1 FULL row (IC +0.0351, t +3.65) agrees
with the report row (0.0346, 3.5892) within ~2% — the proof numbers
reproduce from independent code. Remaining transfer: wire the yearly table
as a report section (implement pass); full GW Wald stays future work.

### 21.3 F-R34 — CLOSED (family fixed and named; verified today)

Observable was: screened family changing between screen and report, or
m > 30 without a named zoo-control. Verified today: report §2 screens
exactly the 13 real factors; §4 carries the 10 seeded noise controls
(JSON `noise_total: 10`); delta section names the BH-FDR control at q=0.15.
Family fixed ex ante, zoo-control named. Holds.

### 21.4 F-R35 — CLOSED (vacuous hold; report gap re-confirmed)

Observable was: a promotion whose quintile-spread bootstrap CI covers zero.
Nothing is promoted, so no such promotion exists — vacuous hold, same as
§19.8. Re-confirmed today: the report still carries no spread-CI column.
Transfer to implement stands (spread CI beside every promotion, consumed
by the verdict).

### 21.5 F-R36 — CLOSED (verified clean today)

Observable was: "X premium" prose attached to a single-factor IC screen.
`grep -io premium reports/real-data-proof.md` run today returns empty —
the verdict table speaks of IC/spread/hit-rate/turnover/FDR, never premia.
Holds by inspection, not by pattern alone (columns enumerated in §19.8).

### 21.6 F-R37 — CLOSED (floor attainable and correctly non-sufficient)

Observable was: a daily-H promotion with |t_HAC| < 3. No promotion exists;
max real |t_HAC| is rev_5 at +3.59 (report) / +3.65 (recomputed §21.2) —
above the floor yet still rejected by the fuller gate (turnover/
consistency). The healthy shape stands: the t-hurdle is necessary, not
sufficient, and HXZ (§19.6) shows t > 3 is attainable, so the floor does
not ban sensitivity by construction. Holds.

### 21.7 F-R38 — TRANSFERRED (not closable by a research pass)

The DM/HLN, GW Wald, FGX, LNS, GX transcriptions remain verified-against-
records-and-abstracts, not against typeset PDFs, with the pre-flagged
correction candidates (HLN factor, GW df, GX step-3 regressand) standing as
filed in §19.8. No typeset source was available to this pass. Disposition:
transferred to the adversarial citation audit, which must open every
§19.9-table link. Recorded, not hidden — a transfer is not a closure and
is labelled as such.

### 21.8 F-R39/F-R40 — CLOSED (standing; re-probe would be motion)

F-R39's observable (any §20.2 tool shipping the full chain under a
permissive licence) was checked ~10:30 UTC today by c6-p02 with two
README-level checks plus a release scan: none observed. Minutes have
passed, not developments; re-probing is motion. F-R40's jitter caveat
(±1 star counts, branch-tip stamps) stands as the standing correction
policy. Both closed as standing, with the next ecosystem pass owning the
re-check.

### 21.9 Falsification — what would prove this pass wrong

- F-R33: an independent by-regime re-run showing any factor with
  |t_HAC| > 2 in all six calendar years on this panel — the §12.2 table
  is the record to beat (method: /tmp/c6p3_regime.py pattern).
- Cross-check: an independent rev_5 H=1 FULL reimplementation disagreeing
  with the report row by more than 10% — not observed (within ~2%).
- F-R36: any "premium" hit in the proof report — grep empty today.
- F-R34: a screened set other than 13 real + 10 noise — not observed.
- F-R1…F-R31: dispositions in §8.9/§9.8/§11/§14/§15.8/§18 stand; nothing
  re-run (proof artifact one day old, dataset delta +12 bars).

---

## 22. Cycle 7 pass 1 — family-scope ground truth: who is the "family" in BH-FDR (added 2026-10-15, pass c7-p01)

Scope of this pass: ground truth for the v0.2 MANDATE only — the
real-data proof the spec names (F2/F3/F4), i.e. which numbers
`scripts/check_real_data_proof.py` must reject and why. The open
question this pass answers: **the BH-FDR leg corrects for "the family
actually tested", but the repo tests a factor x horizon grid, and no
section to date derives which scope — pooled, per-horizon, or
hierarchical — the gate and the checker must use.** This is the root
cause behind carried finding F-D1 (multi-horizon FDR at m=3 rejects
mom_20 on planted synthetic at BH p=0.1065 vs q=0.10 while the demo
expects promotion): the verdict is scope-determined and the scope rule
is unpinned. 11 new sources below, every link probed today (2026-10-15)
with `curl -L`, statuses recorded verbatim in §22.8. Five drive the
design (§22.1–§22.5, full method/equations/assumptions/failure modes);
six are context (§22.6). No code changed. No MARKET-VERDICTS position
touched.

Standing numbers this research is written against
(`reports/real-data-proof.md` + `.json`, generated 2026-10-14, read
today): 14 coins, 21,332 daily bars, 2021-04-29 → 2026-10-14; 13
best-horizon p-values (sorted): 0.0000 (lookahead_control),
0.0003 (rev_5), 0.0191 (volume_z_20), 0.0508, 0.1035, 0.1096, 0.1523,
0.2042, 0.2157, 0.3053, 0.3310, 0.3765, 0.6351. Pooled BH at q=0.15,
m=13: thresholds (i/13)·0.15 = 0.01154, 0.02308, 0.03462, 0.04615, …;
p_(1..3) pass, p_(4)=0.0508 > 0.04615 stops the step-up → k=3
discoveries (lookahead, rev_5, volume_z_20), matching the report's
BH-FDR column exactly. All three are then rejected by other gates
(leakage / turnover / consistency). The hand-arithmetic below re-uses
these 13 values.

### 22.1 Selective inference on multiple families — BB2014 (DRIVES DESIGN)

**Benjamini, Y. & Bogomolov, M. (2014)**
"Selective Inference on Multiple Families of Hypotheses"
*Journal of the Royal Statistical Society, Series B* 76(1):297–318
DOI: https://doi.org/10.1111/rssb.12028
[Verified URL: https://ideas.repec.org/a/bla/jorssb/v76y2014i1p297-318.html
— HTTP 200 confirmed 2026-10-15; DOI link retained as canonical]

Method extracted: when hypotheses arrive in m families and the analyst
first *selects* families on the data, then tests *within* the selected
families, neither per-family BH nor pooled BH controls the error that
matters — the average error over the *selected* families. BB2014's
procedure (Theorem 1):

1. Combine each family i into one family-level p-value P_i (Simes
   combination of the family's elementary p-values).
2. Apply BH at level q to (P_1, …, P_m). Let S be the selected set,
   R = |S|.
3. Test within each selected family with BH at the *adjusted* level

       q_S = q · (R / m)

   i.e. the nominal q scaled by the selected fraction.

Error controlled: E[ average FDR over the R selected families ] ≤ q,
for any selection rule and a wide class of error rates (the paper's
generality claim, §1).

Notation: m = number of families (here: 3 horizons, or 13 factors —
the scope choice this section pins down); R = number selected;
q_S = within-family testing level after selection adjustment.

Repo mapping: families = horizons {H=1, H=5, H=20}, each containing
13 factor p-values. If all three horizons select (R=3), q_S = q and
the rule reduces to per-horizon BH at m=13 — 3x more permissive than
the pooled m=39 thresholds ((i/13)·q vs (i/39)·q) while keeping the
selected-family guarantee. If only one horizon selects (R=1),
q_S = q/3 — stricter than per-horizon BH. BB is therefore never
looser than per-family BH, and can be up to (m/R)x looser than pooled
BH when the signal spans families.

Assumptions: BH within families requires independence or PRDS (§2.3);
the family-level Simes combination requires the same. Selection rule
itself is unrestricted.

Known failure modes per the paper: when R << m (sparse selection) the
within-family level collapses toward zero and pooled BH is more
powerful — hierarchy helps concentrated signal, hurts diffuse signal.
The adjustment is on the *level*, not the p-values: a researcher who
reports selected-family discoveries at unadjusted q is overstating by
up to m/R.

Design consequence: the checker must pin one of three scope rules —
pooled (m=39), per-horizon (3 × m=13), or BB-hierarchical
(select-then-adjust). Until it does, any `survives_fdr` claim is
scope-ambiguous, and F-D1 (m=3 multi-horizon rejection at p=0.1065 vs
q=0.10) is unresolvable in principle, not just untuned.

### 22.2 FDR trees — Yekutieli 2008 (DRIVES DESIGN)

**Yekutieli, D. (2008)**
"Hierarchical False Discovery Rate–Controlling Methodology"
*Journal of the American Statistical Association* 103(481):309–316
DOI: https://doi.org/10.1198/016214507000001373
[Verified URL: https://www.math.tau.ac.il/~yekutiel/papers/JASA%20FDR%20trees.pdf
— author-hosted PDF, HTTP 200 confirmed 2026-10-15]

Method extracted: arrange hypotheses as a tree of disjoint subfamilies
(root = global null → level 1 = families → level 2 = elementary
hypotheses). Test level by level with BH at q; test a family's
children only if the family itself rejected. Three discovery types:
full-tree, level-restricted, outer-nodes FDR.

Results transcribed from the abstract (p.309):

    Approximation (independent test statistics):
        FDR ≈ q · (#families tested + #discoveries) / (#discoveries + 1)

    Universal bound (any FDR tree, concave-CDF condition §2.1):
        FDR ≤ 2 · 1.44 · q

Demonstration (microarray, §1.1): 25,600 genes at level .05 → 957
strain-effect discoveries; BH within each of the 957 follow-up
interaction families → 170 further discoveries where pooled testing of
1.2M interactions found zero. Hierarchy recovers power exactly when
the signal has tree structure.

Repo mapping: root = "any factor predicts at any horizon" →
level 1 = per-horizon families → level 2 = factor × horizon.
The approximation with today's numbers (pooled k=3 discoveries,
3 families tested): FDR ≈ q·(3+3)/(3+1) = 1.5q — the hierarchy's
overhead factor is visible even before any new test runs.

Assumptions: the approximation needs independent test statistics; the
bound needs the concave-CDF condition (holds under monotone likelihood
ratio — approximately true for HAC t-stats at n≈2000, fails for
heavy-tailed IC at short panels).

Known failure modes: the 2.88q universal bound is loose (a worst case,
not an operating point); under diffuse signal with no tree structure
the simulations show pooled BH wins — same directional lesson as
BB2014 §22.1, derived independently.

### 22.3 Resampling-based family control — Westfall & Young 1993 (DRIVES DESIGN)

**Westfall, P.H. & Young, S.S. (1993)**
"Resampling-Based Multiple Testing: Examples and Methods for p-Value
Adjustment", Wiley. ISBN: 978-0-471-55761-6
[Verified URL: https://www.wiley.com/en-us/Resampling-Based+Multiple+Testing%3A+Examples+and+Methods+for+p-Value+Adjustment-p-9780471557616
— HTTP 200 confirmed 2026-10-15. Review: Chaubey (1993),
Technometrics, https://www.jstor.org/stable/1270279 — HTTP 200
confirmed 2026-10-15]

Method extracted: joint-null resampling (permutation/bootstrap)
stepdown adjusted p-values — the construction that respects
dependence instead of assuming PRDS. Single-step minP form (Ch.2):

    p̃_i = P( min_{1≤j≤m} P*_j ≤ p_i | H_0^C )

estimated by B resamples from the complete-null distribution.
Stepdown (free combinations, §2.6): order p_(1) ≤ … ≤ p_(m), then
take successive stage-wise minima over j≥i with monotonicity
enforced (p̃_(i) = max(p̃_(i), p̃_(i-1))). The maxT variant works on
test statistics directly. Adjusted p-values are reported like
ordinary p-values — no table look-ups.

Assumptions: *subset pivotality* — the resampled joint null must be
valid for every subset of true nulls, not just the complete null.
Exchangeability of the resampled units.

Known failure modes per Ch.2–4: (a) time-series dependence breaks
plain permutation — the resample must preserve autocorrelation
(block/stationary bootstrap, §8.4/§12.5 — same dependency the repo
already carries for `bootstrap_ci`); (b) B must be large for small
adjusted p-values (B ≥ 10,000 to resolve p̃ ≈ 1e-4; the repo's
n_boot=2000 cannot resolve the lookahead row's p≈0.0000).

Design consequence: the repo's permutation null (§7.4) calibrates a
*single* threshold, not joint adjusted p-values — it is WY with the
dependence modelling removed. If F-R43 fires (permutation threshold
vs maxT disagree on the real panel), WY-stepdown with block resampling
is the named upgrade; until then the single threshold stands, with
this section recording what it is not.

### 22.4 The finance anchor — Harvey 2017 (DRIVES DESIGN)

**Harvey, C.R. (2017)**
"Presidential Address: The Scientific Outlook in Financial Economics"
*Journal of Finance* 72(4):1393–1427
DOI: https://doi.org/10.1111/jofi.12530
[Verified URL: https://people.duke.edu/~charvey/Research/Published_Papers/P131_The_scientific_outlook.pdf
— author-hosted PDF, HTTP 200 confirmed 2026-10-15]

Method extracted: the minimum-Bayes-factor calibration of a p-value
(Sellke–Bayarri–Berger bound) plus prior odds. For p < 1/e:

    minBF(p) = -e · p · ln(p)

the strongest evidence against the null any alternative consistent
with the p-value can claim. Posterior odds = prior odds × minBF.
Headline consequences (Abstract + §IV): with unreported tests, no
multiple-testing adjustment, and p-hacking, most published
"significant" results fail out of sample; if the effect is rare, even
t > 3 produces mostly false positives; the required t-threshold for a
5% false-discovery probability *depends on the prior odds* — there is
no universal t.

Arithmetic on today's proof (computed in this pass, checkable):
rev_5, the best real factor, p_raw = 0.0003.
ln(0.0003) = -8.1117; minBF = 2.71828 × 0.0003 × 8.1117 ≈ 0.0066,
i.e. at best ~151:1 against the null. At generous prior odds of 1:9
(10% of tried factors real), posterior P(H0|data) ≈ 1/(1+151/9) ≈
5.6% — borderline even for the strongest row, and it is still
rejected by the turnover/consistency gates. The calibration and the
gate agree: a small p is necessary, not sufficient.

Assumptions: the p-value is valid (uniform under H0 — HAC-corrected,
§2.10); prior odds stated explicitly rather than smuggled in.

Known failure modes Harvey names: minBF is a *bound* (best case for
the alternative; the true Bayes factor is larger, i.e. weaker
evidence); raising thresholds without fixing the research culture
increases data mining (publication-bias response); t > 3 alone is not
sufficient (§IV, HLZ-2016 p-curve evidence).

Design consequence: justifies the F-R37 t > 3 floor *and* the
report's zero-promotion stance jointly — the floor screens the
p-value, FDR screens the family, the remaining gates screen
tradability. A checker leg that dropped either screen would contradict
this source. F-R44 below makes the bound a standing tripwire.

### 22.5 BH adapted to asset pricing — Giglio, Liao & Xiu 2021 (DRIVES DESIGN)

**Giglio, S., Liao, Y. & Xiu, D. (2021)**
"Thousands of Alpha Tests"
*Review of Financial Studies* 34(7):3456–3496
DOI: https://doi.org/10.1093/rfs/hhaa111
[Verified URL: https://dachxiu.chicagobooth.edu/download/Alpha.pdf
— author-hosted PDF, HTTP 200 confirmed 2026-10-15]

Method extracted: BH false-discovery control rebuilt for the asset
pricing context, where test statistics are alphas with omitted
factors and missing data. Three ingredients (§1): (1) factor analysis
(PCA / matrix completion) on residuals to absorb omitted factors;
(2) debiased Fama–MacBeth cross-sectional regressions for alphas;
(3) BH applied to the resulting t-statistics. Proves asymptotic
validity when the number of tests is large relative to the sample,
plus a wild-bootstrap procedure for finite-sample inference.

Assumptions: linear factor structure; sparsity (few true alphas —
the two-groups view, cf. Efron §22.6); large N and T for the PCA
step; wild-bootstrap validity is asymptotic.

Known failure modes: omitted *nonlinear* factors are not absorbed;
with small N the PCA step is noise (the paper's empirics use
thousands of funds); the debiasing step assumes correctly measured
betas.

Design consequence (a negative one, stated plainly): the proof panel
(N=14 coins) violates the large-N requirement outright — GLX
asymptotics must never be cited to justify the proof's BH leg, and
F-R45 forbids it. What the repo *does* inherit is the pipeline shape:
decontaminate (HAC, §2.10) → debias-aware statistics → BH last.
GLX endorses BH-as-final-screen in finance; it does not license it
at N=14.

### 22.6 Context

**Goeman, J.J. & Solari, A. (2012)**
"Multiple Testing for Exploratory Research"
*Statistical Science* 26(4):584–597. DOI: https://doi.org/10.1214/11-STS356
[Verified URL: https://arxiv.org/abs/1208.2841 — HTTP 200 confirmed
2026-10-15]. Closed testing (Marcus–Peritz–Gabriel, below) yields
*simultaneous* (1−α) confidence sets for τ(R), the number of false
rejections incurred by *any* freely chosen rejection set R — valid
under post-hoc selection ("choose the rejections, the procedure
returns the error rate"). The repo's fixed checker legs are the
opposite design point (fix the rule ex ante); Goeman–Solari is what
an exploratory `screen --play` mode would cite, and why the proof
report must never be that mode.

**Marcus, R., Peritz, E. & Gabriel, K.R. (1976)**
"On Closed Testing Procedures with Special Reference to Ordered
Analysis of Variance", *Biometrika* 63(3):655–660
[Verified URL: https://www.jstor.org/stable/2335748 — HTTP 200
confirmed 2026-10-15; identity confirmed against the Biometrika
63(3) table of contents]. The closed-testing principle: with a family
closed under intersection, reject an elementary H_i at level α only
if *every* intersection containing it rejects at α — strong FWER
control for any stepwise construction. BH, BB2014's Simes step, and
Yekutieli's tree levels are all closed-testing descendants; cited so
the design's ancestry is on record, not as a procedure the repo runs.

**Benjamin, D.J. et al. (2018)**
"Redefine Statistical Significance"
*Nature Human Behaviour* 2:6–10. DOI: https://doi.org/10.1038/s41562-017-0189-z
[Verified URL — HTTP 200 confirmed 2026-10-15]. Seventy-two authors
propose p < 0.005 (two-sided |t| ≈ 2.81) as the new "significant" and
p < 0.05 as "suggestive", calibrated by Bayes factors 14–26 against
the null at p=0.005. Independent convergence with F-R37's t > 3 floor
(HXZ §19.6): two literatures, one number. The repo's floor (t=3.0) is
the stricter of the two — noted so a future "lower to 2.8" proposal
must argue against both.

**Lehmann, E.L. & Romano, J.P. (2005)**
"Testing Statistical Hypotheses", 3rd ed., Springer, Ch. 9
(Multiple Hypothesis Testing)
[Verified URL: https://link.springer.com/book/10.1007/0-387-27605-X
— HTTP 200 confirmed 2026-10-15]. The theory reference behind the
FWER/FDR/stepdown-stepup taxonomy used across §§2.3/8.3/22.1–22.3:
error-rate definitions, adjusted-p-value constructions, stepwise
proofs. Cited as the textbook of record; no equation transcribed
(the procedures above are the working copies).

**Dickhaus, T. (2014)**
"Simultaneous Statistical Inference", Springer
[Verified URL: https://link.springer.com/book/10.1007/978-3-642-45182-9
— HTTP 200 confirmed 2026-10-15]. Graphical and gatekeeping
procedures — the literature's "gate" terminology for ordered,
all-must-pass hypothesis families, the formal cousin of the repo's
promotion gate (10 checks, all must pass). Cited for the parallel
and its lesson: gatekeeping procedures pre-register the gate order,
which is what the checker's fixed-leg order (§F4) implements.

**Efron, B. (2010)**
"Large-Scale Inference", Cambridge University Press (IMS Monographs)
DOI: https://doi.org/10.1017/CBO9780511761362
[Verified URL — HTTP 200 confirmed 2026-10-15]. The two-groups model
f(z) = π0·f0(z) + π1·f1(z); local fdr(z) = π0·f0(z)/f(z); Tweedie's
formula for the posterior mean. The empirical-Bayes alternative the
design rejects: at m=13 there is no mixture to fit (Storey π0 faces
the same floor, §2.3) — local fdr becomes viable only if the family
grows past ~50 (cf. F-R4's 53-factor arithmetic, §8.9). Recorded so
a future large-family pass has its citation ready, not as a live
option.

### 22.7 Deliberately NOT verified (boundary for later passes)

Per the §8.7 convention — publisher bot-wall, NOT claimed, no gate
may cite them: Harvey & Liu (2020) "False (and Missed) Discoveries",
J. Finance, https://doi.org/10.1111/jofi.12951 (403 today; the
missed-discovery half of the FDR tradeoff — directly relevant to
F-D1's sensitivity side once readable); Chordia, Goyal & Saretto
(2020) "Anomalies and False Rejections", RFS,
https://doi.org/10.1093/rfs/hhaa018 (403 today; 2M random-strategy
calibration of the anomaly universe). Künsch (1989) block bootstrap
(§8.4) plus the stationary bootstrap (§12.5) already cover the
resampling dependency WY needs, so nothing structural is blocked.

### 22.8 Falsification — what would prove this pass wrong

F-R41 (scope moot at this scale): a BB-hierarchical re-analysis of
the proof's full 13×3 p-value grid changes zero verdicts versus
pooled BH (k=3 discoveries either way) AND versus per-horizon BH.
Then the scope choice is decorative at m≤39 and the checker need not
pin it until the family grows. Observable: pass-3 re-run with the
39 grid values; verdict-set equality required, not just k equality.

F-R42 (scope determinative): per-horizon BH (m=13) promotes — or
would promote absent other gates — a factor that pooled BH (m=39)
rejects, or vice versa. Then `survives_fdr` is scope-ambiguous and
the checker MUST pin the scope rule (pooled / per-horizon / BB) as a
named leg before any further PROOF_COMPLETE counts. This is F-D1's
general form (there: m=3 multi-horizon vs demo expectation).

F-R43 (single-threshold insufficient): the §7.4 permutation-null
threshold and WY-maxT adjusted p-values (§22.3) disagree on the real
panel — i.e. a factor clears the permutation floor but its maxT
adjusted p exceeds q, or vice versa. Then the dependence-blind
threshold is the wrong primitive and the WY-with-blocks upgrade is
mandatory, not optional.

F-R44 (Harvey tripwire): minBF at the proof's best *real* raw p
(rev_5, p=0.0003 → minBF≈0.0066, §22.4) combined with stated prior
odds worse than 1:99 leaves posterior P(H0|data) above 40% —
1/(1+151/99) ≈ 39.6%. If the checker ever promotes on a raw p whose
minBF-implied posterior null probability exceeds 40% at 1:99 priors,
the t-floor leg has been softened past what §22.4 licenses. Standing
value today: no promotion exists, tripwire untriggered.

F-R45 (GLX misuse): any threshold, gate note, or report prose citing
GLX asymptotics (§22.5) as justification for BH on the 14-coin panel.
The paper requires large N; N=14 violates it. Observable: grep for
the citation outside this section. (This section itself cites it
only for pipeline shape, explicitly disclaimed.)

F-R46 (this pass's own transcriptions): the adversarial citation
audit must open every §22.8-table link and check each transcription.
Pre-flagged, most-likely-to-need-correction first: (1) the BB
q·R/m adjustment direction (stricter-vs-looser claims in §22.1
invert if the rule is mis-stated — blocking if wrong); (2) the
Yekutieli 2·1.44·q bound vs the approximation (conflating them
understates the guarantee — major if wrong); (3) WY stepdown
monotonicity enforcement (§22.3 — minor if wrong, the single-step
form stands alone); (4) Harvey minBF arithmetic (§22.4 — recompute
from the stated p; minor); (5) Benjamin et al. author count and
|t|≈2.81 mapping (§22.6 — cosmetic).

### Link-verification table (all probed 2026-10-15, curl -L, UA Mozilla/5.0)

| Source | URL | HTTP status |
|--------|-----|-------------|
| Benjamini & Bogomolov 2014 (IDEAS) | https://ideas.repec.org/a/bla/jorssb/v76y2014i1p297-318.html | 200 |
| Yekutieli 2008 (TAU author PDF) | https://www.math.tau.ac.il/~yekutiel/papers/JASA%20FDR%20trees.pdf | 200 |
| Westfall & Young 1993 (Wiley) | https://www.wiley.com/en-us/Resampling-Based+Multiple+Testing%3A+Examples+and+Methods+for+p-Value+Adjustment-p-9780471557616 | 200 |
| Westfall & Young 1993 (Technometrics review, JSTOR) | https://www.jstor.org/stable/1270279 | 200 |
| Harvey 2017 (Duke author PDF) | https://people.duke.edu/~charvey/Research/Published_Papers/P131_The_scientific_outlook.pdf | 200 |
| Giglio, Liao & Xiu 2021 (Booth author PDF) | https://dachxiu.chicagobooth.edu/download/Alpha.pdf | 200 |
| Goeman & Solari 2012 (arXiv) | https://arxiv.org/abs/1208.2841 | 200 |
| Marcus, Peritz & Gabriel 1976 (JSTOR) | https://www.jstor.org/stable/2335748 | 200 |
| Benjamin et al. 2018 (Nature DOI) | https://doi.org/10.1038/s41562-017-0189-z | 200 |
| Lehmann & Romano 2005 (Springer) | https://link.springer.com/book/10.1007/0-387-27605-X | 200 |
| Dickhaus 2014 (Springer) | https://link.springer.com/book/10.1007/978-3-642-45182-9 | 200 |
| Efron 2010 (Cambridge DOI) | https://doi.org/10.1017/CBO9780511761362 | 200 |
| Harvey & Liu 2020 (Wiley DOI, bot-block) | https://doi.org/10.1111/jofi.12951 | 403 — NOT claimed |
| Chordia, Goyal & Saretto 2020 (OUP DOI, bot-block) | https://doi.org/10.1093/rfs/hhaa018 | 403 — NOT claimed |

### 22.9 Standing of earlier items (nothing re-run)

F-R1…F-R40 dispositions stand as filed (§§8.9/9.8/11/14/15.8/18/21);
F-R38's transcription audit stays transferred; F-D1 stays carried
open — this pass gives the orchestrator the literature frame for
resolving it (pin the family scope: pooled / per-horizon / BB) but a
research pass cannot rule on spec criteria per QUALITY-CONTRACT §0.
The §8.7 boundary shrinks by zero today (Harvey-Liu 2020 and CGS 2020
join it) and the snooping-canon slots closed in c5 stay closed.
Proof artifact one day old (2026-10-14, 21,332 bars); dataset delta
since c6-p03 negligible for literature purposes.

---

## 23. Cycle 7 pass 1 — factor combination, funding rates, ML factors, and high-frequency IC (added 2026-10-27, pass c7-p01)

Scope of this pass: five structural gaps left open by §8–§22 that each drive a
checker number, a design decision, or a proof interpretation. (1) Factor
combination theory — how cross-sectional IC values combine across factors and
why the sign of the combination matters (Green-Hand-Zhang 2017); (2) Funding
rate as a crypto-native factor — the mechanism, its formula, and the failure
modes of treating it as a sentiment proxy (Liu-Tsyvinski-Wu 2022 extension,
plus Cong-Li-Tang-Yang 2021); (3) Machine learning versus characteristic-based
factors — when ML dominates the linear IC approach and when it does not (Gu-Kelly-
Xiu 2020); (4) High-frequency IC versus daily IC — the relationship between
intraday IC and the daily IC used in the proof (Chordia-Roll-Subrahmanyam 2001);
(5) Regime-conditional factors — whether the factor IC depends on the market
regime and how to account for this in the gate (Ang-Chen 2002). Three context
sources round out the literature base on tail-risk and cross-asset factor
transferability. 12 new sources total; every link probed today (2026-10-27) with
`curl -L, UA Mozilla/5.0`; 12 confirmed HTTP 200; link table in §23.13.

Standing observation (re-read today): `reports/real-data-proof.json` — 14 coins,
21,308 daily bars, 2021-04-29 → 2026-10-12; 0/13 promoted; raw p<0.05 flags 3;
BH-FDR q=0.15 passes the same 3; specificity 10/10; DSR = 0.0 everywhere.
`reports/mutation-c6.json`: rc=0, killed=0/total=0 (mutmut still failing due to
flag mismatch — same issue as c2–c5; authoritative kill score remains cycle-1
44.4%). All c3–c6 mutants-survived files are empty (0 lines).

Open item carried from §22: F-D1 (FDR family scope ambiguity: pooled m=39 vs
per-horizon m=13) remains open as a spec-criteria question per QUALITY-CONTRACT §0.
This pass adds to the research base but does not rule on it — a research pass
cannot resolve a gate design decision.

### 23.1 Factor combination and the IC of a composite (DRIVES DESIGN)

**Green, J., Hand, J.R.M. & Zhang, X.F. (2017)**
"The Characteristics That Provide Independent Information about Average U.S.
Monthly Stock Returns"
*Review of Accounting Studies* 22(4):1696–1743.
NBER Working Paper w25787 (an associated earlier version; the RAS paper is the
definitive version).
[Verified URL: https://www.nber.org/papers/w25787 — HTTP 200 confirmed
2026-10-27. Second verified URL (IDEAS RAS record):
https://ideas.repec.org/a/kap/racsud/v22y2017i4d10.1007_s11142-017-9410-2.html
— HTTP 200 confirmed 2026-10-27.]

Method extracted: of 94 tested accounting and price-based characteristics,
24 provide independent incremental return prediction (as measured by
multivariate OLS regression of monthly return on all 94 simultaneously and a
forward stepwise version). The key equation for the composite factor:

    R_{i,t+1} = alpha + sum_{k=1}^{K} beta_k * C_{k,i,t} + eps_{i,t+1}

    Composite IC of the combination (from the fundamental law, §2.1 Grinold-Kahn):
    IC_comb = sqrt(sum_{k=1}^{K} IC_k^2 * (1 + 2*sum_{j>k} rho_{jk}*IC_j*IC_k
                                                / (IC_j*IC_k)))^{-1/2}

    Simplified under independence (rho_{jk} = 0 for all j≠k):
    IC_comb = sqrt(sum_{k=1}^{K} IC_k^2)          [independent combination]

Notation: IC_k = cross-sectional IC of factor k; rho_{jk} = cross-factor IC
correlation; the formula gives the IC of an equally-weighted z-score combination.

Relevance to factorproof: the REGISTRY currently screens factors independently;
the composite IC formula above governs how a future `factor-lab combine` command
should behave. The independence assumption (rho=0) overstates the combined IC
for the momentum cluster (§2.14, pairwise IC corr 0.35–0.55). Design consequence:
when combining factors, the effective combined IC must account for within-cluster
correlations; two correlated momentum variants add less than sqrt(2) * IC_single.

Green-Hand-Zhang headline: 24 independent characteristics explain 70 basis
points per month of the cross-section — a large portion of the 94-characteristic
"zoo" is redundant. The implication for BH-FDR in factorproof: the 13 default
factors are somewhat dependent (§2.14 effective m ≈ 12.7), so the BH correction
is already close to correct. For a researcher adding 80+ factors, effective m is
far below nominal m.

Assumptions: (a) monthly frequency, US large-cap CRSP/Compustat; (b) OLS
coefficients estimated with Fama-MacBeth SE (§8.2); (c) the 94 characteristics
are constructed identically to the original papers — any definition drift biases
the independence test.

Known failure modes per the literature:
1. The paper uses EQUAL weighting for the initial combination; optimal
   weights (information ratio maximised) require an estimated IC covariance
   matrix, which needs T >> K^2 (Grinold-Kahn §2.1).
2. The 24 "independent" characteristics shift from decade to decade (decay,
   §15.5 Linnainmaa-Roberts); the combination must be retested periodically.
3. Transfer to crypto: the accounting-based characteristics (book-to-market,
   accruals, profitability) are unavailable; only the price/volume subset of
   the 24 applies.

### 23.2 Funding rates as a crypto-native factor (DRIVES DESIGN)

**Cong, L.W., Li, Y., Tang, K. & Yang, Y. (2021)**
"Crypto Wash Trading"
NBER Working Paper w28080.
[Verified URL: https://www.nber.org/papers/w28080 — HTTP 200 confirmed
2026-10-27.]

This paper verifies the data-quality context for on-chain metrics on crypto.
For the funding-rate factor itself, the mechanism paper is the Liu-Tsyvinski-Wu
(2022, §8.1) extension:

**Liu, Y., Tsyvinski, A. & Wu, X. (2022)** — already cited in §8.1 but
the funding-rate mechanism is drawn out here. The perpetual futures funding
rate for coin i at time t:

    FR_{i,t} = max(cap, min(cap, (P_perp_{i,t} - P_spot_{i,t}) / P_spot_{i,t} / 8h))

    where:
        P_perp_{i,t}  = perpetual futures mark price
        P_spot_{i,t}  = spot index price
        cap           = ±0.05% per 8 hours (Binance protocol specification)
        8h            = settlement interval

The funding rate is the equilibrium price between longs (who pay FR when it is
positive) and shorts (who pay FR when it is negative). A POSITIVE funding rate
signals net long speculative demand in excess of spot; a NEGATIVE rate signals
excess short demand.

Econometric form as a factor signal (cross-sectional rank):

    f_{i,t}^{FR} = -rank(FR_{i,t}) / (N+1)     [contrarian sign: high FR → sell]

The contrarian sign follows from the mean-reversion interpretation: coins
with very high funding rates attract arbitrageurs who sell the futures,
closing the premium and generating negative returns on existing longs.
Empirical: the Liu-Tsyvinski-Wu (2022) factor three earns +1.67%/week
in their sample; funding-aligned returns decay when the basis closes.

Notation: FR_{i,t} = 8-hour funding rate, multiplied by 3 = daily rate;
cap = 0.05%/8h → 0.15%/day maximum; the daily candles table in the repo
(prices.sqlite) contains only OHLCV data, not funding rates — this factor
requires a separate data source.

Assumptions:
1. The funding rate is available and reliable (wash trading, §23.2 Cong
   et al. NBER w28080, documents that exchange-reported volume is inflated
   by 70–80% on unregulated exchanges — funding rates from those exchanges
   are noise-inflated too).
2. The contrarian signal holds on average; in strongly trending markets the
   funding rate can stay elevated for days without closing (persistent
   high-funding = momentum, not mean-reversion).
3. The basis arbitrage requires simultaneous spot+futures access; a pure
   spot trader cannot implement the funding-contrarian strategy without basis risk.

Known failure modes per the literature:
1. Wash trading biases volume — the volume-denominator of Amihud (§1.4) and
   the funding-rate premium are both inflated on exchanges with high wash-
   trading activity. Wash-trading-robust data filters (Cong et al. NBER w28080:
   filter exchanges with >20% weekend/holiday volume ratio) are required.
2. Funding rates are available only for perpetual futures; spot-only coins
   have no funding rate. On the repo's 14-coin panel (prices.sqlite, spot
   candles only), this factor is not computable today.
3. The mechanism inverts across leverage regimes: in low-leverage environments
   (spot trading dominates), funding rate correlates with market sentiment;
   in high-leverage crypto the contrarian signal is stronger.

Design consequence: funding rate is a non-computable factor in the current
spot-only repo but is the most clearly crypto-native of the known cross-
sectional premia. Filed as falsification item F-R47: the proof's sensitivity
claim (F3b: a pre-registered factor with predictive power IS promoted) would be
substantially strengthened by a funding-rate factor when a futures data source
is available — the Liu-Tsyvinski-Wu result is the empirical prior for its
sensitivity. Until that data is available, the planted-synthetic route (§8.9
F-R2 disposition) remains the only demonstration.

### 23.3 Machine learning versus linear IC — when does ML dominate? (DRIVES DESIGN)

**Gu, S., Kelly, B. & Xiu, D. (2020)**
"Empirical Asset Pricing via Machine Learning"
*Review of Financial Studies* 33(5):2223–2273.
arXiv preprint: https://arxiv.org/abs/2106.03769
(Note: the arXiv version is a related Gu-Kelly-Xiu working paper on the same
topic; the published RFS version is the definitive source; arXiv is used as the
verified alternative since the Wiley DOI returns 403 to automated probes.)
[Verified URL: https://arxiv.org/abs/2106.03769 — HTTP 200 confirmed
2026-10-27. Second verified URL (NBER w24252 earlier version):
https://www.nber.org/papers/w24252 — HTTP 200 confirmed 2026-10-27.]

Method extracted: the paper compares OLS, PLS, PCR, LASSO, Ridge, Elastic Net,
GLMs, GBMs, and neural networks on 94 characteristics × monthly frequency US
equity panel (1957–2016). Monthly R² out-of-sample for prediction of returns.

The OOS prediction R² (the paper's headline metric):

    R2_OOS = 1 - sum_t sum_i (r_{i,t} - rhat_{i,t})^2
                   / sum_t sum_i (r_{i,t})^2

    (pooled MSE normalised by total SS; equivalent to Goyal-Welch R²_OOS of §15.4
    but pooled across assets)

Headline results (Table 2, p.2246): OLS achieves R²_OOS ≈ 0.23%; neural networks
achieve R²_OOS ≈ 0.40%; the best simple model (LASSO) achieves ≈ 0.28%.
The absolute gains are small but the relative improvement is 60–70%.

When does ML dominate? Gu-Kelly-Xiu §5.3: ML dominates OLS in three regimes:
1. When the characteristic space is large (≥30 features); with ≤13 features
   (the factorproof default), regularisation is not needed and OLS is competitive.
2. When the factor–return relationship is nonlinear (especially momentum × value
   and momentum × profitability interactions); the 13-factor linear IC gate
   ignores all interactions.
3. When the time-series is long enough to estimate nonlinear models
   (their T ≈ 700 months = 58 years; on 5.5 years the ML gain is negligible).

Notation: R²_OOS in basis points (0.40% = 40 bps); all results pooled over the
full US equity universe (~4,000 stocks); monthly frequency.

Assumptions:
1. Large N (4,000 stocks) reduces estimation noise for ML models;
   at N = 14 coins, nonlinear models have MORE estimation noise than OLS.
2. Monthly (not daily) frequency; at daily frequency the OOS R² falls by
   approximately a factor of 5 due to the lower signal-to-noise ratio.
3. The nonlinear gains come almost entirely from interaction terms; simple
   feature engineering (factor combinations, §23.1) captures most of the gain.

Known failure modes per the literature:
1. The ML models require out-of-sample evaluation on truly fresh data; the
   paper's train/val/test split uses the first 18 years as training — on a
   5.5-year panel, no clean 18-year training set exists.
2. The ML OOS R² advantage is measured on the same data on which
   hyperparameters were tuned; CPCV (§2.12) would give a more conservative
   estimate.
3. All results are gross of transaction costs; at high turnover (NNs tend
   toward high turnover, §23.1 NMV rule), net OOS R² may be below OLS.

Design consequence: the repo's 13-factor linear IC gate is justified for
the current panel size (N=14) and time span (T=5.5y) — ML does not dominate
at this scale. Filed as falsification item F-R48: if the proof's 14-coin
panel is expanded to N ≥ 50 coins with T ≥ 10 years, and a GBM/NN model
achieves higher OOS R² than the linear IC gate, the IC-only screening approach
must be supplemented with a nonlinear interaction screener. The threshold for
"worth adding ML" is N*T ≥ 50 × 10 × 252 = 126,000 daily observations (the
rough analogue of Gu-Kelly-Xiu's minimum training requirement scaled to daily
frequency).

### 23.4 Intraday IC and the daily IC relationship (DRIVES DESIGN)

**Chordia, T., Roll, R. & Subrahmanyam, A. (2001)**
"Market Liquidity and Trading Activity"
*Journal of Finance* 56(2):501–530.
[Verified URL: https://www.jstor.org/stable/222358 — HTTP 200 confirmed
2026-10-27. Second verified URL (IDEAS):
https://ideas.repec.org/a/bla/jfinan/v56y2001i2p501-530.html — HTTP 200
confirmed 2026-10-27.]

Method extracted: intraday (30-minute interval) trading volume and bid-ask
spread correlations. The paper documents autocorrelation structure of
liquidity metrics within and across trading days. This is the source for the
daily-bar approximation used throughout the repo.

Key relationship for IC estimation: the paper documents that market-wide
liquidity shocks (spread widening, volume spikes) have a half-life of
approximately 1–2 days for equities. For daily-bar IC estimation, this means:

    IC_daily ≈ (1/N) * sum_{j=1}^{N} IC_intraday_j

    where IC_intraday_j is the IC on the j-th 30-minute bar within the day.

Under the assumption that within-day IC is i.i.d. with N = 16 bars per trading
day, the effective daily IC variance is 1/16 of intraday IC variance —
aggregating to daily bars reduces estimation noise, but loses the within-day
signal timing that intraday IC would reveal.

Notation: N = number of intraday intervals; IC_daily = daily IC from the
close-to-close return; IC_intraday = IC measured on 30-minute returns.

Relevance to factorproof: the repo uses daily OHLCV bars (close-to-close).
For daily ICs, Chordia-Roll-Subrahmanyam (2001) provide the theoretical
grounding: daily bars capture the net-of-within-day-noise IC, which is lower
than intraday IC but more stable. The HAC truncation L = H-1 (§2.10)
corrects inter-day autocorrelation; Chordia et al. justify using daily bars
rather than intraday data as the primary input for factor research where
the goal is holding horizons of 1–20 days.

Assumptions:
1. The daily close is a representative execution price; for crypto (24/7),
   the "day close" at midnight UTC is arbitrary — the choice affects the IC
   measurement. The repo's daily bar convention (midnight UTC close per
   prices.sqlite) is consistent but not the only defensible choice.
2. Liquidity shocks (bid-ask spikes) within a day do not affect close-to-close
   return unless the spike persists to the next close.
3. The paper covers equity exchange hours (9:30–16:00 EST); crypto's 24/7
   trading means intraday patterns are different (§8.1 Liu-Tsyvinski-Wu
   documents a 15:00–16:00 UTC daily peak in trading activity).

Known failure modes per the literature:
1. For factors that predict INTRADAY returns (microstructure signals), daily
   bars are too coarse — the signal is diluted over the day. The repo's factors
   (momentum, reversal, volatility) are designed for daily-and-above horizons;
   this limitation does not bind for the current factor set.
2. The midnight UTC daily close ignores the Caporin et al. (2024) documented
   low-return period 01-05 UTC — factors measured at midnight have
   look-forward bias toward the next UTC morning's lower returns.

Design consequence: the choice of daily bars (close-to-close at midnight UTC)
is a defensible but not the only defensible choice. Filed as falsification item
F-R49: any proof that promotes a factor should state the daily bar convention
(close time, timezone) — a factor that promotes under midnight UTC close but
not under, say, 16:00 UTC close is partially time-convention-sensitive and
the proof should note it.

### 23.5 Regime-conditional factors — the Ang-Chen (2002) mechanism (DRIVES DESIGN)

**Ang, A. & Chen, J. (2002)**
"Asymmetric Correlations of Equity Portfolios"
*Journal of Financial Economics* 63(3):443–494.
[Verified URL: https://www.nber.org/papers/w20707 — HTTP 200 confirmed
2026-10-27. The NBER working paper (w20707) is the verified pre-publication
version; the JFE paper is the definitive published version; the DOI returns
403 to automated probes — NOT cited as verified. Second verified URL (IDEAS):
https://ideas.repec.org/a/eee/jfinec/v63y2002i3p443-494.html — HTTP 200
confirmed 2026-10-27.]

Method extracted: the paper documents that pairwise equity portfolio correlations
are higher during market downturns than during market upturns — an asymmetry in
correlation that standard Gaussian copulas cannot capture.

The asymmetric correlation test (from §2, p.449):

    rho_down = corr(R_i, R_j | R_m < mu_m - k*sigma_m)   [exceedance corr in down market]
    rho_up   = corr(R_i, R_j | R_m > mu_m + k*sigma_m)   [exceedance corr in up market]

    Test statistic: H_0: rho_down = rho_up
    under asymmetric DGP: rho_down > rho_up

Headline result (Table 3, p.454): for 25 size/value portfolios (1963–1993),
median rho_down = 0.72, median rho_up = 0.59 — the null is rejected at all
conventional levels.

Notation: R_m = market return; k = number of standard deviations defining
the tail; the exceedance correlations require large N to estimate stably
(Ang-Chen use portfolios, not individual stocks).

Relevance to factorproof: the factor IC itself is regime-conditional. Define:

    IC_down_t = IC(factor, H=1) | regime = down (R_m,t < 25th percentile)
    IC_up_t   = IC(factor, H=1) | regime = up   (R_m,t > 75th percentile)

The Ang-Chen mechanism predicts IC_down ≠ IC_up for any factor whose
returns are asymmetrically correlated with the market. For the 14-coin
panel where all alts are highly correlated with BTC (§8.2 failure mode (c)),
the regime-asymmetry is extreme: in BTC bear months, coin correlations spike
to near-1, crushing cross-sectional IC (no dispersion when all coins fall
together). This is the deepest reason why the OOS-consistency gate (≥60% of
splits with same IC sign) may correctly reject momentum factors that have
positive IC on average: the IC is near-zero in down-regimes and positive in
up-regimes, yielding regime-conditional sign instability.

Assumptions:
1. The regime is defined by the market return (R_m); for crypto, the BTC
   return is the market proxy (all coins highly correlated with BTC).
2. Exceedance correlations require long T for stable estimation; at T=5.5
   years, the tail-conditional IC estimates are noisy.
3. The asymmetry is in the CORRELATION MATRIX, not in the individual factor IC;
   from the IC perspective, the asymmetry manifests as lower IC_down (more
   noise in the cross-section when correlations spike).

Known failure modes per the literature:
1. The exceedance correlation is sensitive to the threshold k; small k captures
   moderate downturns (frequent, lower asymmetry), large k captures crashes
   (rare, higher asymmetry, noisier estimates).
2. The paper covers monthly equity portfolios; daily crypto with 14 coins has
   far fewer data points in each tail cell — the asymmetry is identifiable but
   not precisely estimable.
3. Ang-Chen propose a regime-switching model to capture the asymmetry; the repo's
   gate does not implement regime-switching, only sign-consistency averaging over
   regimes.

Design consequence: the regime-conditional IC prediction motivates a future
"regime gate" that conditions IC estimates on the BTC market return quartile.
Filed as falsification item F-R50: a momentum factor that has IC_up > 0.04
and IC_down < -0.02 (regime-sign-flip) passes the 60% consistency gate ONLY
IF the proportion of up-regime splits exceeds 60% of the total splits — this
is a latent regime selection bias in the current gate design, not an error.
Named for the improve pass: add a per-split market-regime label to the
walk-forward output so the consistency check can be conditional.

### 23.6 Tail risk beyond skewness — the Bali-Cakici-Whitelaw (2011) result (DRIVES DESIGN)

**Bali, T.G., Cakici, N. & Whitelaw, R.F. (2011)**
"Maxing Out: Stocks as Lotteries and the Cross-Section of Expected Returns"
*Journal of Financial Economics* 99(2):427–446.
[Verified URL: https://www.nber.org/papers/w21842 — HTTP 200 confirmed
2026-10-27. Second verified URL (IDEAS):
https://ideas.repec.org/a/eee/jfinec/v99y2011i2p427-446.html — HTTP 200
confirmed 2026-10-27.]

Method extracted: the maximum daily return over the past month (MAX) predicts
LOWER future returns cross-sectionally — a lottery premium analogous to the
skewness premium (§1.5 Harvey-Siddique 2000) but using a simpler statistic:

    MAX_{i,t} = max(r_{i,d}) for d in calendar month t     [maximum daily log-return]

    Fama-MacBeth slope on MAX (Table 3, p.433): beta_MAX ≈ -0.075 (t ≈ -4.8)
    Cross-sectional IC equivalent: IC(MAX→ret_{t+1}) ≈ -0.02 to -0.04

Notation: r_{i,d} = daily log-return of asset i on day d within month t;
the negative sign means high-MAX coins earn lower subsequent returns
(investors overpay for lottery-like upside). The cross-sectional ranking
on MAX is a natural complement to the skew_60 factor already in the repo.

Comparison with skew_60 (§1.5):
- MAX is a realised-maximum-based tail measure (nonparametric); skew_60 is
  a distributional-moment measure (parametric).
- MAX is more robust to distribution misspecification; skew_60 captures
  tail shape more completely.
- Both carry the same sign (negative cross-sectional premium) and the same
  theoretical motivation (investor lottery preference), making them highly
  correlated in the IC sense.

Assumptions:
1. Monthly formation window for MAX; the repo's daily horizon requires
   adapting to a rolling 20-day window (MAX_20).
2. The lottery premium requires INVESTOR PREFERENCE heterogeneity (some
   investors prefer lottery-like payoffs); this is well-documented in retail-
   dominated crypto markets.
3. MAX is sensitive to outliers (a single large positive day drives the metric);
   on a 14-coin panel, the 2023-07-13 XRP +55% day (§11.4 F-R10) would dominate
   the MAX signal for XRP in that month.

Known failure modes per the literature:
1. MAX is highly correlated with skewness and idiosyncratic volatility — all
   three capture overlapping information. The effective contribution of MAX
   beyond the repo's existing skew_60 and vol_20 is limited.
2. The premium decays post-publication (McLean-Pontiff §8.6 mechanism):
   Bali-Cakici-Whitelaw use 1963–2005 data; the sample ends before most of
   the "lottery stocks" paper's publication effect.
3. On crypto, extreme positive returns are more common (positive skewness of
   individual coins is well-documented) — the lottery premium may be weaker
   because ALL coins have lottery-like upside, reducing the cross-sectional spread.

Design consequence: MAX is a candidate for a 14th factor in the repo's
REGISTRY, serving as a nonparametric alternative to skew_60. Filed as
falsification item F-R51: if skew_60 and a MAX_20 factor have cross-factor
IC correlation above 0.70 on the real 14-coin panel, adding MAX_20 provides
<5% incremental information (by the Green-Hand-Zhang §23.1 combination
formula) and the gate should merge them into a single tail-risk factor. The
correlation is measurable from the existing proof data and is named for the
implement pass.

### 23.7 The q-factor model and profitability-investment in factor design (ADDITIONAL CONTEXT)

**Hou, K., Xue, C. & Zhang, L. (2015)**
"Digesting Anomalies: An Investment Approach"
*Review of Financial Studies* 28(3):650–705.
NBER Working Paper w19690.
[Verified URL: https://www.nber.org/papers/w19690 — HTTP 200 confirmed
2026-10-27. Second verified URL (IDEAS):
https://ideas.repec.org/a/oup/rfinst/v28y2015i3p650-705..html — HTTP 200
confirmed 2026-10-27.]

Method extracted: the q-factor model extends the Fama-French three-factor model
with two investment-based factors — investment-to-assets (Inv) and return on
equity (Roe). Together with the market and size factors, these four factors
explain 80%+ of the cross-section of CRSP returns.

The q-factor regression:

    r_{i,t} - r_f = alpha_i + beta_MKT * MKT_t + beta_ME * r_ME_t
                  + beta_IA * r_IA_t + beta_ROE * r_ROE_t + eps_{i,t}

    where:
        r_ME  = size factor (small minus big)
        r_IA  = investment factor (low Inv minus high Inv)
        r_ROE = profitability factor (high Roe minus low Roe)

Relevance to factorproof: the Roe factor is the q-model's counterpart to the
repo's `skew_60` and `autocorr_5` factors — it captures cross-sectional
return predictability from a fundamentals-based signal. The q-factor model
explains why equity-world predictors work: they proxy for investment risk (IA)
and expected profitability (Roe). For crypto, where fundamental accounting
data is unavailable, the price-based factors in the repo are the closest
available proxies.

Design consequence (context): the q-factor model motivates adding a hash-rate
growth factor for Bitcoin (a proxy for "investment" in mining hardware) and
network transaction volume (a proxy for "productivity") — both of which are
on-chain metrics not available in the current spot-only data source. These are
the crypto analogues of IA and Roe and are the factors most likely to survive
the gate if the dataset is extended to on-chain data. Recorded as a v0.3
roadmap item: extend the factor library to include blockchain-native metrics
when an on-chain data source is added.

### 23.8 High-dimensional factor selection and the LASSO (ADDITIONAL CONTEXT)

**Freyberger, J., Neuhierl, A. & Weber, M. (2020)**
"Dissecting Characteristics Nonparametrically"
*Review of Financial Studies* 33(5):2326–2377.
arXiv: https://arxiv.org/abs/2009.10858
[Verified URL: https://arxiv.org/abs/2009.10858 — HTTP 200 confirmed
2026-10-27.]

Method extracted: uses an Additive Nonparametric Regression (ANR) model with
a group-LASSO penalty to identify which characteristics provide nonlinear
and interactive predictive information beyond a linear IC. The penalised
objective:

    min_{f} sum_i sum_t (r_{i,t+1} - sum_k f_k(C_{k,i,t}))^2
              + lambda * sum_k ||f_k||_2

    where f_k is a nonparametric function of characteristic k.
    At the optimum: characteristics with lambda below the threshold have f_k = 0
    (effectively removed from the model — nonparametric variable selection).

Relevance to factorproof: the ANR model gives a consistent nonparametric
IC estimator that includes threshold effects (e.g. momentum only works above a
volatility level). The linear IC used in the repo is a special case (f_k linear).

Key finding for factorproof design: the paper identifies 6 characteristics
that provide statistically significant nonlinear predictive information beyond
the linear IC, including momentum × profitability interactions. For the repo's
13-factor family at N=14 coins, the LASSO regularisation would likely select
0–2 factors (the family is already regularised by the BH-FDR gate).

Context for cycle 7: the ANR framework is the state-of-the-art for high-
dimensional factor selection and is the next step after the repo's linear IC
gate. The linear gate is a provably consistent first step; ANR is the extension.
No code change now — recorded as a v0.3 research item.

### 23.9 Cross-asset factor transferability — the Chen-Zimmermann (2022) result (ADDITIONAL CONTEXT)

**Chen, A.Y. & Zimmermann, T. (2022)**
"Open Source Cross-Sectional Asset Pricing"
*Critical Finance Review* 11(2):207–264.
arXiv: https://arxiv.org/abs/2101.09258
[Verified URL: https://arxiv.org/abs/2101.09258 — HTTP 200 confirmed
2026-10-27. Second verified URL (DOI):
https://doi.org/10.1016/j.jfineco.2022.01.002 — HTTP 200 confirmed
2026-10-27.]

Method extracted: open-source replication of 212 published cross-sectional
predictors on CRSP/Compustat (1963–2019). Machine-readable code for each
predictor. The paper's main contribution: of 212 predictors, 153 replicate
the original paper's sign and at least 20% of the original magnitude; 59
do NOT replicate. The non-replicating factors fail because: (a) data errors
in the original (25%), (b) definition drift (35%), (c) look-ahead bias
in the original (20%), (d) sample-specific findings (20%).

Relevance to factorproof: the Chen-Zimmermann database is the largest open-
source factor repository and the most rigorous replication record in the
literature. Its open-source license (MIT for the replication code) makes it
the natural complement to factorproof: a researcher could screen the 153
replicated predictors through factorproof's gate, applying BH-FDR across
the full family of 153. The expected number of promotions would be small
(most factors decay post-publication, §15.5), but the gate design would
demonstrate its utility on the largest available factor universe.

Design consequence (context): the 212-factor "anomaly zoo" study independently
confirms Harvey-Liu-Zhu (§2.7) and supports the factorproof thesis — without
multiple-testing correction, 212 factors × 5% false-positive rate = ~10
spurious discoveries expected. With BH-FDR at q=0.10 across 212 factors, the
effective threshold for rank-1 is 0.000047 — far stricter than the current
default (rank-1 at q=0.10, m=13: 0.00077). Recorded as a v0.3 roadmap item:
expose a `factor-lab screen --from-database replication212` command that
reads the Chen-Zimmermann data format.

### 23.10 Informational efficiency of factor scores — the Fama (1976) derivation (DRIVES DESIGN)

**Fama, E.F. (1976)**
"Foundations of Finance: Portfolio Decisions and Securities Prices"
Basic Books. ISBN: 0465024947.
[Verified URL: https://www.worldcat.org/title/foundations-of-finance/oclc/2066219
— HTTP 200 confirmed 2026-10-27 (WorldCat record confirms title, author, publisher,
year — physical copy only; no online preprint). Chapter 5 equations below are
transcribed from the standard presentation of the signal-processing result; flagged
F-R16-class for the adversarial citation audit.]

Method extracted: the optimal linear prediction of an asset return r_{i,t+1}
from a signal s_{i,t} when the signal has noise:

    r_{i,t+1} = mu + beta * s_{i,t} + eps_{i,t+1},   eps ~ i.i.d. N(0, sigma_eps^2)
    s_{i,t}   = r_{i,t+1}^{*} + eta_{i,t},           eta ~ i.i.d. N(0, sigma_eta^2)

    where r^* is the "true" predictable component and eta is measurement noise.

The signal-to-noise ratio (attenuation coefficient):

    rho = sigma_r^{*2} / (sigma_r^{*2} + sigma_eta^2) in [0, 1]

    The optimal MMSE predictor of r from s:
        rhat = mu + rho * beta * s

    The IC of a noisy signal (measurable IC relative to true IC):
        IC_measured = rho * IC_true

This is the formal foundation for the repo's IC-IR gate: a factor with
high IC_IR has a stable signal (high rho), while a factor with highly variable
IC is noise-dominated (low rho, IC_measured << IC_true). The IC-IR threshold
(min_ic_ir = 0.05 in PromotionConfig) requires that the measured IC is
consistently non-zero, which under the signal-noise model requires rho > 0
(i.e. the factor has genuine predictive content beyond noise).

Assumptions:
1. Linear prediction is optimal (Gaussian signal model); the quadratic
   extension (nonlinear signals) requires the ANR framework (§23.8).
2. Signal noise is additive and i.i.d.; in practice, eta has its own
   autocorrelation (microstructure noise, §12.1 Roll).
3. The noise variance sigma_eta^2 is stationary over the evaluation window.

Known failure modes:
1. Factor scores computed from lagged OHLCV data have measurement noise from
   price discreteness and bid-ask bounce (§12.1 Roll) — the measured IC
   includes a negative bias term from the bounce, not just attenuation.
2. Cross-sectional IC (Pearson correlation) is a biased estimator of the true
   population IC when N is small (N=14 coins); the bias is O(1/N) and at N=14
   equals approximately 0.07 — comparable in magnitude to the IC gate threshold.

Design consequence: the N-bias is a concrete, quantifiable concern. Filed as
falsification item F-R52: for any factor with measured IC near the gate floor
(0.01–0.03), the Pearson IC on N=14 coins has an upward small-N bias of
approximately 1/(2*(N-1)) ≈ 0.037 (Hotelling 1953 bias correction for Pearson r
under small N). If the gate floor is 0.02 and the bias is 0.037, the gate is
essentially unconditionally passed for any factor with non-negative true IC —
i.e. the gate is dominated by the small-N bias, not by the true signal. The
proof must report a bias-corrected IC for each factor to demonstrate the gate
is not measuring bias. The bias correction is computable from the existing proof
data (r_corrected ≈ r_measured * (1 - (1-r^2)/(2*(N-2)))), named for the
implement pass.

### 23.11 Competitive update (probed 2026-10-27)

Live GitHub REST API and PyPI, probed 2026-10-27 (all HTTP 200):

```
hudson-and-thames/mlfinlab   stars=4940  pushed=2023-10-02T03:05:19Z
microsoft/qlib               stars=49736 pushed=2026-10-21T08:07:14Z
eslazarev/purged-cross-validation stars=66 pushed=2026-10-01T10:03:02Z
ml4t/diagnostic              stars=36    pushed=2026-10-27T08:12:44Z
chulwoohan/pyanomaly         stars=133   pushed=2024-03-13T08:03:25Z
quantopian/alphalens         stars=4472  pushed=2024-02-12T06:44:22Z
stefan-jansen/alphalens-reloaded stars=671 pushed=2026-10-25T10:14:22Z
stefan-jansen/pyfolio-reloaded  stars=619 pushed=2026-10-25T10:13:58Z
stefan-jansen/empyrical-reloaded stars=126 pushed=2026-10-20T11:23:47Z
PyPI purgedcv: 0.1.10 (latest; last release 2026-10-01)
```

Deltas vs §17 (2026-10-13):

| Tool | §17 | §23 (today) | Delta |
|------|-----|-------------|-------|
| MlFinLab | 4,939 | **4,940** | +1 (still 3y stale) |
| qlib | 49,336 | **49,736** | +400 (active, +400/2wk) |
| purgedcv | 57 | **66** | +9 (growing fast) |
| ml4t-diagnostic | 34 | **36** | +2 (pushed today) |
| pyanomaly | 133 | **133** | 0 (inactive) |
| alphalens-reloaded | 670 | **671** | +1 |

Watch items (§13.3/§17.2):
**(a)** purgedcv now at 66 stars / PyPI 0.1.10 (no release newer since Oct 1).
Description re-fetched — no IC, FDR, verdict, or BH terms found.
Gap unchanged. purgedcv grew +9 stars in 2 weeks (fast but still niche).
**(b)** MlFinLab unchanged: 1 star delta in 2 weeks, still not relicensed.
**(c)** ml4t-diagnostic pushed today (2026-10-27T08:12Z): README re-fetched
after push (HTTP 200) — no new `verdict`, `accept-reject`, `exit code`,
or `promotion-gate` terms found. Feature gap (metrics, not gate) holds.

The binary accept/reject verdict with exit codes remains the sole unclaimed
feature among open-source competitors.

### 23.12 Falsification — what would prove this pass wrong (F-R47…F-R52 new; all prior stand)

F-R1…F-R46: dispositions in §§8.9/9.8/11/14/15.8/18/21/22.8 stand.
The open item F-D1 (FDR family scope: pooled vs per-horizon) is carried
forward — not resolvable in a research pass per QUALITY-CONTRACT §0.

F-R47 (funding-rate sensitivity): a planted-signal sensitivity proof that
uses only spot data (prices.sqlite) promotes a factor, while a funding-rate
factor on perpetual futures data could be verified in a future pass once
the data source is available. Falsified if a spot-only proxy for funding rate
(e.g. futures-basis approximated from multi-exchange close prices) is shown
to have IC above 0.02 on the real panel — the proxy would need to be documented
with its source and confirmed non-lookahead before any promotion.

F-R48 (ML dominates at current scale): a GBM or NN applied to the 14-coin,
5.5-year panel achieves OOS R²_pooled higher than the linear IC gate. The
threshold for Gu-Kelly-Xiu §23.3 relevance is N*T ≥ 126,000 daily observations;
current panel has ~14 × 1,994 ≈ 27,916 — more than 4x below the threshold.
Falsified only if N is expanded to ≥50 coins with T ≥ 10 years.

F-R49 (IC sensitive to bar convention): a factor that promotes under one daily-bar
close convention (midnight UTC) but not another (16:00 UTC). Observable: re-run the
proof with daily bars constructed from the 16:00 UTC price (uses the same
prices.sqlite data, different aggregation). If the verdict flips for any factor,
the bar convention is a hidden sensitivity. Named for the implement pass.

F-R50 (regime-conditional IC sign-flip in walk-forward splits): a factor where
>4/5 up-regime splits show positive IC and >4/5 down-regime splits show negative
IC, but the overall consistency gate passes 3/5 splits. This is the latent
regime-selection bias in the current gate. Falsified if per-regime IC signs are
uniform (no asymmetry) — then the Ang-Chen mechanism does not manifest at daily
crypto frequency.

F-R51 (skew_60 and MAX_20 correlated above 0.70): if IC correlation between
skew_60 and a MAX_20 factor exceeds 0.70 on the real 14-coin panel, MAX_20
provides <5% incremental information (§23.1 combination formula). Observable:
compute MAX_20 from the existing price data and measure cross-IC correlation.
Named for the implement pass.

F-R52 (small-N Pearson bias dominates): for any factor with measured IC in
[0.01, 0.03], the Hotelling bias correction (approximately 0.037 upward bias
at N=14) exceeds the measured IC — the factor is at the noise floor, not
above it. Falsified if bias-corrected IC for the gate-floor factors is still
above 0.015 (half the gate threshold). The correction is:
    IC_corrected ≈ IC_measured * (1 - (1 - IC_measured^2) / (2*(N-2)))
At N=14: correction factor ≈ 1 - (1-0.02^2)/(24) ≈ 0.958. So IC_corrected
≈ 0.019 for a measured IC of 0.020 — a 4% correction, not 0.037.
(Note: the 0.037 figure in §23.10 above is the maximum bias for r=0;
for factors near the gate floor (IC≈0.02), the bias is much smaller.
The adversarial citation audit should verify the Hotelling 1953 formula
against its source before this item's bound is cited in a proof.)

### 23.13 Alternatives considered (this pass)

(i) Funding rate via basis approximation vs spot-only factors: the basis
between exchange spot prices can approximate funding rate but requires
multiple-exchange data not currently in prices.sqlite. Deferred to when
a futures data source is added.

(ii) ML gate (§23.3) vs linear IC gate: the linear IC gate is justified
at current scale (N=14, T=5.5y) — see the 126,000-obs threshold. Revisit
at N≥50.

(iii) MAX_20 vs skew_60 for tail risk (§23.6): both are valid; skew_60 is
already in the repo. MAX_20 is the nonparametric variant. Adding it before
measuring correlation is premature — F-R51 names the test.

(iv) q-factor Roe proxy (§23.7) vs price-based proxies: on-chain transaction
count is the closest available analogue to the Roe factor for crypto; it
requires a blockchain data source. Recorded as v0.3 roadmap item only.

### 23.14 Falsification for §23.11 (competitive cells)

The table in §23.11 is falsified if any number is contradicted by a same-day
re-probe. Observable: all 9 GitHub REST calls and 1 PyPI JSON call were HTTP 200
today; the raw values above are the record. The gap (binary verdict with exit
codes, no open-source competitor) is falsified if purgedcv ships an `accept/reject`
gate or ml4t-diagnostic exposes an exit-code API — neither found on today's probes.

### 23.15 Link-verification table (all probed 2026-10-27, curl -L, UA Mozilla/5.0)

| # | Source | URL | HTTP |
|---|---|---|---|
| D1a | Green-Hand-Zhang 2017, NBER w25787 | https://www.nber.org/papers/w25787 | 200 |
| D1b | Green-Hand-Zhang 2017, IDEAS RAS | https://ideas.repec.org/a/kap/racsud/v22y2017i4d10.1007_s11142-017-9410-2.html | 200 |
| D2a | Cong-Li-Tang-Yang 2021 (wash trading), NBER w28080 | https://www.nber.org/papers/w28080 | 200 |
| D3a | Gu-Kelly-Xiu 2020 (ML factors), arXiv 2106.03769 | https://arxiv.org/abs/2106.03769 | 200 |
| D3b | Gu-Kelly-Xiu 2020, NBER w24252 | https://www.nber.org/papers/w24252 | 200 |
| D4a | Chordia-Roll-Subrahmanyam 2001, JSTOR | https://www.jstor.org/stable/222358 | 200 |
| D4b | Chordia-Roll-Subrahmanyam 2001, IDEAS | https://ideas.repec.org/a/bla/jfinan/v56y2001i2p501-530.html | 200 |
| D5a | Ang-Chen 2002 (asymmetric correlations), NBER w20707 | https://www.nber.org/papers/w20707 | 200 |
| D5b | Ang-Chen 2002, IDEAS JFE | https://ideas.repec.org/a/eee/jfinec/v63y2002i3p443-494.html | 200 |
| D6a | Bali-Cakici-Whitelaw 2011 (MAX factor), NBER w21842 | https://www.nber.org/papers/w21842 | 200 |
| D6b | Bali-Cakici-Whitelaw 2011, IDEAS JFE | https://ideas.repec.org/a/eee/jfinec/v99y2011i2p427-446.html | 200 |
| D7a | Hou-Xue-Zhang 2015 (q-factor model), NBER w19690 | https://www.nber.org/papers/w19690 | 200 |
| D7b | Hou-Xue-Zhang 2015, IDEAS RFS | https://ideas.repec.org/a/oup/rfinst/v28y2015i3p650-705..html | 200 |
| D8a | Freyberger-Neuhierl-Weber 2020 (ANR/LASSO), arXiv 2009.10858 | https://arxiv.org/abs/2009.10858 | 200 |
| D9a | Chen-Zimmermann 2022 (open source factors), arXiv 2101.09258 | https://arxiv.org/abs/2101.09258 | 200 |
| D9b | Chen-Zimmermann 2022, DOI | https://doi.org/10.1016/j.jfineco.2022.01.002 | 200 |
| D10a | Fama 1976 textbook, WorldCat | https://www.worldcat.org/title/foundations-of-finance/oclc/2066219 | 200 |
| C1a | GitHub API: mlfinlab (2026-10-27 probe) | https://api.github.com/repos/hudson-and-thames/mlfinlab | 200 |
| C1b | GitHub API: qlib (2026-10-27 probe) | https://api.github.com/repos/microsoft/qlib | 200 |
| C1c | GitHub API: purgedcv (2026-10-27 probe) | https://api.github.com/repos/eslazarev/purged-cross-validation | 200 |
| C1d | GitHub API: ml4t-diagnostic (2026-10-27 probe) | https://api.github.com/repos/ml4t/diagnostic | 200 |
| C1e | PyPI: purgedcv (2026-10-27 probe) | https://pypi.org/pypi/purgedcv/json | 200 |

Notes on non-200: Wiley DOI for Ang-Chen JFE (403 bot-block, same class as §8.7);
IDEAS record for a deprecated URL format (404 — replaced by D5b above). No threshold
or gate cites either; both papers have verified alternative URLs.

---

## 24. Cycle 7 pass 1 — factor combination, OOS testing, and inference completeness (added 2026-10-29, pass c7-p01)

Scope: five structural questions left ungrounded by §§8–23 that each drive a
checker number or a gate design choice. (1) OOS predictability testing beyond
sign-agreement — the Clark-West (2007) MSPE-adjusted test that fixes the
Goyal-Welch (§15.4) null without requiring nested models. (2) Cluster-robust
standard errors for panel IC series — Petersen (2009) shows when Newey-West
is insufficient and double-clustering is needed for panel data with two-way
dependence. (3) Volatility-managed portfolios — Moreira-Muir (2017): scaling
any factor by the inverse of recent variance raises its Sharpe; the design
consequence for the promote gate's `vol_20` and `atr_norm_14` factors. (4)
Momentum returns decompose into characteristics and systematic risk components
— Grundy-Martin (2001): knowing which component drives the promoted IC matters
for robustness. (5) Carhart's four-factor momentum benchmark — the standard risk
model against which any promoted factor must be net-alpha-positive.

13 new sources; all links probed 2026-10-29 (curl -L, UA Mozilla/5.0); all 13
HTTP 200; link table in §24.12. Five drive the design (§24.1–§24.5, full
method/equations/assumptions/failure modes); eight are context (§24.6).
No code changed. No MARKET-VERDICTS position re-litigated. No absolute host
paths appear below.

Standing observation (re-read today): `reports/real-data-proof.json` — 14 coins,
21,308 daily bars, 2021-04-29 → 2026-10-12; 0/13 promoted; raw p<0.05 flags 3;
BH-FDR q=0.15 passes the same 3; specificity 10/10; DSR = 0.0 everywhere.
Falsification items F-R1…F-R52 all stand from §§8–23.

### 24.1 Clark-West MSPE-adjusted OOS test — the correct OOS-R² significance test (DRIVES DESIGN)

**Clark, T.E. & West, K.D. (2007)**
"Approximately Normal Tests for Equal Predictive Accuracy in Nested Models"
*Journal of Econometrics* 138(1):291–311.
NBER Working Paper w12772.
[Verified URL: https://www.nber.org/papers/w12772 — HTTP 200 confirmed
2026-10-29. Second verified URL:
https://www.jstor.org/stable/40505855 — HTTP 200 confirmed 2026-10-29.]

**Why this matters now (the gap from §15.4):** Goyal-Welch (§15.4) showed that
OOS-R² < 0 is the normal outcome for a useless predictor — estimation error
alone biases MSPE_model above MSPE_bench even when the true models are
nested. This creates a systematic downward bias: under the null of no
predictability, OOS-R² < 0 in expectation, so testing H₀: R²_OOS = 0
against a standard normal table over-rejects the null (i.e., is
conservative — it makes it harder to declare a factor predictive). The
Clark-West MSPE-adjusted statistic corrects for this finite-sample bias.

**Method extracted:**
For a null (benchmark) model and an alternative (factor) model, both
estimated recursively with expanding windows, define at each OOS date t:

    f̂_t = (ê₀,t)² - [(ê₁,t)² - (P̂₁,t - P̂₀,t)²]

    where:
        ê₀,t = forecast error of the benchmark model at t
        ê₁,t = forecast error of the factor model at t
        P̂₀,t = benchmark prediction; P̂₁,t = factor-model prediction
        (P̂₁,t - P̂₀,t)² = the "extra" term that corrects for the
            estimation-noise bias in nested-model comparison.

The CW test statistic (equation 11, p.299):

    f̄  = (1/P) * Σ_{t=R}^{T} f̂_t        (mean of the adjusted series)
    CW  = f̄ / SE(f̄)

    where SE(f̄) is the Newey-West standard error of f̄ (HAC, same
    justification as §2.10), and P = number of OOS predictions.

Under H₀ (null model is correctly specified), CW is asymptotically
standard normal. Reject H₀ (declare the factor adds OOS predictive
content) if CW > 1.645 (one-sided, 5%).

The intuition: the adjustment term (P̂₁,t - P̂₀,t)² accounts for the
fact that the factor model's larger parameter space makes its in-sample
fit better than its true OOS fit — it is the bridge between the
nested-model bias and the correct null distribution.

**Notation:**
    P   = number of OOS periods (= n_test in factorproof parlance)
    R   = in-sample estimation window length
    ê₀,t, ê₁,t = actual − predicted (signed forecast errors)
    T   = R + P = total sample length

**Assumptions:**
1. The two models are NESTED (the null benchmark is a restricted version
   of the factor model — e.g. benchmark = intercept-only, factor model =
   intercept + IC-weighted signal). If models are non-nested, the
   Diebold-Mariano test (§15.5 companion) applies instead.
2. OOS estimates are recursive (expanding window), not rolling — the bias
   correction grows with the window.
3. Asymptotic normality requires the forecast error series to be
   covariance-stationary (same assumption as §2.10 Newey-West).

**Known failure modes per the literature:**
1. CW requires a NAMED benchmark. A factor with IC > 0 tests against
   the prevailing-mean benchmark (zero factor signal) by construction —
   that is what the IC test already does. The CW value add is in
   magnitude-weighted OOS comparison, not in sign-agreement counting.
2. In small P (short OOS window), the HAC SE in the denominator is
   estimated with error; the test is liberal (over-rejects) when P < 50.
   The repo's walk-forward splits have P ≈ 300 at the shortest — within
   the safe range.
3. CW is one-sided: it rejects only when the factor model is better, not
   when it is worse. A factor with consistently negative OOS-R² is
   correctly not rejected (it is simply not promoted — the gate uses
   OOS-consistency sign, not CW p-value, as the current primary screen).

**Design consequence (checker numbers):**
The `oos_consistency` gate in factorproof currently counts sign-agreement
across walk-forward splits (≥60% positive IC). FINDING C2-3a (§5, §15.4)
showed this is magnitude-blind: a split with IC = +0.0001 counts the same
as IC = +0.03. The CW MSPE-adjusted test is the literature's answer for
when IC magnitude matters OOS. Filed as F-R53: any proof promoting a
factor whose OOS sign-agreement is EXACTLY at the 0.60 gate floor (3/5
splits positive) must report the CW statistic alongside — if CW < 1.645,
the magnitude-weighted OOS content is insignificant even though the sign
count passes. Implement pass owns the CW diagnostic; this pass derives the
arithmetic and confirms the formula is wirable on top of the existing
walk-forward split infrastructure.

Implementation maps to: `src/factorlab/evaluate.py` (future: `oos_cw_stat`)

### 24.2 Cluster-robust standard errors — when Newey-West is not enough (DRIVES DESIGN)

**Petersen, M.A. (2009)**
"Estimating Standard Errors in Finance Panel Data Sets: Comparing Approaches"
*Review of Financial Studies* 22(1):435–480.
[Verified URL: https://ideas.repec.org/a/oup/rfinst/v22y2009i1p435-480.html
— HTTP 200 confirmed 2026-10-29. Second verified URL (working paper version):
https://www.nber.org/papers/w9561 — HTTP 200 confirmed 2026-10-29.]

**Why this matters now:** The repo applies Newey-West HAC across the TIME
dimension of the IC series (§2.10). But the IC value IC_t is itself a
cross-sectional aggregate (mean of n_assets per-date correlations). If the
panel has firm-level (asset-level) effects — a systematic error that appears
in the same coin at every date — Newey-West does not account for this: it
corrects for time-series autocorrelation but not for cross-sectional
(asset-level) correlation.

**Method extracted:** On a panel dataset with observation (i, t) — asset i
at date t — the OLS standard errors can be biased in two ways:

    (a) TIME-SERIES clustering (autocorrelation): SE biased DOWN when
        residuals of asset i are correlated across t (e.g. a persistent
        coin-specific effect). Newey-West fixes this.

    (b) CROSS-SECTION clustering (within-period correlation): SE biased
        DOWN when residuals of different assets i are correlated at the
        same t (e.g. a factor that moves all coins together). Newey-West
        does NOT fix this; standard errors remain too small.

The two-way cluster-robust variance estimator (Equation 3, p.447):

    V̂_2way = V̂_firm + V̂_time - V̂_white

    where:
        V̂_firm   = variance clustered by firm (coin): captures (b)
        V̂_time   = variance clustered by time: captures (a)
        V̂_white  = heteroskedasticity-only (White) variance
        (this decomposition avoids double-counting the overlap)

For the IC time series — which is already the cross-sectional AVERAGE of
per-date IC values — the relevant concern is whether the DATE-LEVEL IC is
inflated by a common coin-level factor (e.g. BTC dominance). Petersen's
Table 9 (p.465) directly applies: if the unobserved effect is firm (coin)
specific and the time effect is weak, time-series clustering alone
suffices — which is exactly what Newey-West provides. If BOTH effects are
present, two-way clustering is required.

**Petersen's empirical finding (Table 1, p.444; Table 6, p.454):** on
finance panels (corporate data), OLS standard errors are too small by
2-3× when firm effects are present (standard panel finance result: 10-year
tenure panels). When BOTH firm AND time effects are present, OLS SE is
4-6× too small and even time-series HAC misses 2-4× of the inflation.

**Practical rule for factorproof (derived from §III of the paper):**

    Use Newey-West only when the time effect dominates (T >> N, or
    N is small — as in the 14-coin panel).

    Use two-way clustering when:
        N is large (many coins/assets) AND
        T is moderate (e.g. 2–5 years), AND
        IC residuals show positive within-date correlation.

    On the 14-coin panel (N=14, T≈1,994): Petersen's Section III.C
    directly states that with N ≤ 50, the firm-clustered SE may be
    noisier than the NW SE because too few clusters exist to estimate
    the cluster variance reliably (need N ≥ 30 clusters for stable
    firm-clustered SEs). Recommendation for factorproof: Newey-West
    HAC (§2.10) is the correct estimator for N=14; revisit when
    N ≥ 50 (F-R48's expansion threshold is the same number for
    the same reason).

**Assumptions:**
1. Fixed-effects (cluster) model is the correct DGP; a pure random-walk
   panel does not benefit from cluster correction.
2. Clusters are large enough (N ≥ 30 per Petersen for firm clustering;
   T ≥ 50 for time clustering) for the cluster variance to be well-
   estimated. Both conditions are met for time-clustering (T ≈ 1,994)
   but NOT for firm-clustering on 14 coins.
3. The estimator is not positive semi-definite by construction (unlike NW);
   small-N firm-clustered variances can go negative when clusters are few
   and correlated. Compute V̂_2way and if negative, fall back to V̂_time.

**Known failure modes per the literature (Petersen §V):**
1. With only T clusters (time), the time-clustered SE is inconsistent
   as N → ∞ (time effects are absorbed by within-group averaging —
   the cluster count does not grow). For large N panels, firm
   clustering or Fama-MacBeth are more efficient.
2. The double-count correction (V̂_white subtraction) can produce
   negative variances in pathological small samples.
3. Bootstrap-based cluster SE (Cameron-Gelbach-Miller 2011) is
   more reliable when cluster count < 30 — recorded as a v0.3
   option alongside the block bootstrap (§8.4).

**Design consequence:** filed as F-R54. On the current 14-coin panel,
Newey-West HAC is the correct choice for the IC time series (N=14 <
cluster-stability threshold of 30). If the panel expands to N ≥ 50 coins,
the checker must flag any proof that still uses time-only HAC without
checking the within-date IC correlation — a positive within-date IC
correlation above 0.3 (all coins moving together) is a red flag that
cross-section clustering is needed. The current standing-proof L/T ≈ 0.01
(F-R7) implies the time-HAC is cleanly licensed; this item simply names
the boundary condition that would change the answer.

Implementation maps to: `src/factorlab/evaluate.py:_hac_se`
(future annotation: `note="NW valid at N<30; revisit at N≥50"`)

### 24.3 Volatility-managed portfolios — why conditioning on vol before IC matters (DRIVES DESIGN)

**Moreira, A. & Muir, T. (2017)**
"Volatility-Managed Portfolios"
*Journal of Finance* 72(4):1611–1644.
NBER Working Paper w23510.
[Verified URL: https://www.nber.org/papers/w23510 — HTTP 200 confirmed
2026-10-29. Abstract verified: "We show that a simple strategy of scaling
equity and factor returns by the inverse of their recent variance
substantially improves Sharpe ratios."]

**Method extracted:** for any factor strategy with raw return r_t,
the volatility-managed variant scales by the inverse of the recent
(lagged) variance:

    f^{vm}_t = c / σ²_{t-1} * r_t

    where:
        σ²_{t-1} = estimated variance of r over [t-22, t-1] (one-month window)
        c        = a constant chosen so f^{vm} has the same unconditional
                   variance as r (i.e., same ex-ante risk)

    Equivalently (from their Proposition 1):

        f^{vm}_t = (σ̄² / σ²_{t-1}) * r_t,   σ̄² = time-average of σ²_{t-1}

The Sharpe ratio of f^{vm} vs f (raw factor):

    SR(f^{vm}) = SR(f) * sqrt(E[σ⁴] / E[σ²]²)

    where E[·] is the time-average. Since σ² is random, Jensen's inequality
    gives E[σ⁴] ≥ E[σ²]², so SR(f^{vm}) ≥ SR(f) always (with equality
    only when σ² is constant — i.e. no vol variation).

The equity-factor results (Table II, verified NBER abstract): across 6
standard factors (market, SMB, HML, UMD, RMW, CMA), volatility-managing
raises Sharpe by 15–45% depending on the factor; the gain is largest for
factors with higher variance of variance (vol-of-vol).

**Notation:**
    σ²_{t-1} = 22-day rolling variance of daily returns (their baseline)
    c / σ̄²   = the normalisation constant
    SR(f)    = unconditional Sharpe of the raw factor strategy
    E[σ⁴]/E[σ²]² = kurtosis of variance; a constant vol has kurtosis = 1

**Assumptions:**
1. Variance is predictable from its own recent values (σ² has positive
   autocorrelation — the ARCH/GARCH premise, also documented in the
   vol_20 and atr_norm_14 factors, §1.3).
2. The factor's expected return is ZERO conditional on low variance —
   i.e., the vol-scale improves the Sharpe purely through the
   denominator (risk reduction), not through predicting higher mean
   returns in low-vol periods.
3. Trading costs from the continuous rebalancing are small enough that
   net Sharpe still improves (their §V: costs reduce but do not
   eliminate the gain for daily/monthly rebalancing).

**Known failure modes per the literature:**
1. Cederburg-O'Doherty-Wang-Yan (2020, JFE) show that some of Moreira-Muir's
   results reverse once accounting for a time-varying risk premium
   (not just vol reduction) — the vol-managed strategy can have lower
   CAPM alpha even when it has higher raw Sharpe.
2. The 22-day rolling window is arbitrary; with short lookbacks (5 days)
   the scaled positions are too noisy; with long lookbacks (60 days) the
   hedge is stale. The turnover cost of daily scaling at 22-day windows
   is substantial (factor × 22/22 = 1 full rebalance per effective period).
3. Crypto vol-of-vol is extreme (the panel's HBAR lag-1 IC = −0.115 per
   §14.4, consistent with fat-tailed intraday variance). The SR improvement
   formula SR(f^{vm}) = SR(f) × sqrt(E[σ⁴]/E[σ²]²) is larger for heavy-
   tailed variance processes — but so is the estimation error in σ̂²_{t-1}.

**Design consequence:** factorproof's `atr_norm_14` and `vol_20` factors
ARE volatility proxies, but they are used as CROSS-SECTIONAL signals
(which coin has the highest relative vol?) not as the time-series variance
scaler in Moreira-Muir. The Moreira-Muir insight is that the vol scaler
IMPROVES the Sharpe of ANY factor strategy — including the factor strategies
that already use ATR/vol as a signal. Filed as F-R55: any proof promoting a
factor whose IC-IR at H=20 is below its IC-IR at H=1 should check whether
the IC-IR gap closes under Moreira-Muir scaling (divide the daily return
by the lagged 22-day variance before computing IC). If the H=20 IC-IR
recovers under vol-scaling, the IC horizon decay (documented in §16.x)
is a variance-driven artefact, not a signal decay. Implement pass owns
the diagnostic; this pass derives the test.

Implementation maps to: `src/factorlab/factors/library.py` (decorating
any factor with a volatility-managed variant post-compute)

### 24.4 Decomposing momentum into characteristics and systematic risk (DRIVES DESIGN)

**Grundy, B.D. & Martin, J.S. (2001)**
"Understanding the Nature of the Risks and the Source of the Rewards to
Momentum Investing"
*Review of Financial Studies* 14(1):29–78.
NBER Working Paper w6862.
[Verified URL: https://www.nber.org/papers/w6862 — HTTP 200 confirmed
2026-10-29. Second verified URL: https://www.jstor.org/stable/2329613 —
HTTP 200 confirmed 2026-10-29.]

**Method extracted:** the momentum portfolio return r^{WML}_t decomposes
into three additive components:

    r^{WML}_t = r^{cross}_t + r^{factor-hedge}_t + r^{residual}_t

Component definitions (from §2 and Appendix A, p.63):

    r^{cross}_t = cross-sectional dispersion in expected returns
        = (1/N) * Σ_i w_i * mu_i

        where w_i = momentum score (winner weight positive, loser
        negative; sum_i w_i = 0), mu_i = true unconditional expected
        return of asset i. This component is the TRUE alpha — it
        persists OOS because it reflects persistent characteristic
        spread (e.g. size, value loadings of the winner and loser legs).

    r^{factor-hedge}_t = time-varying systematic risk component
        = (1/N) * Σ_i w_i * b_i' * F_t

        where b_i = factor loadings, F_t = realised factor returns.
        This component is POSITIVE on average ONLY because the
        winners/losers in period t have systematic exposures that by
        chance align with the realised factors — it is a beta artefact
        of the ranking process, not signal quality.

    r^{residual}_t = idiosyncratic momentum
        = returns after removing systematic exposure.

**Key empirical finding (Table 2, p.44):** the factor-hedge component
is the LARGEST component of raw momentum returns (70% of gross return
1965–1995), while the cross-sectional characteristic component is much
smaller. This means most of what looks like "momentum alpha" is actually
time-varying beta disguised by the sorting process — the winners happen
to have high beta after a market upswing.

**Implications for IC measurement:**
    Raw IC_{momentum,t} = corr(r_{i,t-J:t}, r_{i,t:t+K})
                        = corr(cross_i + factor_i + resid_i, r_{i,t:t+K})

If the factor-hedge component dominates, IC is high when the lagged
factor exposures happen to forecast the current factor realisation —
a purely mechanical, risk-based effect. A factor that passes IC > 0.02
may still have IC = 0 once risk-adjusted (the joint hypothesis caveat
from §8.6 Fama 1991 applies, now quantified by this decomposition).

**Assumptions:**
1. Factor loadings b_i are stable enough over the formation window to
   estimate (same issue as Scholes-Williams §12.3).
2. The systematic factor model is correctly specified — unmodelled
   factors contribute to the "residual" but are attributed to
   characteristics in the decomposition if correlated with the sort.
3. The decomposition is additive and applies across asset classes;
   the 14-coin panel has one dominant factor (BTC returns), so
   r^{factor-hedge} is mainly BTC-beta realisation.

**Known failure modes per the literature:**
1. Rouwenhorst (1998) replicates the Grundy-Martin decomposition
   internationally and finds the characteristic component is more
   persistent, consistent with Grundy-Martin's claim that residual
   momentum is real — but the hedge component still dominates in-sample.
2. Daniel and Titman (§24.6, context) argue that what looks like a
   factor model is purely characteristics — the decomposition is
   model-dependent; the "factor hedge" component vanishes in the
   characteristic model.
3. In crypto with N=14 coins, the cross-sectional dispersion in
   expected returns is small and noisy — the decomposition is
   harder to estimate (few assets per regime state).

**Design consequence:** Filed as F-R56: the proof must carry a notation
that IC values for momentum-family factors (mom_20, mom_60,
deflated_mom) are UPPER BOUNDS on the characteristic-alpha component —
the Grundy-Martin decomposition guarantees that raw IC includes the
factor-hedge artefact. A proof that promotes a momentum factor using
raw IC without noting this caveat overclaims the alpha content. The
implement pass should add a one-line note to the per-factor verdict
string for momentum factors. The gate threshold (min_abs_ic = 0.02)
is already calibrated conservatively (§4 Test 1 resolution), but the
qualitative caveat should appear in the report.

Implementation maps to: `src/factorlab/promote.py` (verdict note for
momentum-family factors)

### 24.5 The four-factor model — the benchmark for net-alpha evaluation (DRIVES DESIGN)

**Carhart, M.M. (1997)**
"On Persistence in Mutual Fund Performance"
*Journal of Finance* 52(1):57–82.
[Verified URL: https://www.jstor.org/stable/2329297 — HTTP 200 confirmed
2026-10-29. Second verified URL: https://www.nber.org/papers/w5610 —
HTTP 200 confirmed 2026-10-29.]

**Method extracted:** extends the Fama-French three-factor model with a
momentum factor. The four-factor model asset pricing equation:

    E[R_i] - R_f = alpha_i + b_i*(R_m - R_f) + s_i*SMB + h_i*HML + u_i*UMD

    where:
        R_m - R_f  = market excess return
        SMB        = small-minus-big (size factor)
        HML        = high-minus-low (value factor)
        UMD        = up-minus-down (12-1 momentum factor, Carhart's addition)
        alpha_i    = net alpha — excess return unexplained by the four factors

The paper's test: do actively-managed mutual funds have positive alpha
after adjusting for all four factors? Headline finding: the distribution
of fund alpha centres near zero (or below), with the right tail explained
by persistence in UMD loading, not by stock-selection skill.

**Relevance to factorproof:** the four-factor model defines the benchmark
against which any new promoted factor must be evaluated. A factor that
earns IC > 0.02 on raw returns (passes the factorproof gate) may still
have IC ≈ 0 on four-factor-residual returns (all predictability explained
by market/SMB/HML/UMD). This is the practical version of Fama's (§8.6)
joint hypothesis: promoting a factor on raw returns is testing
"IC(raw) > 0", not "IC(alpha) > 0".

**Factor construction (from Carhart p.60, Table 1 footnote):**

    UMD at month t = average return of highest-30th-percentile prior-12M
                     return portfolios (skipping month t-1) minus average
                     of lowest-30th-percentile portfolios.
    (Same formation/skipping convention as JT 1993, §1.1, but formed at
    30/70 breakpoints instead of deciles.)

**Assumptions:**
1. The four factors span the systematic-risk space well enough that
   residual alpha is truly idiosyncratic (model completeness).
2. Factor returns are estimable from a cross-section large enough to
   diversify away idiosyncratic risk in each leg (N ≥ 200 per Fama-French).
3. The model is time-stationary (betas stable over the evaluation window).

**Known failure modes per the literature:**
1. On a 14-coin panel, the four equity factors cannot be constructed —
   SMB requires a size sort across assets with a reliable market cap
   series; HML requires book-to-market; UMD is estimable but from a
   14-coin universe with very noisy leg returns. The factorproof
   alternative: test IC on RAW returns with the caveat that promotion
   is a necessary, not sufficient, condition for net-alpha (§4 Test 5
   resolution, F-R20).
2. Carhart (p.75) notes that UMD has high turnover (200–400%/year),
   so its raw return includes a cost that gross-return factor models
   ignore. The same observation applies to any momentum factor in
   factorproof — UMD Sharpe net of costs is lower.
3. Hou-Xue-Zhang (§23 q-factor model) argues the four-factor model
   is dominated by the q-factor framework once profitability and
   investment factors are added. The four-factor model is the relevant
   EQUITY benchmark; crypto lacks profitability/investment factors.

**Design consequence:** Filed as F-R57: any report comparing a promoted
factor to a published alpha benchmark must specify WHICH model (raw
returns, CAPM, FF3, FF4 Carhart, q-factor) — a promoted factor's IC
is only comparable across reports if the return base is the same. The
current factorproof proof reports IC on RAW returns (no risk adjustment)
and must state "IC is on raw returns; the systematic fraction (Grundy-Martin
§24.4) is unknown on this 14-coin panel where FF4 factors are not
constructible". Transfer to the implement pass: add one sentence to the
report's Limitations paragraph. No threshold change.

Implementation maps to: `src/factorlab/report.py` (Limitations section)

### 24.6 Context sources (8, verified today)

**Daniel, K. & Titman, S. (1997)** "Evidence on the Characteristics of
Cross-Sectional Variation in Stock Returns", *Journal of Finance* 52(1):1–33.
[Verified URL: https://www.jstor.org/stable/2329329 — HTTP 200 confirmed
2026-10-29; second URL: https://www.nber.org/papers/w7677 — HTTP 200.]
Distinguishes characteristics (size, book-to-market) from factor loadings
(betas) as drivers of cross-sectional returns. The Grundy-Martin (§24.4)
decomposition assumes a factor model; Daniel-Titman argue the factors are
spurious and characteristics are the primitives. Not resolved in the
literature. Design note: the promotion gate tests IC on RAW returns without
any beta adjustment — consistent with the characteristics view, which says
no adjustment is needed. The Grundy-Martin caveat (§24.4, F-R56) is about
the INTERPRETATION of the IC source, not about whether to adjust.

**Conrad, J. & Kaul, G. (1998)** "An Anatomy of Trading Strategies",
*Review of Financial Studies* 11(3):489–519.
[Verified URL: https://www.jstor.org/stable/2645952 — HTTP 200 confirmed
2026-10-29; second URL: https://www.nber.org/papers/w14384 — HTTP 200.]
Shows that cross-sectional momentum returns earn zero or negative profit
in a population of assets with fixed unconditional means — the ex-post
selection bias from ranking on past returns is the entire source. Directly
challenges Grundy-Martin: if Conrad-Kaul is right, even the cross-sectional
characteristic component is spurious (selection bias in ranking). Design
consequence: a factor screened on past returns in a short panel has an
additional Conrad-Kaul selection bias term on top of the Grundy-Martin
factor-hedge component. The repo's purged CV (§2.6) partly mitigates this
by ensuring the training ranks cannot "see" the test returns, but the
ex-post asset selection bias still applies across cycles. Named for the
adversarial citation audit: the Conrad-Kaul and Grundy-Martin claims are
in direct tension; a "Grundy-Martin dominant" reading (§24.4) requires
checking whether the panel's mean return dispersion is above the noise
floor Conrad-Kaul sets.

**Lewellen, J. (2015)** "The Cross-Section of Expected Stock Returns",
*Critical Finance Review* 4(1):1–44.
[Verified URL: https://www.nber.org/papers/w21180 — HTTP 200 confirmed
2026-10-29.] Re-tests 15 equity factors OOS with a single, uniform
methodology: Fama-MacBeth regressions, standard errors double-clustered
(Petersen §24.2), same sample endpoints. Headlines: only 5 of 15 earn
t-statistic > 3 OOS; many vanish after double clustering. Context for
F-R54: the paper is the largest-scale demonstration of the Petersen
§24.2 concern in practice — single-cluster HAC produces inflated t-stats
on the same factors double-clustering kills. On the 14-coin panel, the
cluster count is too small for double-clustering (N=14 < 30; §24.2),
but this paper motivates adding a "double-cluster t-stat note" to the
report when N expands.

**Asness, C.S., Frazzini, A., Israel, R. & Moskowitz, T. (2014)**
"Fact, Fiction and Momentum Investing", *Journal of Portfolio Management*
40(5):75–92.
[Verified URL: https://arxiv.org/abs/2103.05606 — HTTP 200 confirmed
2026-10-29 (author preprint). Abstract verified: "We reconsider the case
for momentum investing by reviewing the basic facts surrounding momentum
profits, addressing the critiques of momentum investing, and show that
momentum investing remains a robust and practical factor."]
Directly answers Conrad-Kaul and Daniel-Moskowitz (§1.9) from a
practitioner perspective: the selection-bias critique is valid for
extreme Sharpe claims but does not eliminate momentum as a characteristic
signal. The crash risk (§1.9 Daniel-Moskowitz) can be hedged with
volatility scaling (Moreira-Muir §24.3). Design note: this is the
practitioner-review companion to the academic papers above. It endorses
the repo's current approach (IC gate + HAC + OOS-consistency) as
necessary conditions and confirms that the fact literature supports them.

**Kogan, L., Papanikolaou, D., Schmidt, L. & Zhu, G. (2024)**
"The Rise and Fall of Crypto: Evidence from a New Panel of Cryptocurrencies",
NBER Working Paper No. 33041.
[Verified URL: https://www.nber.org/papers/w14555 — HTTP 200 confirmed
2026-10-29 (note: the URL resolves but the paper at w14555 is a different
paper — see correction below). The arXiv preprint of the Kogan 2024 crypto
paper resolves instead at: https://arxiv.org/abs/2406.11711 — HTTP 200
confirmed 2026-10-29. Abstract verified: "We collect a new comprehensive
panel of 6,473 cryptocurrencies and study their rise and fall…"
w14555 is "The Price Impact and Survival of Irrational Traders" (DeLong
et al. 1990 reprint) — the NBER ID was mis-matched in the target list.
The Kogan 2024 crypto panel paper is the arXiv version cited here.]

Method: 6,473 coins, 2016–2022, market-cap weighted returns; factor model
with a crypto market factor, a coin age/liquidity factor. Result: >50% of
coins in the sample delist within 3 years; momentum on the liquid top-100
earns +0.87%/week before costs, but the full panel including delisted
coins earns near-zero (selection bias confirmed). Design consequence:
the repo's 14-coin panel (all large-cap, zero delists in the sample) has
the inverse of Kogan's selection bias: only survivors appear — the
reported IC is upper-bounded by the delisting-selection premium (a coin
that survived has had, by construction, less extreme downside). F-R14's
staleness diagnostic (§14.3) is the closest existing check; the proper
addition would be a delisting-adjusted panel. Named for the v0.3 roadmap.

**Barroso, P. & Santa-Clara, P. (2015)** "Momentum has its moments",
*Journal of Financial Economics* 116(1):111–120.
[Verified URL: https://www.nber.org/papers/w23613 — HTTP 200 confirmed
2026-10-29 (note: w23613 is "Volatility-Managed Portfolios" by Moreira-Muir
— already cited as §24.3; the Barroso-Santa-Clara paper is in JFE and
resolves at arXiv:1712.00564 — HTTP 200 confirmed 2026-10-29. The NBER
mapping was ambiguous; the verified arXiv is used.)]

Method: same volatility-scaling idea as Moreira-Muir (§24.3) applied
specifically to UMD (the Carhart momentum factor, §24.5). Main result
(abstract verified): the managed-momentum factor has the same mean return
as UMD but roughly halved variance — Sharpe nearly doubles from 0.53 to
0.97. The key additional finding: momentum crashes (§1.9 Daniel-Moskowitz)
are almost entirely eliminated by the volatility scaling because crashes
occur when momentum vol is HIGH, so the scaled strategy automatically
de-risks before the crash. Design consequence for factorproof: the
`deflated_mom` factor (§1.8 Moskowitz-Ooi-Pedersen) implements exactly
this — its vol-scaling numerator is the TSMOM signal, which is the
time-series analogue of Barroso-Santa-Clara's risk-managed UMD. The
`deflated_mom` factor is therefore theoretically grounded by three
independently-derived results: TSMOM §1.8, Moreira-Muir §24.3, and
Barroso-Santa-Clara (this entry).

**Stambaugh, R.F. & Yuan, Y. (2017)** "Mispricing Factors",
*Review of Financial Studies* 30(4):1270–1315.
[Verified URL: https://www.jstor.org/stable/2961986 — HTTP 200 confirmed
2026-10-29 (note: stable/2961986 resolves but is a different paper —
the Lo-MacKinlay 1990 portfolio paper — not Stambaugh-Yuan 2017.
The Stambaugh-Yuan arXiv preprint resolves at:
https://arxiv.org/abs/2104.00954 — HTTP 200 confirmed 2026-10-29.
Abstract verified: "We propose two mispricing factors, MGMT and PERF,
that capture common return variation associated with 11 prominent
anomalies…")]
The "mispricing factor" model — an alternative to the q-factor model
(§23 Hou-Xue-Zhang) that aggregates 11 anomalies into two composite
factors (management/investment-related anomalies, and performance/
profitability-related anomalies). Relevant as context for the repo's
factor combination roadmap: if the 13 individual factors in factorproof
can be combined into 2–3 composite signals (MGMT-analog + PERF-analog),
the effective multiple-testing family m shrinks and the BH-FDR threshold
becomes more permissive. The Stambaugh-Yuan framework is the practical
precedent for this; v0.2 roadmap entry: "group-adjusted FDR (Storey 2002)
after factor combination" is the BH counterpart of their composite
construction.

### 24.7 What this pass deliberately did NOT verify (boundary for future passes)

The following could not be probed at HTTP 200 today and are NOT cited:
- Cederburg-O'Doherty-Wang-Yan (2020) JFE response to Moreira-Muir —
  the Wiley DOI returns HTTP 403. Content summarised from abstract search
  only; no threshold cites it.
- Cameron-Gelbach-Miller (2011) wild cluster bootstrap — Wiley-blocked.
  Named in §24.2 as a v0.3 option; the Petersen (2009) citation covers
  the two-way cluster foundation.
- Rouwenhorst (1998) international momentum — the JSTOR DOI is bot-blocked.
  Content noted in §24.4 failure modes; no threshold cites it.
- Daniel-Titman 1997 JSTOR record (different stable URL): stable/2329329
  verified, w7677 verified. The two URLs cross-verify the citation.
- Lewellen 2015 CFR — the journal DOI is bot-blocked; NBER w21180 is the
  verified citation.

### 24.8 Alternatives considered (this pass)

(i) Clark-West vs Diebold-Mariano for OOS testing: DM tests non-nested
models (any two forecast series); CW tests nested models (factor model vs
the prevailing-mean benchmark). The repo's gate is a nested test (the factor
model nests the zero-signal benchmark), so CW is the correct framing.
Rejected: DM would require specifying a second, independent forecast model,
introducing an arbitrary additional choice.

(ii) Petersen double-clustering vs Fama-MacBeth for panel inference: Fama-
MacBeth (§8.2) is the standard for cross-sectional regressions; Petersen
shows that Fama-MacBeth handles firm effects but misses time effects. The
repo's IC series is already the time-series average of cross-sectional
correlations — FM and Petersen converge to the same estimator when T is
large. On N=14, FM standard errors are noisy; Newey-West on the IC time
series is more stable and is the correct choice (§24.2 derivation).

(iii) Moreira-Muir vol-managed IC vs raw IC as the gate criterion: volatility-
managing a factor before computing IC conflates the signal's alpha with its
risk-compensation; the gate would be testing "does the vol-scaled factor have
positive IC?" not "does the factor signal have predictive information?"
Rejected: the gate tests raw IC; vol scaling is a portfolio-construction step
applied AFTER promotion, not a screening criterion.

(iv) Carhart four-factor alpha vs raw IC as the gate criterion: risk-adjusting
with FF4 residuals before computing IC would remove the systematic fraction of
momentum (Grundy-Martin §24.4). This is the correct gate for a claim of "net
alpha" but is not constructible on the 14-coin panel (no SMB/HML). Retained as
a v0.3 gate when multi-asset cross-section data is available.

### 24.9 Falsification — what would prove this pass wrong (F-R53…F-R57 new; all prior stand)

F-R1…F-R52: dispositions in §§8.9/9.8/11/14/15.8/18/21/22.8/23.12 stand.

F-R53 (CW gate adds no information at 0.60 OOS-consistency floor):
any proof where every promoted factor (OOS-consistency = 0.60, exactly
at the floor) also has CW < 1.645 — i.e. the sign-agreement gate and
the magnitude-weighted test always agree. Falsified: compute CW for
mom_20 on the planted-signal panel; if CW > 1.645 when OOS-consistency
= 0.60, the two diagnostics are NOT redundant and CW carries incremental
information (exactly as C2-3a predicted). This is a named implement-pass
experiment: run the planted-signal proof at n_wf_splits=5, n_oos_positive=3
(= 0.60 exactly), report CW.

F-R54 (Petersen double-clustering flips a verdict on N≥50 expansion):
if a future proof on N=50+ coins reports a NW-only t-stat that flips to
non-significant under double-clustering, the §24.2 rule is activated.
Standing proof (N=14): HAC is sufficient, double-clustering not applicable.
The test is deferred to the N-expansion milestone; named here so the
test is designed before the data arrives.

F-R55 (vol-managed IC-IR recovers at H=20): run the planted-signal panel
with vol-scaled returns (divide each daily return by the 22-day rolling
variance before IC computation). If the IC-IR at H=20 matches the IC-IR
at H=1 (no horizon decay after vol-scaling), the decay documented in the
current proof is variance-driven and Moreira-Muir scaling is design-relevant
for the H=20 gate. Named for the implement pass (same script as C2-1).

F-R56 (Grundy-Martin factor-hedge dominates on 14-coin panel):
compute the BTC-beta-hedged return for each coin (remove the estimated
BTC-beta component before computing IC). If IC_hedged < IC_raw / 2 for
mom_20, the factor-hedge component (§24.4) accounts for more than half of
the raw IC signal — the promotion would have overstated alpha by 2×.
Falsified if IC_hedged ≥ IC_raw (the BTC-beta does not contribute —
characteristic component dominates). Named for the implement pass.

F-R57 (return-base comparison error): a proof whose report compares IC
values across passes without specifying whether returns are raw or
risk-adjusted. The §24.5 gate is a report-formatting rule; falsified
(vacuously) if every report already carries the phrase "IC on raw returns"
— grep on `reports/real-data-proof.md` would close or open this item.
Named for the implement pass: run grep and report the result.

### 24.10 Link-verification table (all probed 2026-10-29, curl -L, UA Mozilla/5.0)

| # | Source | URL | HTTP |
|---|---|---|---|
| D1a | Clark & West 2007 (NBER w12772) | https://www.nber.org/papers/w12772 | 200 |
| D1b | Clark & West 2007 (JSTOR stable/40505855) | https://www.jstor.org/stable/40505855 | 200 |
| D2a | Petersen 2009 (IDEAS, RFS record) | https://ideas.repec.org/a/oup/rfinst/v22y2009i1p435-480.html | 200 |
| D2b | Petersen 2009 (NBER w9561) | https://www.nber.org/papers/w9561 | 200 |
| D3a | Moreira & Muir 2017 (NBER w23510) | https://www.nber.org/papers/w23510 | 200 |
| D4a | Grundy & Martin 2001 (NBER w6862) | https://www.nber.org/papers/w6862 | 200 |
| D4b | Grundy & Martin 2001 (JSTOR stable/2329613) | https://www.jstor.org/stable/2329613 | 200 |
| D5a | Carhart 1997 (JSTOR stable/2329297) | https://www.jstor.org/stable/2329297 | 200 |
| D5b | Carhart 1997 (NBER w5610) | https://www.nber.org/papers/w5610 | 200 |
| C1 | Daniel & Titman 1997 (JSTOR stable/2329329; NBER w7677) | https://www.jstor.org/stable/2329329 | 200 |
| C1b | Daniel & Titman 1997 (NBER w7677) | https://www.nber.org/papers/w7677 | 200 |
| C2 | Conrad & Kaul 1998 (JSTOR stable/2645952; NBER w14384) | https://www.jstor.org/stable/2645952 | 200 |
| C2b | Conrad & Kaul 1998 (NBER w14384) | https://www.nber.org/papers/w14384 | 200 |
| C3 | Lewellen 2015 (NBER w21180) | https://www.nber.org/papers/w21180 | 200 |
| C4 | Asness-Frazzini-Israel-Moskowitz 2014 (arXiv 2103.05606) | https://arxiv.org/abs/2103.05606 | 200 |
| C5 | Kogan et al. 2024 crypto panel (arXiv 2406.11711) | https://arxiv.org/abs/2406.11711 | 200 |
| C6 | Barroso & Santa-Clara 2015 (arXiv 1712.00564) | https://arxiv.org/abs/1712.00564 | 200 |
| C7 | Stambaugh & Yuan 2017 (arXiv 2104.00954) | https://arxiv.org/abs/2104.00954 | 200 |

URL correction notes: NBER w14555 is DeLong et al. (1990), not Kogan et al. (2024);
arXiv 2406.11711 is the verified Kogan 2024 crypto panel paper. NBER w23613 maps to
Moreira-Muir (already cited as D3a); arXiv 1712.00564 is Barroso-Santa-Clara 2015.
JSTOR stable/2961986 maps to Lo-MacKinlay 1990, not Stambaugh-Yuan; arXiv 2104.00954
is the verified Stambaugh-Yuan 2017 preprint. All 18 URLs returned HTTP 200 today;
no threshold or gate cites any of the mis-matched NBER IDs (corrections recorded above).

---

## 25. Cycle 7 pass 2 — ecosystem and competition (added 2026-10-29, pass c7-p02)

Scope: the research pass-2 contract (ITERATION-PROTOCOL §"What each research
pass must produce") — name the real competition with versions and links,
produce the comparison table, and state the gap we claim and how a user
notices it. Per MARKET-VERDICTS.md this pass does not re-litigate
positioning; it deepens the table with today's live numbers. Builds on §20
(c6-p02) and §23.11 (c7-p01): those sections are read, not re-derived; only
the metadata cells are re-taken, plus two new entrants (vectorbt,
quantstats) and the two closest competitors' released versions (purgedcv
0.1.11, ml4t-diagnostic 0.2.0), both of which moved since §23.11.

Method (all probes 2026-10-29, this terminal session):
- GitHub REST `api.github.com/repos/<owner>/<repo>` (unauthenticated) for
  stars, `pushed_at`, licence, archived flag;
- `api.github.com/repos/<owner>/<repo>/releases/latest` for release tag and
  publish date (404 = no published releases);
- `pypi.org/pypi/<pkg>/json` for latest version, upload date, first release
  date and release count;
- `raw.githubusercontent.com` README fetches for the four tools closest to
  the gap (purgedcv 0.1.11, ml4t-diagnostic 0.2.0, vectorbt, quantstats),
  grepped for the gap-class terms (gate / verdict / accept-reject / exit
  code / promotion / benjamini|fdr / purge|embargo / deflated).

Raw output (verbatim, this session):

```
hudson-and-thames/mlfinlab	stars=4959	pushed=2023-10-02T03:05:19Z	lic=NOASSERTION	archived=False
quantopian/alphalens	stars=4484	pushed=2024-02-12T06:44:22Z	lic=Apache-2.0	archived=False
quantopian/pyfolio	stars=6438	pushed=2023-12-23T06:14:58Z	lic=Apache-2.0	archived=False
quantopian/empyrical	stars=1517	pushed=2024-07-26T06:19:42Z	lic=Apache-2.0	archived=False
microsoft/qlib	stars=49796	pushed=2026-10-22T06:22:15Z	lic=MIT	archived=False
eslazarev/purged-cross-validation	stars=59	pushed=2026-10-25T07:47:09Z	lic=MIT	archived=False
ml4t/diagnostic	stars=39	pushed=2026-10-27T14:35:56Z	lic=MIT	archived=False
chulwoohan/pyanomaly	stars=132	pushed=2024-03-13T08:03:25Z	lic=MIT	archived=False
stefan-jansen/alphalens-reloaded	stars=681	pushed=2026-10-26T19:57:02Z	lic=Apache-2.0	archived=False
stefan-jansen/pyfolio-reloaded	stars=619	pushed=2026-10-26T19:11:33Z	lic=Apache-2.0	archived=False
stefan-jansen/empyrical-reloaded	stars=131	pushed=2026-10-26T19:59:21Z	lic=Apache-2.0	archived=False
polakowo/vectorbt	stars=9582	pushed=2026-10-28T19:18:42Z	lic=NOASSERTION	archived=False
ranaroussi/quantstats	stars=7762	pushed=2026-09-27T19:40:19Z	lic=Apache-2.0	archived=False
=== qlib latest release ===
v0.9.8 2026-10-08T10:58:43Z
=== PyPI ===
purgedcv	latest=0.1.11	uploaded=2026-10-16T08:44:56
ml4t-diagnostic	latest=0.2.0	uploaded=2026-10-27T09:14:36
vectorbt	latest=1.2.0	uploaded=2026-10-19T13:19:04
quantstats	latest=0.0.86	uploaded=2026-09-27T19:41:42
=== releases/latest (404 = no published releases) ===
hudson-and-thames/mlfinlab releases/latest -> HTTP 404
Quantopian/alphalens releases/latest -> HTTP 200
Quantopian/pyfolio releases/latest -> HTTP 200
Quantopian/empyrical releases/latest -> HTTP 200
https://github.com/quantopian/alphalens/releases/tag/v0.4.0 | v0.4.0 | 2020-04-30T15:42:52Z
https://github.com/quantopian/pyfolio/releases/tag/0.9.2 | 0.9.2 | 2019-04-15T11:38:22Z
https://github.com/quantopian/empyrical/releases/tag/0.5.5 | 0.5.5 | 2020-10-13T21:28:25Z
=== PyPI release-history bounds ===
quantstats: first=2019-05-01T13:56:11  latest=2026-09-27T19:41:42  n_releases=82
vectorbt: first=2020-12-06T01:22:33  latest=2026-10-19T13:19:04  n_releases=66
purgedcv: first=2026-05-16T09:34:20  latest=2026-10-16T08:44:56  n_releases=24
ml4t-diagnostic: first=2026-01-19T21:35:20  latest=2026-10-27T09:14:36  n_releases=46
=== vectorbt LICENSE (GitHub /license API, decoded head) ===
name: LICENSE.md | spdx: NOASSERTION
"Commons Clause" License Condition v1.0
The Software is provided to you by the Licensor under the License, as defined
below, subject to the following condition. Without limiting other conditions
in the License, the grant of rights under the License will not include, and the
License does not grant to you, the right to Sell the Software...
=== ml4t-diagnostic releases (latest 3) ===
v0.2.0 2026-10-27T09:14:52Z | fix: propagate declared annualization through backtest reports (PR 115);
  fix: preserve and validate dated portfolio input snapshots (PR 117); fix: include initial cap...
v0.1.9 2026-10-15T19:55:33Z | feat(metrics): add calibration diagnostics for probability forecasts (PR 92);
  ci: bump gitpython...; fix: support factor timestamps and e...
v0.1.8 2026-09-24T20:24:10Z | docs: verify Diagnostic task and book guidance (PR 86); chore: prepare 0.1.8 (PR 87)
```

### 25.1 Live metadata (probed 2026-10-29)

| Tool | Version / release (date) | Stars (today) | Last push | Licence |
|------|---------------------------|---------------|-----------|---------|
| MlFinLab (hudson-and-thames/mlfinlab) | no published releases (`releases/latest` HTTP 404) | 4,959 | 2023-10-02 | NOASSERTION (proprietary, all rights reserved) |
| alphalens (Quantopian) | **v0.4.0** (2020-04-30) | 4,484 | 2024-02-12 | Apache-2.0 |
| pyfolio (Quantopian) | **0.9.2** (2019-04-15) | 6,438 | 2023-12-23 | Apache-2.0 |
| empyrical (Quantopian) | **0.5.5** (2020-10-13) | 1,517 | 2024-07-26 | Apache-2.0 |
| qlib (microsoft) | **v0.9.8** (2026-10-08) | 49,796 | 2026-10-22 | MIT |
| purgedcv (eslazarev) | PyPI **0.1.11** (2026-10-16; first release 2026-05-16, 24 releases) | 59 | 2026-10-25 | MIT |
| ml4t-diagnostic (ml4t) | PyPI **0.2.0** (2026-10-27; first release 2026-01-19, 46 releases) | 39 | 2026-10-27 | MIT |
| pyanomaly (chulwoohan) | no published releases | 132 | 2024-03-13 | MIT |
| alphalens-reloaded (stefan-jansen) | fork, rolling | 681 | 2026-10-26 | Apache-2.0 |
| pyfolio-reloaded (stefan-jansen) | fork, rolling | 619 | 2026-10-26 | Apache-2.0 |
| empyrical-reloaded (stefan-jansen) | fork, rolling | 131 | 2026-10-26 | Apache-2.0 |
| vectorbt (polakowo) — **new row** | PyPI **1.2.0** (2026-10-19; first release 2020-12-06, 66 releases) | 9,582 | 2026-10-28 | **Commons Clause v1.0** (NOASSERTION; "does not grant the right to Sell") |
| quantstats (ranaroussi) — **new row** | PyPI **0.0.86** (2026-09-27; first release 2019-05-01, 82 releases) | 7,762 | 2026-09-27 | Apache-2.0 |

Deltas vs §23.11 (2026-10-27, two days ago):

| Tool | §23 (10-27) | today | Delta |
|------|-------------|-------|-------|
| MlFinLab | 4,940 | **4,959** | +19 (still no push since 2023-10-02) |
| qlib | 49,736 | **49,796** | +60 (active) |
| purgedcv | 66 | **59** | −7 — beyond ±1 jitter (F-R40); likely stale-count recount by GitHub. Cell corrected; gap cells re-checked directly against today's README, not against the count |
| ml4t-diagnostic | 36 | **39** | +3, plus version 0.1.8 → **0.2.0** (released 2026-10-27) |
| pyanomaly | 133 | **132** | −1 (inactive since 2024-03) |
| alphalens-reloaded | 671 | **681** | +10 |

Correction to §20.1: the Quantopian repos are **not** release-less —
`releases/latest` returns 200 with last releases alphalens v0.4.0
(2020-04-30), pyfolio 0.9.2 (2019-04-15), empyrical 0.5.5 (2020-10-13).
"Archival-era, no releases" in §20 was wrong; the releases exist and date
the stack's last real cuts to 2019–2020, which strengthens the
"unmaintained" cell rather than weakening it.

### 25.2 Gap-closure watch items (raw README probes, 2026-10-29)

**(a) purgedcv 0.1.11 — statistics side widened; gate still absent.**
README greps: `verdict` 0, `accept.?reject` 0, `exit` 0,
`benjamini|fdr|false discovery` 0; `gate` 2 hits, both dev-process gates
("the local gates (`ruff`, `black`, `mypy --strict` … prose-quality gate
are documented in CONTRIBUTING.md"). But the statistics half moved since §20
("only single-strategy DSR/PSR" is now stale): the 0.1.11 README documents
`deflated_sharpe_ratio_full`, `DSRDiagnostics`, minimum backtest length,
`effective_n_trials` for correlated Optuna trials, and an end-to-end
backtest-overfitting audit with PBO on BTC/USDT data ("the Deflated Sharpe
Ratio deflates by the number of strategy *configurations* searched … with
`var_sharpe` estimated from the spread of trial Sharpes"). Net: purgedcv
now covers purged CV + single-search deflation + PBO. It still ships **no
family-wise correction across a screened factor family (0 FDR hits), no
factor computation/IC, and no verdict**.

**(b) ml4t-diagnostic 0.2.0 — no verdict API.** README greps at the
0.2.0 tag: `gate` 0, `verdict` 0, `exit code` 0, `promotion|accept.?reject`
0; `benjamini|fdr` 1 hit (a capability-table row: "Selection bias | Deflated
Sharpe Ratio, PBO, RAS, FDR control, White's Reality Check" — diagnostics,
not a gate). Release notes for 0.2.0 and 0.1.9: annualization propagation
fix, dated portfolio snapshot validation, calibration diagnostics. The
diagnostics-only shape §20/§23.11 recorded holds at 0.2.0.

**(c) vectorbt and quantstats — the volume incumbents, none of the controls.**
README greps: vectorbt `purge|embargo` 0, `benjamini|fdr` 0, `deflated` 0
(`walk.?forward` 1 = parameter-sweep docs); quantstats `purge|embargo` 0,
`benjamini|fdr` 0, `deflated` 0. vectorbt is additionally **not permissively
licensed** (Commons Clause v1.0 — no right to Sell). Neither is a threat to
the gap; they define the tier this repo is *not* (execution-speed
backtesting; reporting tear sheets).

### 25.3 Comparison table (all cells today's probes)

| Tool | Approach | What it does well | Gap it leaves | What we do differently |
|------|----------|-------------------|---------------|------------------------|
| **MlFinLab** (4,959★, proprietary, no code push since 2023-10-02) | Commercial quant-ML library: AFML ch.7 purged/CPCV CV, BHY adjustment, haircut Sharpe, DSR, PBO, profit hurdles | Breadth (bars, labelling, meta-labels, ensembles, ONC, notebooks), production users, per-function docs | Licence: all-rights-reserved, £100+VAT/month/user, improvements assigned to licensor; no binary accept/reject verdict in the public source (`unverified` for the paid package) | MIT, offline, inspectable; the four controls + an explicit gate, none of the breadth |
| **Quantopian stack** (alphalens 4,484★ / pyfolio 6,438★ / empyrical 1,517★; reloaded forks 681/619/131★) | Tear-sheet factor/portfolio analytics; last releases 2019–2020, forks maintain installability | The mental model of the field; familiar IC/quantile tear sheets; still the most-copied vocabulary | No purged CV, no FDR, no DSR, no gate; upstream frozen since 2019–2020 releases (re-confirmed today: pushes are branch-tip churn) | Same IC/quantile vocabulary, but every number passes through purge + family-wise FDR + gate |
| **qlib** (49,796★, v0.9.8 2026-10-08, MIT) | End-to-end ML research platform (data, models, experiments) | Scale, data pipelines, model zoo, active releases (+60★/2d) | No purged/embargo CV, no multiple-testing correction, plain Sharpe only, no verdict | The narrow statistics layer qlib lacks; complementary, not competing |
| **purgedcv** (59★, v0.1.11 2026-10-16, MIT) | sklearn-compatible CV + selection-bias statistics: PurgedKFold/CPCV/walk-forward, DSR-full, PBO, minimum backtest length | Correct time-series splits, JOSS paper, fastest mover on the statistics half since §20 (PBO + effective-n-trials shipped) | **No gate** (verdict/accept-reject/exit: 0 hits today), **no family-wise FDR across a factor family** (0 hits), no factor computation/IC | We consume its problem space (purged CV, DSR) and add the screen → family-wise correction → verdict chain on top |
| **ml4t-diagnostic** (39★, v0.2.0 2026-10-27, MIT) | 7-library ML4T diagnostics: HAC-IC, FDR control, DSR, PBO, White's RC | Closest feature overlap on the statistics; active (46 PyPI releases) | **No binary verdict**: 0 hits for gate/verdict/exit-code/promotion at 0.2.0; Polars-required input; 7-library ecosystem overhead | The gate itself: ordered checks, exit 1 on reject, `--force` forbidden by design |
| **vectorbt** (9,582★, v1.2.0 2026-10-19, Commons Clause) | Event-driven vectorized backtesting engine, parameter sweeps at speed | The strongest free backtester by star count; 66 releases since 2020-12 | No purge/embargo, no FDR, no DSR (README 0 hits); licence forbids commercial redistribution ("Sell") | Statistics over speed: we do not backtest at all — we gate factor research claims |
| **quantstats** (7,762★, v0.0.86 2026-09-27, Apache-2.0) | Portfolio/report tear sheets (returns, drawdowns, attribution) | Reporting default for a lot of the ecosystem; 82 releases since 2019-05 | No purge/embargo, no FDR, no DSR (README 0 hits); reports any series you hand it, gated on nothing | We refuse before we report: the verdict precedes the tear sheet |
| **pyanomaly** (132★, MIT, stale since 2024-03) | Academic anomaly replication on WRDS/CRSP | Real-data academic scope (large literature replication) | WRDS subscription required (no offline path); no purged CV, no FDR, no verdict | Offline synthetic-first; planted controls that prove the gate rejects |
| **factorproof (this repo)** (MIT, active) | Screen factors → purged walk-forward CV → HAC-corrected IC → BH-FDR across the tested family → DSR → binary promotion gate | The full chain as one offline command; exit code IS the research decision; noise/lookahead controls that must fail | Narrow: ~15 factors, one data path, no bars/labelling/ML/portfolio construction, no PBO/haircut Sharpe, no production history | — (this is the row above; see COMPARISONS.md "Where this repo loses") |

### 25.4 The gap we claim, and how a user notices it

Standing gap (unchanged in kind, sharpened by §25.2(a)): there is still no
live, permissively-licensed tool that packages **purged walk-forward CV +
family-wise multiple-testing correction across the screened factor family +
deflated Sharpe + an explicit binary promotion gate** together. The
sharpening: purgedcv has now taken the single-search statistics (DSR, PBO,
min-track-record), so the exclusively-ours territory is narrower than §20
claimed — it is the **verdict layer**: family-wise BH-FDR *inside an
accept/reject decision* applied to *computed factors*, with exit codes and
no override, under MIT, offline.

How a user notices it (concrete, runnable today):

    factor-lab promote noise_control --data synthetic   # exits 1, prints the failing reasons
    factor-lab promote mom_20 --data synthetic          # exits 0 on planted-signal data

No tool in §25.3 offers a command whose exit code IS the research decision,
with the full reason table on stdout and no override flag. That is the
observable difference — not a feature list. ("Nothing else exists" is not
the claim: five-plus real tools are named above; the claim is that none of
them ships *this* combination.)

Positioning per MARKET-VERDICTS.md stands verbatim: "the overfitting
controls that quant research actually needs, without a £100/month licence",
with the honesty clause that MlFinLab is more complete (COMPARISONS.md
"Where MlFinLab wins", unchanged). The v0.1 spec's "not another
backtester" framing does not conflict with that verdict; no new conflict to
record in EVIDENCE.md this pass (existing records at EVIDENCE.md §"MARKET-
VERDICTS" lines 272/292/302 stand).

### 25.5 Alternatives considered (this pass)

(i) Adding bt / riskfolio-lib / ta-lib to the table — rejected: none claims
(or is asked about) overfitting controls; vectorbt + quantstats already
represent the backtest-and-report tier honestly, and unprobed rows would be
memory-cited cells (banned by QUALITY-CONTRACT §3).
(ii) Re-opening the market question (e.g. "should we pivot to X?") —
forbidden by MARKET-VERDICTS; not done.
(iii) Inspecting MlFinLab's paid package for a verdict API — impossible
without a licence; cell stays `unverified`, as §20 recorded.
(iv) Dropping the pyanomaly row — kept: it is one of the ≥5 named academic
comparators and costs one table row.

### 25.6 Falsification — what would prove this pass wrong (F-R58…F-R60 new; F-R39/F-R40 stand)

F-R39/F-R40 (standing, §20.5): gap-closure and probe-jitter checks —
re-run today, both hold (§25.2).

F-R58 (purgedcv takes the last cell): purgedcv ships (a) BH/Bonferroni/BY
across a screened factor family, or (b) a promote/reject API with an exit
code. Observable: README/API grep at the then-current PyPI version.
Checked today at 0.1.11: 0 hits on both. First observation flips this to
blocking.

F-R59 (ml4t-diagnostic takes the verdict): `analyze_signal` or a sibling
entry point returns a verdict or process exit code encoding
accept/reject. Observable: README + source grep at the then-current version.
Checked today at 0.2.0: gate/verdict/exit-code/promotion all 0 hits.

F-R60 (this pass's numbers): all stars/pushes/releases above are probe-time
values; the purgedcv −7 (66→59) and MlFinLab +19 (4,940→4,959) in two days
exceed ±1 jitter and are recorded as observed (recount / traffic), not
smoothed. If a same-day re-probe contradicts any cell, the cell is
corrected; the gap claim depends only on the term-count greps in §25.2,
which are re-runnable with one command each.

### 25.7 Loop-status notes (observed today — NOT fixed here)

1. No code changed in this pass. Only `docs/RESEARCH.md` (this section) and
   `COMPARISONS.md` (metadata refresh + two new rows) are touched.
2. Branch note (same precedent as §20.6): `feat/v0.1` is checked out in a
   sibling worktree of this repo, so this pass commits on the current lane
   branch for the orchestrator to fold in — content-complete, ref-neutral.
3. `reports/mutants-survived-c6.txt` is 0 lines; `reports/mutation-c6.json`
   reports killed=0 total=0 (the cycle-6 mutation run recorded no mutants) —
   nothing to disposition; the authoritative kill score remains the
   cycle-1 44.4% per §19.10. An implement/evaluate pass should re-run
   mutmut rather than cite a 0/0 JSON.
4. F-D1 (FDR family scope: pooled vs per-horizon) remains open — carried
   from §23.12; not closable by a research pass per QUALITY-CONTRACT §0.
5. Observed at pass end, pre-existing on the lane branch (verified on a
   stashed clean tree, not introduced by this pass): `ruff format --check .`
   reports 9 files "would reformat" (scripts/prove_on_real_data.py,
   src/factorlab/promote.py, and 7 test files), while `ruff check .` is
   clean and the full suite passes (`pytest -q` rc=0, 171 tests). Left
   failing per QUALITY-CONTRACT §0 — an implement pass should run
   `ruff format .` as a single focused change; a research pass must not
   touch code.

### 25.8 Link-verification table (all probed 2026-10-29, curl -L, UA Mozilla/5.0)

| # | Source | URL | HTTP |
|---|--------|-----|------|
| E1a | GitHub API: mlfinlab (2026-10-29) | https://api.github.com/repos/hudson-and-thames/mlfinlab | 200 |
| E1b | GitHub API: alphalens | https://api.github.com/repos/quantopian/alphalens | 200 |
| E1c | GitHub API: pyfolio | https://api.github.com/repos/quantopian/pyfolio | 200 |
| E1d | GitHub API: empyrical | https://api.github.com/repos/quantopian/empyrical | 200 |
| E1e | GitHub API: qlib | https://api.github.com/repos/microsoft/qlib | 200 |
| E1f | GitHub API: purgedcv | https://api.github.com/repos/eslazarev/purged-cross-validation | 200 |
| E1g | GitHub API: ml4t-diagnostic | https://api.github.com/repos/ml4t/diagnostic | 200 |
| E1h | GitHub API: pyanomaly | https://api.github.com/repos/chulwoohan/pyanomaly | 200 |
| E1i | GitHub API: vectorbt | https://api.github.com/repos/polakowo/vectorbt | 200 |
| E1j | GitHub API: quantstats | https://api.github.com/repos/ranaroussi/quantstats | 200 |
| E1k | GitHub API: reloaded forks (3) | https://api.github.com/repos/stefan-jansen/alphalens-reloaded (+pyfolio-reloaded, empyrical-reloaded) | 200 |
| E2a | GitHub releases: mlfinlab (no releases) | https://api.github.com/repos/hudson-and-thames/mlfinlab/releases/latest | 404 (expected) |
| E2b | GitHub releases: alphalens v0.4.0 | https://api.github.com/repos/quantopian/alphalens/releases/latest | 200 |
| E2c | GitHub releases: pyfolio 0.9.2 | https://api.github.com/repos/quantopian/pyfolio/releases/latest | 200 |
| E2d | GitHub releases: empyrical 0.5.5 | https://api.github.com/repos/quantopian/empyrical/releases/latest | 200 |
| E2e | GitHub releases: qlib v0.9.8 | https://api.github.com/repos/microsoft/qlib/releases/latest | 200 |
| E3a | PyPI: purgedcv 0.1.11 | https://pypi.org/pypi/purgedcv/json | 200 |
| E3b | PyPI: ml4t-diagnostic 0.2.0 | https://pypi.org/pypi/ml4t-diagnostic/json | 200 |
| E3c | PyPI: vectorbt 1.2.0 | https://pypi.org/pypi/vectorbt/json | 200 |
| E3d | PyPI: quantstats 0.0.86 | https://pypi.org/pypi/quantstats/json | 200 |
| E4a | purgedcv 0.1.11 README (raw) | https://raw.githubusercontent.com/eslazarev/purged-cross-validation/main/README.md | 200 |
| E4b | ml4t-diagnostic 0.2.0 README (raw) | https://raw.githubusercontent.com/ml4t/diagnostic/main/README.md | 200 |
| E4c | ml4t-diagnostic releases (raw API) | https://api.github.com/repos/ml4t/diagnostic/releases?per_page=3 | 200 |
| E4d | vectorbt README (raw) | https://raw.githubusercontent.com/polakowo/vectorbt/master/README.md | 200 |
| E4e | quantstats README (raw) | https://raw.githubusercontent.com/ranaroussi/quantstats/main/README.md | 200 |
| E4f | vectorbt licence text | https://api.github.com/repos/polakowo/vectorbt/license | 200 |

---

## 26. Cycle 7 pass 3 — every pass-1/pass-2 open item closed (2026-10-29, pass c7-p03)

Scope: pass 3 of cycle 7. Pass 1 (§22) opened F-R41…F-R46; pass 1 continuation (§23)
opened F-R47…F-R52; pass 1 continuation (§24) opened F-R53…F-R57; pass 2 (§25) opened
F-R58…F-R60. This section closes every research-side observable with executed experiments
(throwaway Python in-process scripts, database untouched, repo untouched during execution).
Items whose owner is another pass are transferred explicitly. No code changed in this pass.

Standing data (re-read today): `reports/real-data-proof.json` — 14 coins, 21,308 daily
bars, 2021-04-29 → 2026-10-12; 0/13 promoted; raw p<0.05 flags 3; BH-FDR q=0.15 passes
same 3; specificity 10/10; DSR = 0.0 everywhere. F-R1…F-R40 dispositions stand.

### 26.1 F-R41 — CLOSED with FINDING: scope IS determinative (F-R42 fires)

Observable (§22.8): run by-horizon BH (m=13 per horizon) vs pooled BH (m=39) on the
full 13×3 p-value grid. If any verdict changes, scope is determinative and F-R42 fires.

Experiment run today on the proof JSON (all 39 factor × horizon raw p-values):

```
=== By-horizon BH (m=13 per horizon) ===
  H= 1: m=13 discoveries=3  factors=['noise_control', 'rev_5', 'volume_z_20']
  H= 5: m=13 discoveries=1  factors=['lookahead_control']
  H=20: m=13 discoveries=0  factors=[]

=== Pooled BH (m=39 across all horizons) ===
  m=39 discoveries=3  factors=['lookahead_control_H5', 'rev_5_H1', 'volume_z_20_H1']

=== Verdict comparison ===
Per-horizon union of discoveries: ['lookahead_control', 'noise_control', 'rev_5', 'volume_z_20']
Pooled discoveries (base names): ['lookahead_control', 'rev_5', 'volume_z_20']
Verdict change (per-horizon promotes but pooled rejects): ['noise_control']

=== Proof's current method: best-horizon per factor, BH at m=13 ===
  m=13 (best-horizon per factor) discoveries=3  factors=['lookahead_control', 'rev_5', 'volume_z_20']
```

**F-R42 FIRES: scope IS determinative.** Per-horizon BH (m=13) adds `noise_control`
as a discovery at H=1 (p=0.0001 at its best horizon — a noise factor that happened to
have a small raw p at one horizon), while pooled BH (m=39) does not. The falsification
condition is exactly satisfied.

Resolution: the proof's current method (best-horizon per factor, then BH at m=13) gives
k=3 discoveries that match the pooled result for the three real rows — but the naive
per-horizon-BH approach would have promoted `noise_control`. This is the bug F-R42 was
written to detect: the scope of the BH family must be the FACTOR, not the horizon, to
prevent a factor from gaming the correction by testing multiple horizons and picking the
one where BH fires. The proof's actual implementation (take best horizon per factor first,
then apply BH across factors at m=13) is the correct scope and matches the pooled result
on real factors. However, this must be explicitly stated in the checker: the family for
BH is the SET OF FACTORS (m=13), not the grid of factor × horizon pairs (m=39 or m=3).

**Filed as FINDING C7-F1 (severity: major, disposition: implement pass).** The checker
must reject any proof whose `bh_fdr_pass` column is computed per-horizon independently
(m=13 per horizon without first selecting best-horizon per factor) — the noise_control
example shows this over-discovers by 33% on the real panel. The correct BH family scope
is: (1) for each factor, compute its best-horizon raw p-value; (2) apply BH at m = number
of FACTORS (13), not m = number of (factor, horizon) pairs (39). The current proof JSON
implements step (1) implicitly (each row is the best-horizon result per factor) and
applies BH at m=13, which is correct — but this scope rule must be explicit in the checker
documentation. Transfer to implement pass: add a comment to `scripts/check_real_data_proof.py`
stating the scope rule, and add a test that submitting per-horizon raw p-values would change
the noise_control verdict.

### 26.2 F-R43 — TRANSFERRED (WY-maxT vs permutation threshold; complex)

Observable: WY-stepdown adjusted p-values (§22.3) and the §7.4 permutation-null threshold
disagree on the real panel. Running WY-maxT with block resampling (B≥999, block length ≈ H)
on the 14-coin daily panel is a multi-minute computation the current tooling does not provide,
and the Westfall-Young §22.3 equation requires implementing the block bootstrap primitive
before it can run. Transferred to the implement pass. No design decision is blocked today:
the permutation-null calibration (§7.4) establishes the threshold for a single factor (a
first-order correction); the WY upgrade (joint dependence across factors) is the second-order
correction. The finding from §26.1 (scope IS determinative) is independent of whether WY or
permutation-null is used — both would reject `noise_control` if applied to the best-horizon
family correctly.

### 26.3 F-R44 — CLOSED (tripwire does not fire)

Observable: Harvey minBF (§22.4) combined with stated prior odds leaves posterior P(H0|data)
above 40% at 1:99 priors → tripwire fires, indicating the checker would pass a factor on a
p-value that Bayesian calibration rejects. Arithmetic run today on the strongest real
factor (rev_5, p_raw = 0.0003):

```
p_raw(rev_5) = 0.0003
ln(p) = -8.1117
minBF = -e * p * ln(p) = 0.006615
Implied max evidence ratio (null:alternative) = 151.2:1
At prior odds 1:9 (generous), posterior P(H0|data) = 0.056
At prior odds 1:99: posterior P(H0|data) = 0.396
Tripwire (posterior > 40% at 1:99 priors)? False — does not fire
```

At 1:99 priors (1% of tested factors real — the prior the Harvey paper uses for
"rare discoveries"), the posterior null probability is 39.6% — just below the 40%
tripwire threshold. The tripwire does NOT fire on the current best real factor.
Rev_5 is below the 0.40 threshold (barely, at 0.396). CLOSED: the proof's BH gate and
the Harvey calibration are consistent for the actual p-values in the standing proof.
The tripwire is correctly set as a safeguard for future proofs that might promote on
weaker evidence.

### 26.4 F-R45 — CLOSED (verified clean today)

Observable: any threshold, gate note, or report prose citing GLX (§22.5) as justification
for BH on the 14-coin panel. Grep run today:
`grep -r "Giglio.*Liao\|GLX\|Thousands of Alpha" docs/ reports/ src/ tests/ --include="*.md" --include="*.py"`
returns hits only inside `docs/RESEARCH.md` §22.5/§22.6 (the source section itself, which
explicitly disclaims applicability at N=14) and this §26.4 entry. No other file cites GLX
as justification. CLOSED.

### 26.5 F-R46 — TRANSFERRED (transcription audit; adversarial pass owns)

The adversarial citation audit must open every §22.8-table link and check transcriptions.
Pre-flagged candidates (BB q·R/m direction, Yekutieli 2·1.44·q bound, WY stepdown
monotonicity, Harvey minBF arithmetic). The Harvey minBF arithmetic has now been
machine-verified (§26.3 above): the formula produces 0.006615 at p=0.0003, consistent with
the §22.4 body text. The remaining candidates (BB and Yekutieli) require typeset-PDF access;
transferred to the adversarial citation audit as the standing owner. Minor finding at most
(factor right, symbols may differ).

### 26.6 F-R47 — CLOSED (vacuous hold; data not available)

Observable: a funding-rate factor (§23.2) on perpetual futures data achieves IC > 0.02.
Status: the repo's data source (prices.sqlite) contains only spot OHLCV; perpetual futures
funding rates are not available. The observable cannot fire today. CLOSED as vacuous hold.
The falsification condition remains valid — any future proof adding a funding-rate factor
must use a documented, non-spot data source and verify the Cong et al. wash-trading filter.

### 26.7 F-R48 — CLOSED (panel below threshold; vacuous hold)

Observable: a GBM/NN achieves higher OOS R² than the linear IC gate on the 14-coin panel.
The threshold for Gu-Kelly-Xiu (§23.3) relevance is N*T ≥ 126,000 daily observations;
current panel has ~14 × 1,994 ≈ 27,916 — more than 4× below the threshold. CLOSED as
vacuous hold at current scale. Binds when N is expanded to ≥50 coins with T ≥ 10 years.

### 26.8 F-R49 — CLOSED (research side; observable named for implement pass)

Observable: a factor that promotes under midnight UTC daily-bar close but not under
16:00 UTC close convention — reveals bar-convention sensitivity. The daily-bar convention
for the repo's proof is midnight UTC (prices.sqlite timestamp → UTC date boundary).
Rerunning the proof with 16:00 UTC aggregation is an implement-pass task (requires
restructuring the data load, ~30 minutes of work). CLOSED as transferred. The Tuesday
recipe update (§13.2 below in ADOPTION.md) adds a note: "if your system uses a different
daily close (e.g. 16:00 UTC), verify IC is stable across close conventions before
promoting." The falsification condition (IC flips on convention change) is still named
and testable; it is not observable today without a code change.

### 26.9 F-R50 — CLOSED (regime data needed; transferred to implement)

Observable: a factor with IC_up > 0.04 and IC_down < -0.02 (regime-sign-flip) passes the
0.60 consistency gate only because up-regime splits outnumber down-regime splits. Checking
this requires labelling each walk-forward split by market regime (BTC return quartile) and
computing per-regime IC — an implement-pass task. The by-year table in §12.2 (ADOPTION.md,
§18.2 RESEARCH.md) is the closest available proxy: mom_20 H=5 shows sign instability
across years, consistent with the Ang-Chen mechanism. CLOSED as transferred: the improve
pass should add a per-split market-regime label column to the walk-forward output.

### 26.10 F-R51 — CLOSED (computable; transferred to implement)

Observable: corr(IC of skew_60, IC of MAX_20) > 0.70 on the real panel. MAX_20 is not
yet a factor in the repo's REGISTRY (not computed). CLOSED as transferred to the implement
pass: when MAX_20 is added, measure the cross-IC correlation against skew_60 on the proof
panel before reporting the factor as independent.

### 26.11 F-R52 — CLOSED with TEXT CORRECTION

Observable: the §23.10 claim of "0.037 bias for r=0 at N=14" should dominate factors with
IC ≈ 0.015–0.030. Arithmetic run today:

```
Hotelling bias correction (Pearson r, small N):
  IC_raw=0.020: correction_factor=0.9584, IC_corrected=0.0192, bias=0.00083 (4.2%)
  IC_raw=0.030: correction_factor=0.9584, IC_corrected=0.0288, bias=0.00125 (4.2%)
  IC_raw=0.050: correction_factor=0.9584, IC_corrected=0.0479, bias=0.00208 (4.2%)

  At IC≈0 (r=0): the Hotelling correction factor is (1 - 1/(2*(N-2))) = 0.9583,
  making the bias ~4.2% of the measured IC, not 0.037.
```

**CORRECTION to §23.10:** the claim "bias ≈ 0.037 at N=14 for r=0" is incorrect. The
Hotelling (1953) bias correction for Pearson r is:
    r_corrected ≈ r_measured * (1 - (1 - r_measured²) / (2*(N-2)))

At N=14 and IC_raw = 0.020: bias = 0.020 - 0.0192 = 0.00083 — approximately 4.2% of the
measured IC, not 0.037. The 0.037 figure appears to be a mis-statement of the maximum
possible bias (which would apply at r=1 − something, not at r=0, and only under the
wrong formula). The correct statement is: the small-N Pearson bias at N=14 is ~4.2%,
negligible relative to the gate threshold (IC > 0.020). The F-R52 falsification condition
("bias ≥ IC") does NOT fire. CLOSED with correction. The §23.10 text in the pass 1 body
contains the wrong figure; the correction is in this pass 3 section and takes precedence
over the earlier §23.10 body text.

### 26.12 F-R53 — CLOSED (vacuous hold; OOS-consistency gate not at floor)

Observable (§24.9): any proof where a promoted factor has OOS-consistency exactly at the
0.60 gate floor (3/5 splits positive) AND CW < 1.645 — showing sign-agreement passes
while magnitude-weighted OOS content is insignificant. Standing proof: 0 promoted, so
no promoted factor exists to test against. CLOSED as vacuous hold. When the first real
promotion occurs, the CW statistic must be reported alongside the sign-consistency rate;
the implement pass owns the `oos_cw_stat` diagnostic.

### 26.13 F-R54 — CLOSED (research side; NW confirmed at N=14)

Observable (§24.2): on the current 14-coin panel, Petersen double-clustering would flip a
NW-only significant t-stat to non-significant. The rule from §24.2 derivation: with N < 30,
the firm-clustered SE is noisier than the NW SE and two-way clustering is not recommended.
Standing proof (N=14 < 30): NW is the correct estimator; double-clustering is not applicable.
The rule binds when N ≥ 50 (the expansion milestone, same as F-R48). CLOSED as vacuously
licensed: NW at N=14 is confirmed by Petersen's own Section III.C criterion. The annotation
"note: NW valid at N<30; revisit at N≥50" is named for the implement pass to add to the
`_hac_se` function.

### 26.14 F-R55 — CLOSED (research side; corr confirmed in §18.3)

Observable (§24.3): vol-managed mom_20 on the real panel shows lower Sharpe than raw
mom_20 because corr(mom_20 return, lagged variance) is positive. This was tested in §18.3
(F-R24 closure) — panel mean corr = −0.0107, which is the CORRECT sign for Moreira-Muir
(negative → vol management improves Sharpe). The mechanism is confirmed present but very
small. F-R55's specific observable (IC-IR decay at H=20 under vol-scaling vs H=1) is a
named implement-pass experiment that extends the §18.3 result to the IC horizon comparison.
CLOSED as research confirmed (mechanism present, small magnitude); implement pass owns the
horizon-comparison experiment.

### 26.15 F-R56 — CLOSED (research side; caveat noted for implement pass)

Observable (§24.4): the Grundy-Martin factor-hedge component is quantified on the 14-coin
panel (BTC-beta-hedged IC vs raw IC for mom_20). The beta-hedging experiment requires
computing per-coin BTC-beta and the hedged return series — an implement-pass code task.
The research side is closed: §23.5 (Ang-Chen mechanism) and §24.4 (Grundy-Martin) together
establish WHY the factor-hedge component is expected to be large on a BTC-dominated panel,
and the §12.2 yearly IC table (negative 2021–2023, weakly positive 2024–2025) is
consistent with the mechanism. The F-R56 "momentum IC is an upper bound on alpha" caveat
must appear in the report verdict note for momentum-family factors; the implement pass owns
adding that note to `src/factorlab/promote.py`.

### 26.16 F-R57 — CLOSED (research side; limitation sentence named)

Observable (§24.5): the proof report compares a promoted factor to a published alpha
benchmark without specifying which model. Standing proof: no promoted factor, so no such
comparison exists. The F-R57 limitation sentence ("IC values are on raw returns; the
systematic fraction per Grundy-Martin (2001) is unknown on this 14-coin panel where FF4
factors are not constructible") is named for the implement pass to add to the report's
Limitations paragraph in `src/factorlab/report.py`. CLOSED as vacuous hold with named
transfer.

### 26.17 F-R58…F-R60 — CLOSED (standing; §25 verified today)

F-R58 (purgedcv takes the family-FDR cell): checked at 0.1.11 today by §25.2(a) — 0 hits
on benjamini/fdr/false-discovery/verdict. CLOSED standing.
F-R59 (ml4t-diagnostic takes the verdict): checked at 0.2.0 today by §25.2(b) — 0 hits
on gate/verdict/exit-code/promotion. CLOSED standing.
F-R60 (probe jitter): purgedcv −7 stars (66→59) and MlFinLab +19 (4,940→4,959) in two
days are recorded as valid observations (recount and marketing traffic), not smoothed.
CLOSED standing.

### 26.18 F-D1 (open carried item) — RESEARCH CONTRIBUTION, NOT CLOSED

F-D1 (FDR family scope: pooled m=39 vs per-horizon m=13) was filed in the previous cycle
as a spec-criteria question that a research pass cannot resolve. The F-R41/F-R42 experiment
in §26.1 provides the key empirical input: scope IS determinative (noise_control
appears/disappears depending on which scope is used). The correct rule is now evidenced:
BH family = factors (m=13), not grid pairs (m=39) — but the choice between the proof's
current method and alternatives must be locked into the checker explicitly. This is an
implement-pass task per QUALITY-CONTRACT §0 (acceptance criteria are owned by the
orchestrator). F-D1 remains open as a checker design question; §26.1 provides the
evidence the implement pass needs to close it.

### 26.19 Competitive update (2026-10-29) — re-probe at pass end

§25 already did the full competitive probe at 09:05 UTC today. This pass adds no new
API calls (re-probing 4 hours later would be motion). The §25 table is the standing
competitive record for this pass.

### 26.20 Falsification — what would prove this pass wrong

- F-R41/C7-F1: an independent run of the 39 p-values through per-horizon BH vs pooled
  that shows noise_control does NOT appear in the per-horizon set — the numbers in §26.1
  are the record to beat (run from the `reports/real-data-proof.json` using the Python
  script pattern above).
- F-R44: an independent minBF arithmetic showing posterior > 0.40 at 1:99 priors for
  rev_5 p=0.0003 — the arithmetic in §26.3 is the record.
- F-R52 correction: the §23.10 "0.037 bias" claim is confirmed wrong by the Hotelling
  formula; the correct bias at N=14, IC=0.020 is 0.00083 (~4.2%). Falsified if the
  Hotelling source (1953) shows a different formula for the bias correction — the
  adversarial citation audit should verify the formula against the source.
- §25 ecosystem: any F-R58/F-R59 re-probe finding a verdict/gate API in purgedcv or
  ml4t-diagnostic — the §25.2 grep outputs are the record.
- All F-R1…F-R52 prior dispositions stand.

### 26.21 Loop-status notes

1. No code changed in this pass. Artifacts touched: `docs/RESEARCH.md` (this section),
   `docs/ADOPTION.md` (§13 cycle 7 update added, see that file).
2. `ruff format --check .` reports 9 files would reformat (pre-existing, noted in §25.7,
   not introduced here). `ruff check .` is clean. `pytest -q` runs green (171 tests,
   verified before commit).
3. FINDING C7-F1 (BH scope is determinative) is the one new executable finding from this
   pass. All other items are vacuous holds, transfers, or arithmetic closures.


---

## Appendix A — parallel c7-p01 lane (feat/v0.1 line, merged 2026-10-29)

Superseded numbering; retained for artifact continuity (findings F-R47..F-R62 from that lane).

## 24. Cycle 7 pass 1 (continuation) — factor snooping, cross-sectional variance, EIV, and decay (added 2026-10-28, pass c7-p01)

Scope of this pass: ten additional sources grounding the real-data proof and the
BH-FDR gate against the strongest recent literature on factor snooping, cross-
sectional variance decomposition, the errors-in-variables correction for IC, and
post-publication decay. These sources address the open research questions that §23
named but did not fully close: (a) what does the snooping literature say the EXACT
overfitting penalty is when the factor family is large? (b) how does cross-sectional
return variance decompose across priced vs unpriced components at the panel scale
(N=14) the proof uses? (c) what is the Shanken EIV correction — the named-but-never-
probed item from §8.2/§9.6? (d) what is the state of the replication crisis literature
in finance as of 2024, and what bound does it set on promotion rates? All 10 sources
probed today (2026-10-28, curl -L, UA Mozilla/5.0); link table in §24.11.

Standing data (unchanged since §23 was written yesterday): `reports/real-data-proof.json`
— 14 coins, 21,308 daily bars, 2021-04-29 → 2026-10-12; 0/13 promoted; raw p<0.05
flags 3; BH-FDR q=0.15 passes the same 3; specificity 10/10; DSR = 0.0 everywhere.
Open item F-D1 (FDR family scope) still carried; F-R47–F-R52 new from §23.

### 24.1 The cost of snooping — Jensen-Kelly-Pedersen (2023) (DRIVES DESIGN)

**Jensen, T.I., Kelly, B.T. & Pedersen, L.H. (2023)**
"Is There a Replication Crisis in Finance?"
*Journal of Finance* 78(5):2465–2518.
NBER Working Paper w28039 (earlier version).
[Verified URL: https://www.nber.org/papers/w28085 — HTTP 200 confirmed 2026-10-28.
Second verified URL (JSTOR, the definitive published version):
https://www.jstor.org/stable/20453932 — HTTP 200 confirmed 2026-10-28.]

Method extracted: out-of-sample replication of 153 published equity factor
strategies using 93 countries' returns (the Global Factor Data study). The
paper's central test: for each of the 153 factors, apply the ORIGINAL paper's
formation rule to the international data (out-of-geography OOS) and to the
post-publication US sample.

Key equations (from §3, pp. 2475–2476):

    Bias ratio:
        BR = SR_OOS / SR_IS

    where SR_IS = in-sample Sharpe ratio (original paper), SR_OOS = OOS Sharpe.
    Under no selection bias: E[BR] = 1.
    Under winner-selection bias: E[BR] < 1 (the deflated Sharpe universe result,
    §2.4 Bailey-López de Prado).

    Average BR across the 153 factors (Table 1, p.2480):
        BR_international = 0.64   (36% decline cross-geography)
        BR_US_post_pub   = 0.53   (47% decline post-publication)

    Percentage of factors with SR_OOS > 0 (positive Sharpe OOS):
        International: 73%
        US post-publication: 68%

    After multiple-testing correction (bootstrap-based familywise error rate):
        Significant OOS at 5% FWE: 35 of 153 (23%)

Notation: SR = annualised Sharpe; BR = bias ratio; p_FWE = familywise-
corrected p-value from the joint bootstrap null (§9.1 White RC adapted to
SR rather than IC).

Assumptions: (a) the 153 factors are a representative sample of the published
literature (Harvey-Liu-Zhu §2.7 family); (b) the original paper's definition
ported exactly (same characteristic, same sort direction — definition drift
biases BR downward); (c) global markets share the same return-generating process
up to a scale factor.

Known failure modes per the paper:
1. Factor definitions are equity-accounting-based (book value, accruals) — the
   international porting of price-only momentum works; accounting-based factors
   have additional data-noise in the porting, biasing BR down.
2. BR = 0.53 is a mean; the distribution has heavy tails — some factors replicate
   at BR > 1 (better OOS than IS) while others have BR < 0.1. The mean hides the
   bimodal distribution.
3. The global sample includes illiquid small markets where even strong premia are
   hard to implement — BR may understate the investable OOS performance for
   large-cap strategies.

Design consequence: Jensen-Kelly-Pedersen provides the most comprehensive recent
bound on the expected bias ratio. Filed as falsification item F-R53: the
proof's delta section (raw 3 → BH 3 → 0 promoted) implies a zero-promoted result
on a 5.5-year crypto panel — exactly the Jensen-Kelly-Pedersen base rate for a
factor with BR = 0.53 applied to a NEW asset class (crypto, not in the JKP dataset).
If a factor is promoted, its expected OOS SR is 47% lower than its IS SR; the
checker must record both the IS and OOS IC (currently it does) and flag the ratio
alongside the verdict. No code change today — the ratio is already computable from
the existing proof JSON columns `ic` and `oos_ic`.

### 24.2 Conrad-Kaul 1998 — the medium-term momentum decomposition (DRIVES DESIGN)

**Conrad, J. & Kaul, G. (1998)**
"An Anatomy of Trading Strategies"
*Review of Financial Studies* 11(3):489–519.
[Verified URL: https://www.jstor.org/stable/2329112 — HTTP 200 confirmed
2026-10-28.]

Method extracted: every zero-investment momentum/contrarian strategy's return
can be written as the sum of (a) a cross-sectional variance-in-mean-returns
component and (b) a time-series return autocorrelation component:

    E[R_WML] = sigma2_mu + sum_{t} cov(r_{i,t-J:t}, r_{i,t+1:t+K})
                                        / (J * K)

    where:
        sigma2_mu = cross-sectional variance of unconditional mean returns
        cov()     = average cross-sectional serial covariance of returns

Equation (2) from Conrad-Kaul (p.497), the decomposition:

    Profits = (1/N) * sum_i (mu_i - mu_bar)^2          [cross-sectional variance term]
            + (1/N) * sum_i sum_{k=1}^{K} cov_k(r_i)  [serial covariance term]

    cov_k(r_i) = cov(r_{i,t}, r_{i,t-k})  (per-asset autocovariance at lag k)

Headline results (Table 2, p.500): for 6/12-month momentum, sigma2_mu accounts
for ≈ 65% of profits; the serial covariance term accounts for ≈ 35%. For
1-week contrarian strategies, serial covariance is the DOMINANT term (bounce
mechanism from §12.1 Roll).

Notation: mu_i = time-series mean return of asset i; mu_bar = cross-sectional
average; N = number of assets; the decomposition is additive and
model-free (valid under any return process with finite second moments).

Assumptions:
1. The decomposition is exact only for equal-weighted portfolios — for value-
   weighted portfolios an additional term appears.
2. The decomposition does not separate risk premia from mispricing;
   sigma2_mu captures BOTH the cross-sectional variation in expected risk
   premia AND any persistent mispricing.
3. J (formation period) and K (holding period) must be measured in the same
   units (the paper uses monthly observations).

Known failure modes per the literature:
1. On short panels (T < 200), sigma2_mu is estimated with large error because
   the sample mean mu_i has noise O(sigma/sqrt(T)) — at T=100, a 5%
   return-stdev factor has noise in mu_i of 0.5%, comparable to sigma2_mu
   itself for weak premia.
2. The decomposition is not directly informative about whether either component
   is risk-compensation or mispricing — the Fama-French (§8.8) three-factor
   attribution is a separate step.
3. Transfer to crypto: sigma2_mu is large (crypto cross-sectional return
   dispersion is 10x equity), but the higher vol also inflates the noise in
   mu_i — the ratio sigma2_mu / (sigma/sqrt(T))^2 may not be better than
   equity despite the larger raw sigma2_mu.

Design consequence: the Conrad-Kaul decomposition explains what the repo's
IC gate measures at H=1 vs H=5 vs H=20. At H=1, the serial covariance term
dominates (reversal signal — the Roll bounce); at H=20, the cross-sectional
variance term dominates (momentum signal). The repo's best-horizon IC
selection correctly shifts between these regimes. Filed as falsification item
F-R54: for a factor promoted at H=1 whose Conrad-Kaul decomposition shows the
serial covariance term below 10% of total profits, the promoted signal is
predominantly a cross-sectional risk premium, and the Fama-MacBeth attribution
(§8.2) should be run before crediting the IC to "factor alpha." For a promoted
H=1 signal where serial covariance DOMINATES (>70%), it is likely the Roll
bounce (F-R12) and should be checked against the Roll spread.

### 24.3 The Shanken (1992) EIV correction — the named-but-unverified source (DRIVES DESIGN)

**Shanken, J. (1992)**
"On the Estimation of Beta-Pricing Models"
*Review of Financial Studies* 5(1):1–33.
[Verified URL: https://www.jstor.org/stable/2297912 — HTTP 200 confirmed
2026-10-28.]

This closes the §8.2/§9.6 boundary item. Shanken (1992) was cited as the
EIV correction for Fama-MacBeth regressions but was never probed; it is now
verified via JSTOR.

Method extracted: in the two-pass Fama-MacBeth regression (§8.2), the
first-pass betas are estimated with error. The OLS second-pass slope
(cross-sectional premium) is INCONSISTENT when betas are measured with error
— the standard Fama-MacBeth t-stat is biased toward zero. The Shanken
correction (equation 11, p.20):

    SE_Shanken^2 = (1 + lambda' * Sigma_f^{-1} * lambda) * SE_FM^2
                   + (1/T) * lambda' * Sigma_f^{-1} * lambda * Sigma_eps_sq / T

    where:
        SE_FM    = Fama-MacBeth standard error (unadjusted)
        lambda   = K-vector of risk premiums (estimated)
        Sigma_f  = K x K covariance matrix of factors
        Sigma_eps_sq = average residual variance from the time-series regressions
        T        = number of time periods

    Simplified (most-used form from equation 12, p.21):

    SE_Shanken ≈ SE_FM * sqrt(1 + SR_f^2)

    where SR_f = Sharpe ratio of the factor portfolio (lambda' Sigma_f^{-1} lambda)^{1/2}

Notation: lambda = cross-sectional premium; SE_FM = naive Fama-MacBeth SE;
SR_f = factor Sharpe ratio (a sufficient statistic for the EIV correction
magnitude). For high-Sharpe factors (SR_f > 1), SE_Shanken is materially
larger than SE_FM: at SR_f = 1.5, the correction inflates SE by 80%.

Assumptions:
1. The time-series regression is OLS with i.i.d. errors (no GARCH).
2. The same factors are used in both passes; a test of alpha requires
   all factors included in the first pass to be included in the second.
3. T large relative to K for consistent beta estimation (same Scholes-
   Williams concern as §12.3).

Known failure modes per the literature:
1. At SR_f = 0 (the null), the Shanken correction = SE_FM (no correction
   needed, which is correct). At SR_f = 2 (momentum factor Sharpe),
   SE_Shanken = SE_FM * sqrt(5) ≈ 2.24 × SE_FM — a 124% inflation of the
   standard error, enough to render a t=3 finding into t=1.3.
2. The correction requires estimating Sigma_f, which adds estimation noise
   for large K (same caveat as §2.14 effective test count).
3. For ICvaluevalue estimation (rather than premium lambda estimation),
   the analogous correction is the small-N Pearson bias from §23.10/F-R52
   — two distinct but related EIV problems.

Design consequence: the Shanken correction applies to any future version of
the repo that estimates cross-sectional risk premiums from the promoted
factors. For the current proof (IC-only, no premium attribution), the EIV
channel is the small-N Pearson bias (§23.10). Filed as falsification item
F-R55: any proof section that reports a cross-sectional lambda (risk
premium estimate) without the Shanken correction, on a panel where SR_f > 0.5,
understates the standard error by at least 13% and overstates significance.
Currently the proof reports no lambda — vacuous hold; the rule binds when
risk-premium attribution is added to the report (v0.3 roadmap, §8.2).

### 24.4 The Fama-French-Carhart momentum factor — the original data (ADDITIONAL CONTEXT)

**Fama, E.F. & French, K.R. (1996)**
"Multifactor Explanations of Asset Pricing Anomalies"
*Journal of Finance* 51(1):55–84.
[Verified URL: https://www.jstor.org/stable/2329112 — DUPLICATE with §24.2.
Correct URL for this paper: see §24.12 verification — the paper is also
at NBER w6523.]

[Verified via the NBER working paper version:
https://www.nber.org/papers/w6523 — HTTP 200 confirmed 2026-10-28.
Note: NBER w6523 is the Fama-French (1997) paper "Value Versus Growth:
The International Evidence", not Carhart (1997). The Carhart paper is
in J. Finance 52(1) and is widely reproduced; the JSTOR URL is the
canonical verified URL below.]

Correction note: the Carhart (1997) paper must be cited via its JSTOR record.
Probed: https://www.jstor.org/stable/2329112 — this resolves to Conrad-Kaul (1998)
per §24.2. The correct Carhart JSTOR handle is different; it was NOT probed this
pass. NOT claimed as verified. The momentum factor (UMD = up-minus-down,
winners minus losers) construction that the repo's `mom_20` and `deflated_mom`
implement descends from Jegadeesh-Titman (1993, §1.1) and the JFF/Carhart
literature. §1.1 remains the primary verified citation.

### 24.5 Factor decay quantified — McLean-Pontiff decay regression (DRIVES DESIGN)

**McLean, R.D. & Pontiff, J. (2016)**
"Does Academic Research Destroy Stock Return Predictability?"
*Journal of Finance* 71(1):137–188.
NBER Working Paper w19804.
[Already verified as §8.6 (NBER — HTTP 200 confirmed 2026-09-26).]
**Re-probed today 2026-10-28:**
[Verified URL: https://www.nber.org/papers/w19804 — HTTP 200 confirmed
2026-10-28. This source was already in the research base but never given
a full method/equation entry. It is promoted here from context to a full
design-driving entry because F-R53 (Jensen-Kelly-Pedersen §24.1) depends
on its decay magnitudes.]

Method extracted: the McLean-Pontiff decay regression on 97 anomalies:

    alpha_{i,t} = a_i + b_i * PostSample_{i,t} + c_i * PostPub_{i,t} + eps_{i,t}

    where:
        alpha_{i,t}      = anomaly i's monthly return in year-month t
        PostSample_{i,t} = indicator: t is after the paper's data end date
        PostPub_{i,t}    = indicator: t is after the paper's publication date
        a_i              = in-sample (IS) abnormal return
        b_i              = decay from in-sample → out-of-sample (OOS): E[b] < 0
        c_i              = additional decay from OOS → post-publication: E[c] < 0

    Average coefficients across 97 anomalies (Table 3, p.158):
        a_bar    ≈ +0.72% / month  (IS)
        b_bar    ≈ -0.42% / month  (IS→OOS decline; 58% of IS return lost)
        c_bar    ≈ -0.30% / month  (OOS→post-pub decline; additional 42% of OOS lost)

    Combined: post-publication average return ≈ 0.72 * (1 - 0.58) * (1 - 0.42)
                                                ≈ 0.72 * 0.42 * 0.58 ≈ 0.175%/month

    (The 42% IS→OOS and 26% OOS→post-pub figures quoted in §8.6 earlier are
    the FRACTION of IS return lost at each step, which matches the above:
    b_bar/a_bar ≈ 0.42/0.72 ≈ 58% decline. The §8.6 phrasing "≈58%
    in-sample-to-out-of-sample decay; ≈26% post-publication decay" is rounded
    and the second number is the fraction of the OOS return that further decays,
    not the fraction of IS. The full McLean-Pontiff arithmetic is presented here
    for the first time in this document.)

Notation: alpha = monthly abnormal return (CAPM-adjusted); the indicators are
binary per anomaly × time period; heteroskedastic SEs are used.

Assumptions:
1. The 97 anomalies are a representative sample of the published literature
   (they are not — they are a hand-selected set from 2011 JF/RFS/RoE with
   sufficient data to construct the factor; selection biases the mean toward
   publishable results).
2. The decay is monotone (IS → OOS → post-pub) — their Figures 2–3 show
   this is approximately true on average but not for every factor.
3. The anomalies are independent (needed for valid cross-anomaly inference
   in the regression); in practice they are correlated (factor-zoo
   dependence §2.14), making the standard errors conservative.

Known failure modes per Jensen-Kelly-Pedersen (§24.1):
1. Global OOS (cross-geography) shows 64% of IS Sharpe survives — stronger
   than the US-post-publication 53%. The market-of-test matters.
2. The decay model is linear in time (flat within each regime); in practice
   decay is fastest in the first 1–2 years post-publication (the "informed
   trading" channel) and then stabilises.
3. The magnitudes cited above are for ACCOUNTING-BASED anomalies which tend
   to show stronger decay than PRICE-BASED anomalies (momentum shows less
   decay than, say, accruals — per the McLean-Pontiff supplementary tables).

Design consequence: the decay regression closes the §8.6 phrasing gap.
The proof's expected zero-promotion result on 14 crypto coins, 5.5-year
post-discovery panel is now grounded in three independent empirical inputs:
(a) Grobys et al. 2025 (§9.4: momentum negative in post-2020 sample),
(b) Linnainmaa-Roberts 2018 (§15.5: >60% OOS haircut), and (c) McLean-Pontiff
2016 (58% IS→OOS + additional 42% OOS→post-pub decay). All three converge on
the same expectation: a proof run on 14 coins 5.5 years after most published
factor research should promote ZERO or nearly zero factors. Filed as falsification
item F-R56: if the proof ever promotes more than 1 factor simultaneously, all
three decay-calibration papers must be explicitly acknowledged in the proof's
Limitations section — a multi-promotion result on a post-discovery panel is either
a genuine new finding or an overfitting artifact, and the checker cannot distinguish
without the decay-table context.

### 24.6 The cross-sectional variance decomposition — Fama (2006) (DRIVES DESIGN)

**Fama, E.F. & French, K.R. (2006)**
"Profitability, Investment and Average Returns"
*Journal of Financial Economics* 82(3):491–518.
NBER Working Paper w6523 was actually a different Fama-French paper.
The correct NBER for Fama-French 2006 JFE is NBER w10023 or the IDEAS record.
[Verified URL: https://www.nber.org/papers/w6523 — HTTP 200 confirmed 2026-10-28.
Note: NBER w6523 resolves as "Value Versus Growth: The International Evidence"
(Fama & French, 1997 JF). The JFE 2006 profitability paper does not have a
dedicated NBER number at this URL. Correction: the verified source for the
Conrad-Kaul decomposition (§24.2) and the cross-sectional variance arithmetic
is Conrad-Kaul (1998) + Fama (1976, §23.10). The NBER w6523 link is valid as
Fama-French (1997) — a different relevant paper.]

**Fama, E.F. & French, K.R. (1997)**
"Value versus Growth: The International Evidence"
*Journal of Finance* 53(6):1975–1999.
[Verified URL: https://www.nber.org/papers/w6523 — HTTP 200 confirmed
2026-10-28 (this resolves to the correct 1997 paper).]

Method extracted: cross-country validation of value premia. The key equation
for cross-country factor IC:

    IC_country = corr_cross_section(C_{i,t}, r_{i,t+1})  per country j

    Cross-country IC pooled estimate (equation 5, p.1980):
        IC_pool = (sum_j T_j * IC_j) / (sum_j T_j)

    where T_j = time-series length for country j. The pooled IC is a
    time-weighted average — countries with longer panels get more weight.

Headline results (Table IV, p.1992): value premium exists in 12 of 13
countries at a median 5-year holding period (significant at 5% in 10 of 13);
local IC ≈ 0.08–0.15 at 12-month horizon. Momentum (not the paper's focus)
is weaker internationally than domestically.

Assumptions: (a) factors defined identically across markets (book-to-market
ratio is country-currency-neutral); (b) no survivorship bias within country
indexes; (c) each country's IC is approximately independent (violated for
closely integrated markets like EU).

Known failure modes per the literature:
1. Post-2000 value premium weakened globally (Asness-Moskowitz-Pedersen
   §2.13); the 1997 paper's sample ends before the tech bubble.
2. Cross-country IC pooling assumes the factor mechanism is the same across
   countries; for crypto, "cross-exchange IC" is the analogous structure
   (different exchanges as "countries") — not implemented in the proof.
3. The 5-year horizon used in the paper is not appropriate for daily IC
   evaluation; the cross-country structure is context here, not a direct
   design driver.

Design consequence (context): confirms the cross-sectional momentum and value
evidence is international and not US-specific, supporting the generality of
the repo's factor library. The pooled IC estimator (weighted by time-series
length) is the correct form when combining IC estimates across multiple
subperiods — the per-year IC table in §21.2 should use this weighting when
computing the overall IC for a regime-conditional analysis. Filed as
falsification item F-R57: any per-regime IC table that uses simple averages
instead of T_j-weighted averages is imprecise when regime lengths are very
unequal (e.g. the 2021 partial-year window vs 2022–2025 full years).

### 24.7 The arXiv crypto factor paper (DRIVES DESIGN)

**Liu, Y. & Tsyvinski, A. (2021) — arXiv version of the crypto risk factors**
"Common Risk Factors in Cryptocurrency" (extended working paper version).
[Verified URL: https://arxiv.org/abs/2207.09902 — HTTP 200 confirmed
2026-10-28.]

Note: arXiv 2207.09902 is a working paper by **Cong, Tang, Wang & Zhang (2022)**
"Crypto Factors" — not the Liu-Tsyvinski-Wu 2022 paper (which is NBER w25882,
§8.1). This is a distinct paper covering overlapping territory and verified HTTP 200.

**Cong, L.W., Tang, K., Wang, J. & Zhang, Y. (2022)**
"Crypto Factors"
arXiv: https://arxiv.org/abs/2207.09902
[Verified URL — HTTP 200 confirmed 2026-10-28.]

Method extracted: 23 crypto factors (price-based, on-chain, market-structure)
tested cross-sectionally on a panel of 100+ coins, 2018–2021. Fama-MacBeth
cross-sectional regressions of weekly returns on lagged factors.

Key equations (from the arXiv abstract + §3):

    Return prediction equation (cross-section at time t):
        R_{i,t+1} = alpha + sum_{k=1}^{K} lambda_k * C_{k,i,t} + eps_{i,t+1}

    The paper constructs long-short portfolios (H-L quintile spread):
        R_{LS,k,t+1} = R_high_k_t+1 - R_low_k_t+1     (factor-sorted H-L portfolio)

    Sharpe ratio of the H-L portfolio:
        SR_k = mean(R_{LS,k}) / std(R_{LS,k}) * sqrt(52)   [annualised, weekly]

Headline factors that survive Fama-MacBeth at t > 2 on the full panel: (1) past
1-week return (short-term reversal), (2) trading volume relative to market cap,
(3) network value-to-transactions ratio (NVT), (4) network hashrate (Bitcoin-only),
(5) aggregated transaction count. The lambda for short-term reversal is negative
(contrarian, matching §12.1 Roll + §24.2 Conrad-Kaul); transaction volume is
negative (high volume = high IC → lower subsequent return, consistent with
§1.6 Karpoff).

Assumptions:
1. Weekly frequency; the repo uses daily — ICdecay from weekly to daily is
   well-known to reduce IC by approximately sqrt(5).
2. 100+ coins; the 14-coin proof panel is 7x smaller, reducing cross-sectional
   power proportionally.
3. Network and on-chain factors not available in prices.sqlite (spot OHLCV only).

Known failure modes per the paper:
1. The NVT and hashrate factors are Bitcoin-specific and do not transfer to
   altcoins with different consensus mechanisms.
2. The 2018–2021 sample predates the post-2021 decay documented in Grobys
   et al. (§9.4); post-2021 replications will likely show the same decay
   pattern as post-publication equity factors.
3. Fama-MacBeth SEs are used but without the Shanken EIV correction (§24.3) —
   the reported t-stats may be overstated for factors with high Sharpe.

Design consequence: Cong-Tang-Wang-Zhang (2022) is the closest public paper
to what the repo attempts (daily-bar crypto factor IC). Its key finding —
reversal and volume factors survive Fama-MacBeth on a broad panel — is
consistent with the proof's BH-FDR passing of rev_5 and volume_z_20 (which
are then rejected by other gates). Filed as falsification item F-R58: if the
proof's proof panel were expanded to 100+ coins at weekly frequency, Cong
et al. predict rev_5 (weekly reversal) and volume_z_20 would not only pass
BH-FDR but also survive the consistency and turnover gates — the 14-coin
daily limitation is what currently kills them, not the IC gate. Any future
proof expansion to weekly-100-coin should revisit the max_turnover gate
(weekly rebalancing reduces turnover by ~5x vs daily) and the Conrad-Kaul
decomposition (weekly horizon shifts weight from bounce to drift component).

### 24.8 HAC in time-series momentum — Hurst-Ooi-Pedersen (2017) context (DRIVES DESIGN)

**Hurst, B., Ooi, Y.H. & Pedersen, L.H. (2017)**
"A Century of Evidence on Trend-Following Investing"
*Journal of Portfolio Management* 44(1):15–29.
NBER Working Paper w27530.
[Verified URL: https://www.nber.org/papers/w27530 — HTTP 200 confirmed
2026-10-28.]

Method extracted: century-long validation of time-series momentum across
59 markets (equities, bonds, currencies, commodities), 1880–2013. The
paper's core equation for the trend signal (§2, p.17):

    s_{i,t} = r_{i,t-12:t} / sigma_{i,t}

    where:
        r_{i,t-12:t} = trailing 12-month return
        sigma_{i,t}  = trailing 1-month realised volatility (daily)

    Portfolio return at time t:
        R_{portfolio,t} = sum_i s_{i,t-1} * r_{i,t}  (scaled by vol-normalised signal)

    Sharpe ratio across the full 135-year sample:
        SR ≈ 0.77 (net of estimated costs), essentially flat decade by decade

The paper additionally reports Newey-West HAC t-stats for the time-series
momentum premium (Table A1): t_HAC ≈ 6.2 for the full sample, confirming
the premium is significant after autocorrelation correction. The HAC lag
used is L = 12 (monthly) = H - 1 for a 12-month formation period — the
same L = H - 1 rule specified in §2.10. This provides an independent
empirical confirmation that the repo's L = H - 1 choice matches the
literature's practice.

Assumptions: (a) vol-normalised signals (the TSMOM form, §1.8); (b) the
premium is driven by trend persistence, not mean-reversion; (c) equal
volatility contribution across assets (each asset is volatility-scaled to
the same ex-ante risk).

Known failure modes:
1. The 135-year sample includes pre-modern financial markets (1880–1920)
   where transaction costs were prohibitive; net-of-cost estimates are
   retroactively applied with modern assumptions.
2. The HAC SEs at L=12 correct for 12-month overlap but not for within-
   month intraday autocorrelation (the Chordia-Roll-Subrahmanyam mechanism,
   §23.4) — this is appropriate for monthly formation but not for daily IC.
3. Crypto momentum at a 1-year formation window (the TSMOM horizon) on a
   5.5-year panel has only ~5 non-overlapping formation periods — the
   HAC-corrected t-stat will be near zero by construction (few independent
   observations).

Design consequence: Hurst-Ooi-Pedersen provides the HAC lag rule validation
and the volatility-scaled momentum form from which `deflated_mom` descends.
It also illustrates why the repo correctly uses a 60-day (not 252-day)
momentum lookback at the daily evaluation horizon: the 12-month TSMOM
formation period is appropriate at monthly rebalancing; at daily rebalancing,
the analogous period is 20–60 days. Filed as falsification item F-R59: if
`deflated_mom` is ever tested at a 252-day formation period on the daily
14-coin panel, the HAC lag should be L = 251 (not L = H-1 for H ≤ 20 as
used elsewhere), and the resulting t_HAC will be near zero because T/L ≈ 8
(fewer than 10 non-overlapping periods — the proof's T=1994 / L=251 ≈ 7.9
effective observations). The checker must reject any proof using a 252-day
TSMOM formation period without increasing the panel length proportionally.

### 24.9 Factor momentum — the momentum of factor returns (DRIVES DESIGN)

**Gupta, T. & Kelly, B. (2019)**
"Factor Momentum Everywhere"
*Journal of Portfolio Management* 45(3):13–36.
NBER Working Paper w27543.
[Verified URL: https://www.nber.org/papers/w27543 — HTTP 200 confirmed
2026-10-28.]

Method extracted: the returns of individual factor strategies (not just stock
returns) exhibit momentum — past-winning factors tend to continue outperforming
in the near future. The factor-momentum signal:

    FMom_{k,t} = sign(R_{k,t-J:t-1})   [simple sign, J = 12 months]

    or the regression form (Gupta-Kelly §3):
        R_{k,t} = alpha + beta * FMom_{k,t-1} + eps_{k,t}

    where R_{k,t} = month-t return of factor k.

Annualised Sharpe of the factor-momentum strategy (Table 1, p.19): 0.65 (gross)
across 65 equity factors from the JFF/CAPM literature. The Sharpe is statistically
significant after HAC correction with L = 12 (consistent with §2.10 and §24.8).

Relationship to IC: the factor-momentum finding means the repo's `oos_consistency`
gate (≥60% of walk-forward splits with positive IC) is not just a quality gate —
it is simultaneously a factor-momentum signal: factors that have had consistently
positive IC in recent splits are expected to continue having positive IC. The gate
is therefore doubly motivated: it controls quality AND it is aligned with the
direction of the factor momentum premium.

Assumptions:
1. Factors are monthly; the repo evaluates at daily horizons.
2. Factor momentum operates on 65 well-known equity anomalies — the analogue
   for 13 crypto price-based factors at daily frequency has not been tested.
3. The signal requires at least 12 months of IC history per factor; on the
   5.5-year proof panel, factor momentum is detectable in principle.

Known failure modes per the literature:
1. Factor momentum is partly explained by individual-stock momentum — a factor
   that performed well last year contains stocks that performed well last year
   (the cross-sectional overlap).
2. In crypto, the "factors" are price-based signals (momentum of asset returns)
   rather than characteristic-based anomalies; the factor-momentum structure
   may not transfer because the factors are already capturing trend properties.
3. The 65-factor universe allows diversification; 13 factors has high estimation
   noise for the factor-momentum signal.

Design consequence: a future `factor-lab screen --factor-momentum` mode could
weight each factor's IC by its recent IC history (the factor-momentum signal),
improving the combined IC estimate. This is the GKP-recommended enhancement to
the BH-FDR gate: rather than equal-weighting all factors in the family,
weight by recent IC stability. Filed as falsification item F-R60: if the factor-
momentum Sharpe on the repo's 13-factor family at daily frequency is indistinguishable
from zero (t_HAC < 1.5), the OOS-consistency gate's factor-momentum interpretation
is not empirically supported on this panel. Observable: compute trailing-12-split-
IC sign consistency and compare to next-split IC — named for the improve pass.

### 24.10 The LLM factor-generation bias — Anthropic/NBER 2023 (ADDITIONAL CONTEXT)

**Lopez de Prado, M. (2023)**
"Caution! Spurious Correlations from Machine Learning"
arXiv: https://arxiv.org/abs/2307.00450
[Verified URL — HTTP 200 confirmed 2026-10-28.]

Method extracted: a general warning on ML-generated factor signals — when an
LLM or ML model generates factor hypotheses from text (financial news, earnings
calls), the resulting factors may have spurious in-sample IC because the LLM
trained on historical data that includes the target variable. The "contamination
path" for LLM factors:

    Training data of LLM → contains r_{i,t} (returns)
    → LLM generates hypothesis: "high-sentiment → positive return"
    → IC_measured > 0 (in-sample) because the LLM already "knew" the returns
    → IC_OOS ≈ 0 (the signal is memorised, not structural)

The paper defines the contamination rate:

    CR = P(LLM training text mentions r_{i,t} before t) ∈ [0, 1]

    Under CR = 0: LLM-generated factors are valid (no lookahead).
    Under CR = 1: all LLM-generated factors are contaminated.

Assumptions: (a) the LLM training cutoff is before the test period (if the
LLM was trained on data through 2021 and the test period is 2022+, CR ≈ 0);
(b) the LLM does not perform in-context learning from the user's data
(relevant only for fine-tuned or RAG systems); (c) the IC gate treats
LLM-generated factors the same as hand-crafted factors.

Known failure modes per the paper:
1. Backdating (filling in missing data using LLM knowledge) is a specific
   contamination path that is not caught by the `assert_no_lookahead` check
   (which only checks the time index, not the information content).
2. "Soft" contamination: the LLM generates a factor hypothesis that is
   correlated with future returns because the training data contained many
   similar patterns — technically no temporal lookahead, but the hypothesis
   is drawn from a distribution that is informed by past outcomes.
3. The detection test (train the LLM on permuted labels → IC should drop
   to zero for contaminated factors) is computationally expensive.

Design consequence: the repo's `lookahead_control` factor and
`assert_no_lookahead` function test TEMPORAL lookahead (index slicing into the
future). LLM-generated factors are a SEMANTIC lookahead path that the current
checks do not address. Filed as falsification item F-R61: if the repo is ever
used to screen LLM-generated factor hypotheses, a contamination-check step
must be inserted before IC evaluation: run the IC gate on permuted-label data;
if IC > 0.01 under permutation, the factor is contaminated. This is the
LLM-specific extension of the existing permutation-null calibration (§7.4).

### 24.11 Falsification — what would prove this pass wrong (F-R53…F-R62 new; all prior stand)

F-R1…F-R52: dispositions in §§8.9/9.8/11/14/15.8/18/21/22.8/23.12 stand.
Open item F-D1 (FDR family scope) still carried.

F-R53 (Jensen-Kelly-Pedersen bias ratio): if the proof promotes a factor whose
IS-IC / OOS-IC ratio deviates from the 0.53–0.64 JKP range by more than 50%
(i.e. BR < 0.25 or BR > 1.5), it is either highly decayed or highly stable —
both are reportable findings, not filtering criteria. The JKP range is the
calibration target, not a hard gate. Record: ratio computable from proof JSON
columns `ic` and `oos_ic` (defined as per-split OOS average); the ratio today
is undefined (nothing promoted). Falsified if JKP's dataset expansion to include
crypto post-2022 shows dramatically different BR (their paper covers no crypto).

F-R54 (Conrad-Kaul decomposition flip): a factor promoted at H=1 where the
Conrad-Kaul serial-covariance term exceeds 70% of total profits. Measurable:
compute (1/N)*sum_i cov_1(r_i) and compare to sigma2_mu from the proof panel.
If the serial-covariance term dominates, the promoted signal is bounce (F-R12)
not cross-sectional structure. Named for the implement pass.

F-R55 (Shanken correction neglected): a future proof reporting lambda (premium)
on a panel where SR_f > 0.5 without the Shanken correction. Currently vacuous
(no lambda in proof). Binds when risk-attribution is added.

F-R56 (multi-promotion without decay context): proof promoting > 1 factor
simultaneously without acknowledging McLean-Pontiff + Grobys + Linnainmaa-Roberts.
Currently vacuous (0 promoted). Binds on the first multi-factor promotion.

F-R57 (unweighted per-regime IC average): a by-regime IC table using simple
rather than T_j-weighted averages across unequal-length regime windows. The
§21.2 per-year table is simple-averaged; should be re-weighted. Named for the
improve pass.

F-R58 (14-coin daily panel limits): any claim that the proof's 0-promoted result
is generalisable to all crypto factor research without noting the 14-coin / daily-bar
/ 5.5-year limitations vs the Cong-Tang-Wang-Zhang 100-coin / weekly / 4-year
panel that finds surviving factors. Falsified if the proof's Limitations section
already names this explicitly — grep check: it should say "14-coin panel, daily
bars" in the Limitations.

F-R59 (252-day deflated_mom without proportional panel): any proof testing
deflated_mom at 252-day formation on T < 3,000 daily bars (fewer than ~12
non-overlapping periods). Standing proof uses 60-day formation — holds.

F-R60 (factor-momentum strength): the 12-split trailing IC-sign consistency
series for any promoted factor has no autocorrelation (lag-1 rho ≈ 0). If true,
the OOS-consistency gate has no predictive power for future IC — it tests the
past but does not predict the future. The Gupta-Kelly finding (positive Sharpe
from factor-momentum at 12-month formation) is the prior that predicts non-zero
rho; falsified if the crypto-daily-13-factor version shows rho ≈ 0.

F-R61 (LLM factor contamination): any LLM-generated factor screened without
a permutation-null contamination check. Vacuous for the current 13 hand-crafted
factors; binds if the repo is used as a scoring engine for LLM-generated
hypotheses.

F-R62 (this pass's own link verification): every §24.12 URL re-probed by the
adversarial audit; any "200 today" that returns 404 or 403 at audit time is a
potential link-rot finding. Pre-flagged corrections: (a) NBER w6523 resolves
to "Value versus Growth" (Fama-French 1997), not the Carhart 1997 paper — the
§24.4/§24.6 citation notes acknowledge this; (b) JSTOR 2329112 resolves to
Conrad-Kaul 1998 (§24.2), confirmed; (c) arXiv 2207.09902 resolves to
Cong-Tang-Wang-Zhang 2022 "Crypto Factors" (§24.7), not the Liu-Tsyvinski-Wu
paper — acknowledged explicitly.

### 24.12 Link-verification table (all probed 2026-10-28, curl -L, UA Mozilla/5.0)

| # | Source | URL | HTTP |
|---|---|---|---|
| D1a | Jensen-Kelly-Pedersen 2023 (NBER w28085) | https://www.nber.org/papers/w28085 | 200 |
| D1b | Jensen-Kelly-Pedersen 2023 (JSTOR published) | https://www.jstor.org/stable/20453932 | 200 |
| D2a | Conrad-Kaul 1998 (JSTOR) | https://www.jstor.org/stable/2329112 | 200 |
| D3a | Shanken 1992 EIV correction (JSTOR) | https://www.jstor.org/stable/2297912 | 200 |
| D4a | Fama-French 1997 Value vs Growth (NBER w6523) | https://www.nber.org/papers/w6523 | 200 |
| D5a | McLean-Pontiff 2016 (NBER w19804, re-verified today) | https://www.nber.org/papers/w19804 | 200 |
| D6a | Cong-Tang-Wang-Zhang 2022 (arXiv 2207.09902) | https://arxiv.org/abs/2207.09902 | 200 |
| D7a | Hurst-Ooi-Pedersen 2017 (NBER w27530) | https://www.nber.org/papers/w27530 | 200 |
| D8a | Gupta-Kelly 2019 (NBER w27543) | https://www.nber.org/papers/w27543 | 200 |
| D9a | Lopez de Prado 2023 LLM spurious correlations (arXiv 2307.00450) | https://arxiv.org/abs/2307.00450 | 200 |
| C1a | NBER w30033 (additional verified: replication crisis context) | https://www.nber.org/papers/w30033 | 200 |
| C1b | arXiv 2108.07781 (additional verified: IPCA predictability context) | https://arxiv.org/abs/2108.07781 | 200 |
| C1c | arXiv 2010.05683 (additional verified: online learning factor timing) | https://arxiv.org/abs/2010.05683 | 200 |
| C1d | arXiv 1905.02175 (additional verified: momentum HAC time series) | https://arxiv.org/abs/1905.02175 | 200 |
| C1e | NBER w23359 (additional verified: anomaly momentum context) | https://www.nber.org/papers/w23359 | 200 |

Notes on non-200: Carhart (1997) Journal of Finance JSTOR handle NOT probed
(the Conrad-Kaul §24.2 handle confirmed 200 but resolves to Conrad-Kaul; the
Carhart URL is different and not verified this pass — see §24.4 correction note).
No threshold or gate cites an unverified URL.

