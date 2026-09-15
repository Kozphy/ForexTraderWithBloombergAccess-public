# Benchmarks

Benchmarks are mechanical baselines used to contextualize a candidate signal. They are not performance targets or claims of profitability.

## Default benchmarks (OOS)

| Benchmark | Definition | Purpose |
|-----------|------------|---------|
| Zero signal | Position = 0 every bar | Sanity / flat book |
| Buy and hold | Signal = +1 with same execution delay and costs | Passive risk exposure |
| Candidate | Lagged momentum differential | Strategy under test |

Metrics compared on the same OOS window: Sharpe, CAGR, Max Drawdown, turnover, cost-adjusted return.

## Ablations

Override feature windows via the experiment `ablation` argument (e.g. `fast_window`, `slow_window`) while keeping data fingerprint and seed fixed where possible.

## Failure-mode table

| Failure mode | Observable | Expected framework behavior |
|--------------|------------|-----------------------------|
| Same-bar fill | `position == signal` | `LeakageError` |
| Train/OOS overlap | `oos_start <= train_end` | `LeakageError` |
| Missing prices under REJECT | null closes | `ValueError` |
| Duplicate timestamps | duplicate `(asset, timestamp)` | schema failure |
| OOS Sharpe below threshold | policy gate | `REJECTED` / FAIL |
| Leakage tests fail | validation flag | cannot promote |
| Drawdown stop hit | control plane | alert + kill switch |
| Retry budget exhausted | control plane | kill + audit event |
| Human approval missing | paper/live deploy | `PermissionError` |

## Interpretation rule

A PASS policy verdict on synthetic demo data demonstrates **pipeline mechanics**, not tradable edge. Economic claims require real point-in-time market data and independent review.
