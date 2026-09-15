# Evidence index

Generated experiment bundles live under `../artifacts/` (created by the pipeline CLI / CI).

## Sample runs

| Experiment purpose | Config | How to regenerate |
|--------------------|--------|-------------------|
| Baseline research | `configs/baseline.yaml` | `python -m forex_quant.pipeline --config configs/baseline.yaml --artifacts artifacts` |
| PASS mechanics demo | `configs/pass_demo.yaml` | `python -m forex_quant.pipeline --config configs/pass_demo.yaml --artifacts artifacts` |
| FAIL mechanics demo | `configs/fail_demo.yaml` | `python -m forex_quant.pipeline --config configs/fail_demo.yaml --artifacts artifacts` |

Each bundle contains `manifest.json`, `metrics.json`, `validation.json`, `risk.json`, `policy_decision.json`, `equity_curve.csv`, and `report.md`.

See [GAP_ANALYSIS.md](GAP_ANALYSIS.md) for CURRENT → IMPLEMENTED → STILL MISSING.
