# Quant Research Report Template

## 1. Research question
State the falsifiable economic hypothesis and why it might exist.

## 2. Data
Document source, instrument universe, timestamps, timezone, missing-data treatment, corporate/instrument lifecycle handling, and point-in-time availability. For FX, document pair conventions and quote direction explicitly.

## 3. Bias controls
Describe controls for look-ahead bias, survivorship bias, selection bias, data snooping, leakage, stale prices and repeated testing.

## 4. Baselines
Compare against at least one simple baseline such as buy-and-hold exposure, zero-signal, moving-average rule, or another economically justified benchmark.

## 5. Features and signal
Define every feature mathematically or algorithmically. State its lag and the information set available at decision time.

## 6. Statistical evidence
Report sample size, effect size, confidence intervals where appropriate, test statistic and p-value. Treat p-values as evidence, not proof. Discuss multiple-hypothesis testing when many signals are explored.

## 7. Walk-forward design
Document train, validation and test windows, step size, embargo/purge rules when labels overlap, hyperparameter selection procedure and number of folds.

## 8. Backtest mechanics
State rebalance timing, execution assumption, position lag, leverage limits, position bounds and cash treatment.

## 9. Costs and slippage
Report spreads, commissions, slippage, market-impact assumptions and sensitivity to worse-than-baseline costs.

## 10. Portfolio construction
Explain sizing, diversification, constraints, gross/net exposure, risk budget and concentration controls.

## 11. Results
Report gross and net return, annualized volatility, Sharpe, Sortino, maximum drawdown, turnover and transaction-cost drag.

## 12. Out-of-sample validation
Clearly separate final OOS performance from all development and model-selection data. Do not retune on the final OOS window and continue calling it OOS.

## 13. Stress and regime analysis
Break results down across volatility, trend/range and crisis-like periods. Include adverse cost and parameter scenarios.

## 14. Failure analysis
Identify where the strategy loses money, where signals reverse, and which assumptions are most fragile.

## 15. Threats to validity
Cover data quality, non-stationarity, multiple testing, model risk, implementation shortfall, market capacity and external validity.

## 16. Reproducibility
Record code revision, data fingerprint, config, random seed, environment and exact command needed to reproduce the experiment.

## 17. Conclusion
State what the evidence supports, what it does not support, and the next falsifiable experiment.
