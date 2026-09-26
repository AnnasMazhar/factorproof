"""
factorlab.significance — honest statistical significance testing.

All implementations are from first principles (no scipy, no statsmodels).

References:
- Benjamini & Hochberg (1995) J. Royal Statistical Society B 57(1):289-300.
  FDR control procedure. Equations transcribed verbatim below.
- Wilson (1927) J. American Statistical Association 22(158):209-212.
  Score interval for binomial proportion.
- Bailey & López de Prado (2014) J. Portfolio Management 40(5):94-107.
  Deflated Sharpe Ratio (DSR). Formulation implemented from first principles.
- Storey (2002) J. Royal Statistical Society B 64(3):479-498.
  Discussion of FDR vs FWER in high-dimensional testing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Benjamini-Hochberg FDR
# ---------------------------------------------------------------------------


def benjamini_hochberg(
    p_values: list[float],
    q: float = 0.10,
) -> list[bool]:
    """Apply Benjamini-Hochberg FDR correction.

    Reference: Benjamini & Hochberg (1995) JRSS-B 57(1):289-300.

    Procedure (Algorithm 1 from the paper):
        1. Order the m p-values p_(1) <= p_(2) <= ... <= p_(m).
        2. Find k = max{i : p_(i) <= (i/m) * q}.
        3. Reject all H_(1), ..., H_(k).

    The procedure controls FDR at level q under positive dependence (PRDS).

    Parameters
    ----------
    p_values:
        List of m p-values.
    q:
        FDR level (default 0.10).

    Returns
    -------
    List of bool: True if the null is rejected (discovery).
    """
    m = len(p_values)
    if m == 0:
        return []

    # Step 1: sort by p-value, track original indices
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    rejected_set: set[int] = set()

    # Step 2: find largest k such that p_(k) <= (k/m)*q
    k_star = -1
    for rank_zero, (orig_idx, pval) in enumerate(indexed):
        rank_one = rank_zero + 1  # 1-based rank
        threshold = (rank_one / m) * q
        if pval <= threshold:
            k_star = rank_zero

    # Step 3: reject all hypotheses up to k_star
    if k_star >= 0:
        for rank_zero in range(k_star + 1):
            orig_idx = indexed[rank_zero][0]
            rejected_set.add(orig_idx)

    return [i in rejected_set for i in range(m)]


def bonferroni(
    p_values: list[float],
    alpha: float = 0.05,
) -> list[bool]:
    """Apply Bonferroni FWER correction.

    Rejects H_i if p_i <= alpha/m where m = len(p_values).
    Conservative; controls the family-wise error rate.

    Reference: Bonferroni (1936) "Teoria statistica delle classi e calcolo
    delle probabilita", Pubblicazioni del R Istituto Superiore di Scienze
    Economiche e Commerciali di Firenze 8:3-62.
    """
    m = len(p_values)
    if m == 0:
        return []
    threshold = alpha / m
    return [p <= threshold for p in p_values]


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio
# ---------------------------------------------------------------------------


def deflated_sharpe_ratio(
    observed_sr: float,
    n_trials: int,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Compute the Deflated Sharpe Ratio (DSR) of Bailey & Lopez de Prado (2014).

    The DSR adjusts an observed Sharpe Ratio downward to account for:
      1. Selection bias from multiple trials.
      2. Non-normality of returns (via skewness and excess kurtosis).

    Reference: Bailey & López de Prado (2014) J. Portfolio Management 40(5):94-107.
    Equation (11) in the paper:

        SR* = E[max SR | n_trials, T] estimated via the expected maximum of
              n_trials draws from the distribution of SR estimators.

        Expected maximum of N IID standard normals:
            E[max] ~ (1 - gamma(1 - 1/N)) / sqrt(log N) ... for large N
        Bailey & Lopez de Prado use the approximation:
            SR* = (1 - euler_gamma) * Z(1 - 1/n) + euler_gamma * Z(1 - 1/(n*e))
        where Z = inverse normal CDF, euler_gamma = 0.5772156649.

        Then the Sharpe ratio is deflated:
            DSR = Phi( (SR - SR*) * sqrt(T-1) /
                       sqrt(1 - skew*SR + (kurt-1)/4 * SR^2) )
        where Phi = standard normal CDF (implemented from first principles).

    Assumptions:
        - Returns are approximately stationary.
        - Trials are IID draws from the same SR distribution.
        - n_trials is the number of distinct strategies/parameterisations tested.

    Known failure modes:
        - If trials are highly correlated, DSR over-corrects.
        - For very small n_obs (< 30), the chi-squared approximation is poor.

    Parameters
    ----------
    observed_sr:
        The Sharpe Ratio of the selected strategy.
    n_trials:
        Number of strategies/trials tested (selection bias correction).
    n_obs:
        Number of independent observations.
    skew:
        Sample skewness of returns (default 0.0 = Gaussian).
    kurtosis:
        Sample kurtosis (default 3.0 = Gaussian; excess = kurtosis - 3).

    Returns
    -------
    Probability that observed_sr > SR* (DSR p-value).
    """
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    if n_obs < 2:  # noqa: PLR2004
        raise ValueError("n_obs must be >= 2")

    # Expected maximum SR from n_trials trials
    # Bailey & Lopez de Prado (2014) eq. 5-6, using:
    #   Euler-Mascheroni constant gamma_EM ~ 0.5772156649
    #   Approximation via two quantiles of the standard normal
    gamma_em = 0.5772156649
    if n_trials == 1:
        sr_star = 0.0
    else:
        # Z(1 - 1/n) and Z(1 - 1/(n*e)) where e = Euler's number
        z1 = _norm_ppf(1.0 - 1.0 / n_trials)
        z2 = _norm_ppf(1.0 - 1.0 / (n_trials * math.e))
        sr_star = (1.0 - gamma_em) * z1 + gamma_em * z2

    # Variance adjustment for non-normality (excess kurtosis = kurtosis - 3)
    excess_kurt = kurtosis - 3.0
    denom_sq = 1.0 - skew * observed_sr + (excess_kurt / 4.0) * observed_sr**2
    if denom_sq <= 0:
        denom_sq = 1e-9  # degenerate case; clamp

    # Standardised statistic
    z = (observed_sr - sr_star) * math.sqrt(n_obs - 1) / math.sqrt(denom_sq)
    return _norm_cdf(z)


