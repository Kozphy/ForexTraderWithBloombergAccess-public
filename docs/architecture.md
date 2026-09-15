# Architecture

This repository implements a research-to-control-plane pipeline for FX quantitative experiments. It is a software research framework with automated integrity tests — not a live trading system.

## Target flow

```text
Raw Market Data
      ↓
Point-in-Time Data Layer          (src/forex_quant/data.py)
      ↓
Golden Schema / Data Quality
      ↓
Feature & Signal Registry         (features.py / signals.py / research.py)
      ↓
Statistical Validation            (validation.py / institutional.py)
      ↓
Walk-Forward / Time-Series CV
      ↓
Backtesting                       (backtest.py / research.py)
      ↓
Transaction Costs / Slippage
      ↓
Portfolio & Risk                  (metrics.py / institutional.py)
      ↓
Out-of-Sample Evaluation          (experiment.py)
      ↓
Policy Gate                       (policy.py)
      ↓
Shadow/Paper Deployment           (control_plane.py)
      ↓
Monitoring → Drift → Kill Switch → Audit
      ↓
Evidence Bundle                   (evidence.py → artifacts/<experiment_id>/)
```

## Module map

| Module | Responsibility |
|--------|----------------|
| `data.py` | PIT semantics, timestamp normalization, duplicates, missing-data policy, schema, lineage, fingerprint |
| `features.py` / `signals.py` | Causal feature and signal entrypoints |
| `research.py` | Core feature/signal/backtest helpers (preserved API) |
| `backtest.py` | Execution delay, liquidity caps, leakage guards |
| `institutional.py` | Purged CV, FDR, bootstrap, PSR/DSR, impact, Monte Carlo |
| `metrics.py` | Sharpe, Sortino, CAGR, MaxDD, Calmar, hit rate, turnover, exposure |
| `experiment.py` | Deterministic runner, manifests, train/val/OOS |
| `policy.py` | Configurable promotion gates with PASS/FAIL evidence |
| `control_plane.py` | Deploy, monitor, alert, kill, rollback, JSONL audit |
| `evidence.py` | Artifact writer + reviewer report |
| `pipeline.py` | CLI orchestration |

## Experiment identity

Every run records:

- dataset version + content fingerprint (SHA-256)
- config snapshot
- random seed
- git commit SHA
- execution timestamp (UTC)
- immutable `experiment_id`

## Control-plane lifecycle

```text
Strategy → Deployment → Monitoring → Drift Detection
        → Alert → Kill Switch → Rollback → Audit (JSONL)
```

Human approval is required before `paper`/`live` deployment states. Retry budgets and stopping conditions are explicit.
