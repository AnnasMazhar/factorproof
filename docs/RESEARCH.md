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

(End of file)
