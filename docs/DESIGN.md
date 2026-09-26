# docs/DESIGN.md — factor-lab v0.1

## Purge/Embargo Timeline

The leakage-safe CV split separates training and test windows with a purge zone
that prevents the forward-return label from contaminating the test window.

```
  |--- training data ---|  purge  | embargo |--- test data ---|
  t_0             t_purge_cutoff            t_test_start   t_test_end
```

- **Purge zone**: training rows whose label window `[t, t+h]` overlaps `t_test_start`
  are removed. The cutoff is `t_purge_cutoff = t_test_start - label_horizon`.
- **Embargo zone**: an additional `embargo_days` rows are dropped before the test
  window to prevent correlated noise from leaking through residual autocorrelation.
- **Result**: the training set ends strictly before `t_test_start - embargo_days`.

This is implemented in `src/factorlab/cv.py:PurgedWalkForward`.
Reference: Lopez de Prado (2018) "Advances in Financial Machine Learning" ch. 7.

---

## Statistics Choices

### Why Wilson lower bound, not raw hit rate?

Raw hit rate `p_hat = k/n` is an unbiased estimator but has high variance for
small n. If a factor has 60% hit rate on 20 observations, the 95% CI is
approximately [0.37, 0.79] — the true rate could easily be below 50%.

The Wilson lower bound at 95% confidence gives a *provably conservative* floor.
By requiring lb >= 0.50, we demand that even under the pessimistic end of the
confidence interval the factor beats chance. With n=1500 observations, a 50.1%
hit rate gives Wilson LB = 0.4979 (fails); 50.9% gives LB = 0.4869 (fails).
You need statistically meaningful evidence of directional edge.

### Why BH FDR, not Bonferroni?

With 13 factors, Bonferroni requires p < 0.05/13 = 0.38%. This would reject
most real factors in small samples. Bonferroni controls the family-wise error
rate (probability of *any* false discovery), which is the wrong question when
one or two false positives in 13 are acceptable.

BH FDR controls the *expected fraction* of false discoveries. At q=0.10, if 3
factors are promoted, we expect at most 0.3 of them to be noise. This is the
appropriate error rate for an exploratory pipeline that downstream backtesting
will further filter.

Both BH and Bonferroni are computed; BH is the gate, Bonferroni is reported
for comparison.

### Why purged walk-forward, not standard K-fold?

Standard K-fold assigns test folds randomly. With time-series data, a random
fold assignment puts future observations in the training set and past observations
in the test set, constituting lookahead. This inflates apparent IC and hit rate.

Purged walk-forward preserves temporal ordering: the test set always follows
the training set. The purge step prevents the training labels from reaching
into the test period. The embargo step accounts for residual autocorrelation.

### Why IC-IR as the primary selection criterion?

IC-IR = mean(IC) / std(IC) is the Sharpe Ratio of the information signal.
A factor with high mean IC but high IC variance is less reliable than one with
consistent moderate IC. IC-IR penalises inconsistency, matching practitioner
preference for factors that work reliably, not factors that spike once.

### Why reject lookahead at the structural level?

The `LookaheadControl` factor uses `close.shift(-1)` — the next period's close.
This achieves near-perfect prediction by construction (IC > 0.4). Rather than
detecting this through statistical gates (which it would pass), we reject it
at the structural level: the `uses_future_data=True` flag is checked before
any computation begins.

This illustrates the key principle: statistical gates cannot detect all forms
of contamination. Structural guards are necessary.

---

## Gate Sequence and Rationale

The promotion gate (`src/factorlab/promote.py:promote`) applies gates in order.
Early failures short-circuit remaining computation.

| Gate | Default | Rationale |
|------|---------|-----------|
| not_lookahead | structural | Future data has no predictive value — it *is* the target |
| not_degenerate | constant check | Constant factor = undefined IC, no information |
| coverage | >= 50% non-NaN | Sparse factor inflates IC by selecting only liquid days |
| min_observations | 30 periods | Below 30 cross-sections, IC is noise-dominated |
| min_abs_ic | >= 0.02 | IC < 0.02 is economically negligible; see Grinold & Kahn |
| min_ic_ir | >= 0.05 | IC-IR < 0.05 = unreliable signal (high IC variance) |
| hit_rate_wilson_lb | >= 0.50 | Directional signal must beat chance at 95% confidence |
| max_turnover | <= 0.50 | High turnover destroys edge through transaction costs |
| oos_consistency | >= 60% splits | Signal must work in most walk-forward folds, not just one |
| survives_fdr | BH q=0.10 | Correct for multiple testing across the full factor family |

All thresholds are configurable via `PromotionConfig`. The defaults are conservative.
Lowering them without documented justification defeats the purpose of the gate.
