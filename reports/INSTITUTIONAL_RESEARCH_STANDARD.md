# Institutional Quant Research Standard

A strategy is not considered production-grade merely because a backtest is profitable.

## Validation stack

```text
Hypothesis
  -> Point-in-time data
  -> Purged / embargoed time-series CV
  -> Multiple-testing correction
  -> Bootstrap confidence intervals
  -> Probabilistic / Deflated Sharpe evidence
  -> Cost-aware backtest
  -> Volatility targeting / portfolio construction
  -> Capacity + market-impact analysis
  -> Out-of-sample holdout
  -> Monte Carlo + regime stress
  -> Reproducible experiment record
```

## Institutional gates

```text
INSTITUTIONAL_RESEARCH_READY =
RESEARCH_VALID
AND PURGED_CV_PASS
AND EMBARGO_PASS
AND MULTIPLE_TESTING_CONTROL_PASS
AND BOOTSTRAP_CI_REPORTED
AND DEFLATED_SHARPE_REPORTED
AND VOL_TARGETING_REVIEWED
AND MARKET_IMPACT_MODELED
AND CAPACITY_REVIEWED
AND MONTE_CARLO_STRESS_PASS
AND EXPERIMENT_FINGERPRINTED
```

## Required evidence

Every strategy review should include:

1. Economic hypothesis and expected mechanism.
2. Point-in-time dataset definition and source lineage.
3. Train/validation/OOS chronology with purge and embargo parameters.
4. Number of hypotheses tried and the multiple-testing method used.
5. Confidence intervals for key return statistics.
6. Raw Sharpe, Probabilistic Sharpe and Deflated Sharpe evidence.
7. Gross-to-net performance bridge including spread, commission, slippage and market impact.
8. Portfolio constraints, leverage policy and volatility-targeting assumptions.
9. Capacity assumptions including participation-rate limits.
10. Regime and Monte Carlo stress results.
11. Failure cases and conditions under which the signal should be disabled.
12. Config, code revision and data fingerprint sufficient for reproduction.

## Important limitation

The included statistical utilities are educational/research building blocks. They should not be treated as a substitute for independent model validation, execution simulation, venue-specific microstructure analysis, or professional investment-risk governance.
