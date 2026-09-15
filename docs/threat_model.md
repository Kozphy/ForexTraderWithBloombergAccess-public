# Threat Model

## Research integrity threats

| Threat | Mechanism | Mitigation in this repo |
|--------|-----------|-------------------------|
| Look-ahead / leakage | Same-bar feature or fill | Lagged features; `execution_delay_bars >= 1`; `assert_no_lookahead_positions`; injected-leakage tests |
| Train/OOS contamination | Overlapping windows | Chronological split + `assert_train_oos_separation` |
| Label leakage around folds | Overlapping dependent samples | Purge + embargo in purged walk-forward |
| Survivorship bias | End-of-sample universe screens | Documented controls; lineage notes; fixed synthetic universe in demo |
| Multiple testing | Many signals tried | BH FDR utility; require recording n_trials for DSR |
| Cost understatement | Ignoring spread/slippage | Mandatory cost model in realistic backtest |
| Capacity illusion | Unlimited participation | Liquidity / participation cap |
| Non-stationarity | Regime shifts | Regime breakdown + Monte Carlo stress |
| Silent promotion | Shipping failed OOS | Policy engine PASS/FAIL gates |
| Irreproducibility | Missing seed/config/data | Manifest: fingerprint, seed, git SHA, timestamp |
| Unattended live risk | Auto-trading without gates | Control plane requires human approval for paper/live; kill switch |

## Operational threats

| Threat | Mitigation |
|--------|------------|
| Retry storms | Retry budget; kill on exhaustion |
| Drift | Feature z-score monitor → alert |
| Risk breaches | Drawdown / daily-loss stopping conditions |
| Missing audit trail | Append-only JSONL audit log |

## Explicit non-goals / residual risk

- No claim of live venue connectivity, prime-broker workflows, or real Bloomberg production feeds in CI.
- Synthetic demo data cannot prove economic alpha.
- Statistical utilities are research building blocks, not substitutes for independent model validation.
- Market-impact model is a square-root approximation, not a calibrated microstructure simulator.
