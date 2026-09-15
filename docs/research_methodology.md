# Research Methodology

## Hypothesis discipline

Each experiment states a falsifiable economic hypothesis in the manifest and report. Positive historical PnL alone is not acceptance evidence.

## Data

1. Normalize timestamps to a configured timezone (default UTC).
2. Attach `available_at` for point-in-time eligibility.
3. Validate golden schema (`timestamp`, `asset`, `close`, `available_at`).
4. Apply missing-data policy (`reject` | `drop` | `forward_fill_limit`).
5. Fingerprint the cleaned panel for reproducibility.
6. Document survivorship / universe membership rules (see `data.SURVIVORSHIP_BIAS_NOTES`).

## Separation of samples

Chronological split used by the experiment runner:

- **Train** (~0–55%): development
- **Validation** (~55–70%): walk-forward / model-selection support
- **OOS holdout** (~70–100%): final evaluation; not used for tuning in the runner

Walk-forward folds on the development window use purge and embargo gaps from `institutional.purged_walk_forward_splits`.

## Features and causality

Momentum features are lagged (`shift(1)`). Positions apply `execution_delay_bars >= 1`. Same-bar fills are rejected by leakage guards.

## Costs

Net returns subtract spread, slippage and commission on turnover. Optional liquidity scaling caps participation vs ADV.

## Metrics

Reported metrics include Sharpe, Sortino, CAGR, Max Drawdown, Calmar, turnover, hit rate, exposure and cost-adjusted total return. Bootstrap mean-return confidence intervals are attached when sample size allows.

## Benchmarks

Default comparisons:

- zero-signal (flat)
- buy-and-hold (always long)

## Promotion

`policy.evaluate_promotion` advances stages only when all configured gates pass:

`research → candidate → validated → shadow → approved`

Failures yield `REJECTED` with explicit gate-level evidence. There is no silent promotion path.
