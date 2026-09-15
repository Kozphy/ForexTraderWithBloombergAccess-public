# Reproducibility

## One-command reproduce

```bash
python -m pip install -e ".[dev]"
pytest -q
python -m forex_quant.pipeline --config configs/baseline.yaml --artifacts artifacts
```

## What every experiment records

| Field | Location |
|-------|----------|
| Dataset version | `manifest.json` → `dataset_version` |
| Dataset fingerprint | `manifest.json` → `dataset_fingerprint` |
| Config | `manifest.json` → `config` |
| Random seed | `manifest.json` → `random_seed` |
| Git commit SHA | `manifest.json` → `git_commit_sha` |
| Execution timestamp | `manifest.json` → `execution_timestamp` |
| Immutable experiment ID | directory name `artifacts/exp_<hash>/` |

## Evidence bundle

```text
artifacts/<experiment_id>/
  manifest.json
  metrics.json
  validation.json
  risk.json
  policy_decision.json
  equity_curve.csv
  report.md
```

`report.md` answers the nine reviewer questions (hypothesis, data, leakage, benchmark, OOS, costs, stress, promotion rationale, reproduction).

## Determinism notes

- NumPy Generator is seeded from config.
- Dataset fingerprint is SHA-256 over canonical CSV ordering.
- Bootstrap / Monte Carlo use explicit seeds.
- Bit-identical floating results across OS/BLAS builds are not guaranteed; fingerprints and seeds are the reproducibility contract.

## Sample commands

```bash
# Baseline research config
python -m forex_quant.pipeline --config configs/baseline.yaml --artifacts artifacts

# Relaxed policy demo (PASS path for pipeline mechanics)
python -m forex_quant.pipeline --config configs/pass_demo.yaml --artifacts artifacts

# Unreachable thresholds (FAIL path with explicit gate evidence)
python -m forex_quant.pipeline --config configs/fail_demo.yaml --artifacts artifacts
```
