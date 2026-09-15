"""Evidence harness: write reviewer-facing experiment artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from .experiment import ExperimentResult


ARTIFACT_FILES = (
    "manifest.json",
    "metrics.json",
    "validation.json",
    "risk.json",
    "policy_decision.json",
    "equity_curve.csv",
    "report.md",
)


def _json_dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def render_report(result: ExperimentResult) -> str:
    m = result.manifest
    metrics = result.metrics
    validation = result.validation
    risk = result.risk
    policy = result.policy_decision
    verdict = policy.get("verdict", "FAIL")

    lines = [
        f"# Experiment Report: `{m.experiment_id}`",
        "",
        f"**Policy verdict:** {verdict}",
        "",
        "## 1. What hypothesis was tested?",
        m.hypothesis,
        "",
        "## 2. Which data was used?",
        f"- Dataset version: `{m.dataset_version}`",
        f"- Dataset fingerprint (SHA-256): `{m.dataset_fingerprint}`",
        f"- Source config: `{m.config.get('data', {})}`",
        "",
        "## 3. Could leakage have occurred?",
        f"- Leakage tests pass: `{validation.get('leakage_tests_pass')}`",
        f"- Train end: `{validation.get('train_end')}`",
        f"- OOS start: `{validation.get('oos_start')}`",
        f"- Purge / embargo: `{validation.get('purge')}` / `{validation.get('embargo')}`",
        "- Features use lagged information; positions apply execution delay >= 1 bar.",
        "",
        "## 4. What benchmark was used?",
        f"- Benchmarks: `{m.benchmark}`",
        f"- Zero-signal OOS Sharpe: `{metrics.get('benchmark_zero_sharpe')}`",
        f"- Buy-and-hold OOS Sharpe: `{metrics.get('benchmark_buyhold_sharpe')}`",
        "",
        "## 5. Did it work out-of-sample?",
        f"- OOS Sharpe: `{metrics.get('oos_sharpe')}`",
        f"- OOS CAGR: `{metrics.get('oos_cagr')}`",
        f"- OOS max drawdown: `{metrics.get('max_drawdown')}`",
        f"- Walk-forward mean Sharpe: `{metrics.get('walk_forward_mean_sharpe')}`",
        f"- Bootstrap mean-return CI: `{validation.get('bootstrap')}`",
        "",
        "## 6. Does it survive transaction costs?",
        f"- Cost-adjusted total return: `{metrics.get('cost_adjusted_return')}`",
        f"- Transaction cost drag: `{metrics.get('transaction_cost_drag')}`",
        f"- Average turnover: `{metrics.get('average_turnover')}`",
        "",
        "## 7. What happens under stress?",
        f"- Monte Carlo terminal return p05: `{risk.get('stress_terminal_p05')}`",
        f"- Monte Carlo max drawdown p05: `{risk.get('stress_max_drawdown_p05')}`",
        f"- Regime breakdown: `{risk.get('regimes')}`",
        "",
        "## 8. Why was it promoted or rejected?",
        f"- From stage: `{policy.get('from_stage')}` → `{policy.get('to_stage')}`",
        f"- Rationale: {policy.get('rationale')}",
        "- Gates:",
    ]
    for gate in policy.get("gates", []):
        status = "PASS" if gate.get("passed") else "FAIL"
        lines.append(
            f"  - `{gate.get('name')}`: {status} (observed={gate.get('observed')}, threshold={gate.get('threshold')})"
        )

    lines.extend(
        [
            "",
            "## 9. Can the exact experiment be reproduced?",
            f"- Experiment ID: `{m.experiment_id}`",
            f"- Random seed: `{m.random_seed}`",
            f"- Git commit: `{m.git_commit_sha}`",
            f"- Execution timestamp (UTC): `{m.execution_timestamp}`",
            f"- Ablation overrides: `{m.ablation}`",
            "",
            "Reproduce with:",
            "```bash",
            "python -m forex_quant.pipeline --config configs/baseline.yaml --artifacts artifacts",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(result: ExperimentResult, root: str | Path) -> Path:
    """Write the standard evidence bundle under artifacts/<experiment_id>/."""
    out = Path(root) / result.manifest.experiment_id
    out.mkdir(parents=True, exist_ok=True)
    result.manifest.write(out / "manifest.json")
    _json_dump(out / "metrics.json", result.metrics)
    _json_dump(out / "validation.json", result.validation)
    _json_dump(out / "risk.json", result.risk)
    _json_dump(out / "policy_decision.json", result.policy_decision)
    result.equity_curve.rename("equity").to_csv(out / "equity_curve.csv", header=True)
    (out / "report.md").write_text(render_report(result), encoding="utf-8")
    return out
