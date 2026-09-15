# Gap Analysis

## CURRENT (pre-upgrade)

Existing package already had:

- Causal lagged features and basic market-data validation
- Cost-aware backtest (spread / slippage / commission)
- Basic walk-forward + purged/embargo CV utilities
- Sharpe / Sortino / MaxDD metrics
- Bootstrap CI, BH-FDR, PSR/DSR, Monte Carlo stress helpers
- Minimal pytest CI

## IMPLEMENTED (this upgrade)

| Phase | Delivered |
|-------|-----------|
| 1 Data correctness | `data.py`: PIT filter, timestamp normalization, duplicates, missing policy, golden schema, lineage, fingerprint, survivorship notes; contract tests |
| 2 Research harness | `experiment.py`: deterministic runner, train/val/OOS, walk-forward, benchmarks, ablations, manifests; extended metrics (CAGR, Calmar, hit rate, exposure, TC-adjusted) |
| 3 Realistic backtest | `backtest.py`: execution delay, liquidity caps; leakage injection + rejection tests |
| 4 Policy engine | `policy.py`: research→candidate→… gates with explicit PASS/FAIL; fail_demo / pass_demo configs |
| 5 Control plane | `control_plane.py`: deploy, drift, alerts, kill, rollback, retry budget, human approval, JSONL audit, failure taxonomy |
| 6 Evidence harness | `evidence.py` → `artifacts/<experiment_id>/` with 9-question `report.md` |
| 7 CI | Multi-step GitHub Actions integrity gate (unit, contracts, leakage, harness, smoke, audit schema) |
| 8 Presentation | Recruiter-readable README + architecture / methodology / threat / reproducibility / benchmark docs |

## STILL MISSING

- Live Bloomberg/B-PIPE adapter with licensed data fixtures
- Persistent experiment registry / database (beyond JSON artifacts)
- Feature & signal registry as a versioned catalog service
- Full portfolio optimizer (risk-parity / constraints engine beyond vol-targeting utility)
- Calibrated venue-specific microstructure / market-impact models
- Real shadow/paper broker connectivity
- Distributed job orchestration for large research grids
- Formal Deflated Sharpe integration into the promotion policy gates (utility exists; not a hard gate yet)
- Multi-strategy portfolio allocation and capacity curves as first-class artifacts

## EVIDENCE

- Tests: `pytest` (data contracts, leakage, harness, policy, audit, legacy cores)
- Artifacts: `artifacts/exp_*/` including PASS and FAIL demos
- CI: `.github/workflows/ci.yml`
- Docs: `architecture.md`, `research_methodology.md`, `threat_model.md`, `reproducibility.md`, `benchmark.md`

## NEXT MILESTONE

**Point-in-time Bloomberg adapter + frozen fixture pack**

1. Define a read-only PIT market-data interface backed by recorded fixtures (no credentials in git).  
2. Add contract tests that replay fixtures through schema/lineage/fingerprint.  
3. Re-run baseline experiment on fixtures and attach real-data evidence bundles.  
4. Optionally promote Deflated Sharpe / multiple-testing counts into hard policy gates.