# ---------------------------------------------------------------------------
# Bootstrap confidence interval
# ---------------------------------------------------------------------------


def bootstrap_ci(
    values: list[float],
    n_boot: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval.

    Reference: Efron & Tibshirani (1993) "An Introduction to the Bootstrap"
    ISBN 0412042312. Section 13.3 (percentile method).

    Parameters
    ----------
    values:
        Sample values.
    n_boot:
        Number of bootstrap replications.
    seed:
        RNG seed for determinism.
    alpha:
        Significance level (default 0.05 → 95% CI).

    Returns
    -------
    (lower, upper) confidence interval.
    """
    import numpy as np

    arr = np.array([v for v in values if not math.isnan(v)], dtype=float)
    if len(arr) == 0:
        return (float("nan"), float("nan"))

    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(arr, size=len(arr), replace=True)
        boot_means[i] = sample.mean()

    lower = float(np.percentile(boot_means, 100 * alpha / 2))
    upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return (lower, upper)


# ---------------------------------------------------------------------------
# Sample size helper
# ---------------------------------------------------------------------------


def min_sample_size(
    effect: float,
    power: float = 0.8,
    alpha: float = 0.05,
) -> int:
    """Minimum sample size for a one-sided z-test.

    n = ((z_alpha + z_beta) / effect)^2
    where:
        z_alpha = _norm_ppf(1 - alpha)
        z_beta  = _norm_ppf(power)

    This is the standard result for testing H0: mu=0 vs H1: mu=effect
    with known sigma=1 (standardised effect = Cohen's d for unit-sigma).

    Reference: Cohen (1988) "Statistical Power Analysis for the Behavioral
    Sciences", 2nd ed. ISBN 0805802835. Chapter 7.

    Parameters
    ----------
    effect:
        Standardised effect size (signal / noise).
    power:
        Desired statistical power (default 0.8).
    alpha:
        Type-I error rate (default 0.05).
    """
    if effect <= 0:
        raise ValueError("effect must be > 0")
    z_alpha = _norm_ppf(1.0 - alpha)
    z_beta = _norm_ppf(power)
    n = ((z_alpha + z_beta) / effect) ** 2
    return math.ceil(n)


# ---------------------------------------------------------------------------
# Wilson lower bound (also exposed from evaluate.py; re-exported here)
# ---------------------------------------------------------------------------


def wilson_lower(k: int, n: int, z: float = 1.96) -> float:
    """Wilson score lower bound for a binomial proportion.

    Reference: Wilson (1927) JASA 22(158):209-212. Equation (1):

        lb = (p_hat + z^2/(2n) - z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) /
             (1 + z^2/n)

    where p_hat = k/n, z = 1.96 for 95% CI.

    Parameters
    ----------
    k:
        Number of successes.
    n:
        Total trials.
    z:
        z-score for confidence level (1.96 = 95%).
    """
    if n <= 0:
        return 0.0
    p_hat = k / n
    z2 = z * z
    term = math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    lb = (p_hat + z2 / (2 * n) - z * term) / (1 + z2 / n)
    return float(max(0.0, min(1.0, lb)))


# ---------------------------------------------------------------------------
# Multiple testing summary
# ---------------------------------------------------------------------------


@dataclass
class MultipleTestingResult:
    """Summary of multiple-testing correction for a set of factors."""

    p_values: list[float]
    bh_rejected: list[bool]  # Benjamini-Hochberg
    bonferroni_rejected: list[bool]
    n_bh_discoveries: int
    n_bonferroni_discoveries: int
    q_level: float
    alpha_level: float


def correct_multiple_tests(
    p_values: list[float],
    q: float = 0.10,
    alpha: float = 0.05,
) -> MultipleTestingResult:
    """Apply both BH FDR and Bonferroni corrections to a set of p-values.

    Parameters
    ----------
    p_values:
        One p-value per factor (from IC t-test).
    q:
        FDR level for Benjamini-Hochberg.
    alpha:
        FWER level for Bonferroni.
    """
    bh = benjamini_hochberg(p_values, q)
    bf = bonferroni(p_values, alpha)
    return MultipleTestingResult(
        p_values=p_values,
        bh_rejected=bh,
        bonferroni_rejected=bf,
        n_bh_discoveries=sum(bh),
        n_bonferroni_discoveries=sum(bf),
        q_level=q,
        alpha_level=alpha,
    )


# ---------------------------------------------------------------------------
# Private: normal CDF and quantile function (no scipy)
# ---------------------------------------------------------------------------

# Abramowitz & Stegun (1964) "Handbook of Mathematical Functions"
# Section 26.2.17 — rational approximation to the normal CDF.
# Maximum absolute error: 7.5e-8.


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via Abramowitz & Stegun (1964) 26.2.17.

    Abramowitz & Stegun (1964) "Handbook of Mathematical Functions",
    National Bureau of Standards. Formula 26.2.17, p.932.
    """
    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)

    # Rational polynomial approximation
    t = 1.0 / (1.0 + 0.2316419 * x)
    b1 = 0.319381530
    b2 = -0.356563782
    b3 = 1.781477937
    b4 = -1.821255978
    b5 = 1.330274429
    poly = (((b5 * t + b4) * t + b3) * t + b2) * t + b1
    cdf_x = 1.0 - _norm_pdf(x) * poly * t

    if sign >= 0:
        return cdf_x
    return 1.0 - cdf_x


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_ppf(p: float) -> float:
    """Inverse normal CDF via rational approximation.

    Beasley & Springer (1977) algorithm, as described in:
    Abramowitz & Stegun (1964) "Handbook of Mathematical Functions" 26.2.22.
    Maximum absolute error ~ 4.5e-4 for p in [0.001, 0.999].
    """
    if p <= 0 or p >= 1:
        raise ValueError(f"p must be in (0, 1), got {p}")

    # Symmetry: work with p <= 0.5
    if p > 0.5:
        return -_norm_ppf(1.0 - p)

    # Rational approximation valid for 0 < p <= 0.5
    # From Abramowitz & Stegun 26.2.22
    t = math.sqrt(-2.0 * math.log(p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    numerator = c0 + c1 * t + c2 * t * t
    denominator = 1.0 + d1 * t + d2 * t * t + d3 * t * t * t
    return -(t - numerator / denominator)
