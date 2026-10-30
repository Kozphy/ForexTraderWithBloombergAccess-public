# Experiment Report: `exp_9b9f1c9a066c7c38`

**Policy verdict:** PASS

## 1. What hypothesis was tested?
Lagged momentum differential has positive risk-adjusted OOS edge after costs.

## 2. Which data was used?
- Dataset version: `synthetic_fx_v1`
- Dataset fingerprint (SHA-256): `6944673719842cde3e3910a36660fd685935f88f178b6c736ae7b0c7bcd9275c`
- Source config: `{'source': 'synthetic_demo', 'dataset_version': 'synthetic_fx_v1', 'timezone': 'UTC', 'point_in_time_required': True, 'missing_policy': 'reject', 'periods': 800, 'notes': 'Demo config with relaxed policy thresholds to illustrate a PASS path on synthetic data.'}`

## 3. Could leakage have occurred?
- Leakage tests pass: `True`
- Train end: `2021-09-07 00:00:00+00:00`
- OOS start: `2022-02-23 00:00:00+00:00`
- Purge / embargo: `5` / `3`
- Features use lagged information; positions apply execution delay >= 1 bar.

## 4. What benchmark was used?
- Benchmarks: `zero_signal + buy_hold`
- Zero-signal OOS Sharpe: `nan`
- Buy-and-hold OOS Sharpe: `-0.26180937046267394`

## 5. Did it work out-of-sample?
- OOS Sharpe: `1.0034466798558452`
- OOS CAGR: `0.037334432114433325`
- OOS max drawdown: `-0.030235263417347946`
- Walk-forward mean Sharpe: `0.31323685388451056`
- Bootstrap mean-return CI: `{'mean_return_ci_low': -0.00018060103455960153, 'mean_return_ci_high': 0.00042098516292809855}`

## 6. Does it survive transaction costs?
- Cost-adjusted total return: `0.03552539958565859`
- Transaction cost drag: `0.00118`
- Average turnover: `0.24583333333333332`

## 7. What happens under stress?
- Monte Carlo terminal return p05: `-0.012774247605606703`
- Monte Carlo max drawdown p05: `-0.012615611467578846`
- Regime breakdown: `{'normal': {'observations': 125.0, 'mean_return': 0.00041495076297375734, 'volatility': 0.0019942210806081625}, 'high_vol': {'observations': 115.0, 'mean_return': -0.00014174442098643112, 'volatility': 0.0026524530419919003}}`

## 8. Why was it promoted or rejected?
- From stage: `research` → `candidate`
- Rationale: All gates passed; promoted research -> candidate.
- Gates:
  - `oos_sharpe`: PASS (observed=1.0034466798558452, threshold=-5.0)
  - `max_drawdown`: PASS (observed=-0.030235263417347946, threshold=-1.0)
  - `min_observations`: PASS (observed=240, threshold=10)
  - `leakage_tests`: PASS (observed=True, threshold=True)
  - `stress_tests`: PASS (observed=True, threshold=False)
  - `cost_adjusted_return`: PASS (observed=0.03552539958565859, threshold=0.0)

## 9. Can the exact experiment be reproduced?
- Experiment ID: `exp_9b9f1c9a066c7c38`
- Random seed: `7`
- Git commit: `c911ee7fa4c98ee1b7ff009845498d61da724525`
- Execution timestamp (UTC): `2026-10-30T11:03:19.998507+00:00`
- Ablation overrides: `{}`

Reproduce with:
```bash
python -m forex_quant.pipeline --config configs/baseline.yaml --artifacts artifacts
```
