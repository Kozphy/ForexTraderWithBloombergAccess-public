"""Research harness, policy, control-plane and evidence tests."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forex_quant.control_plane import (
    AuditLog,
    ControlPlane,
    Deployment,
    DeploymentState,
    FailureClass,
)
from forex_quant.evidence import ARTIFACT_FILES, write_artifacts
from forex_quant.experiment import load_config, run_experiment
from forex_quant.metrics import cagr, calmar_ratio, hit_rate, performance_summary
from forex_quant.pipeline import synthetic_fx_data
from forex_quant.policy import PolicyThresholds, PromotionStage, evaluate_promotion


def test_extended_metrics():
    r = pd.Series([0.01, -0.005, 0.02, 0.0, 0.015])
    assert np.isfinite(cagr(r))
    assert np.isfinite(calmar_ratio(r))
    assert 0.0 <= hit_rate(r) <= 1.0
    summary = performance_summary(r, turnover=pd.Series([0.1] * 5))
    assert "calmar" in summary


def test_experiment_runner_writes_repro_fields(tmp_path: Path):
    config = load_config("configs/baseline.yaml")
    result = run_experiment(synthetic_fx_data(periods=400), config)
    assert result.manifest.dataset_version
    assert result.manifest.dataset_fingerprint
    assert result.manifest.random_seed == 7
    assert result.manifest.git_commit_sha
    assert result.manifest.execution_timestamp
    assert "oos_sharpe" in result.metrics
    out = write_artifacts(result, tmp_path)
    for name in ARTIFACT_FILES:
        assert (out / name).exists()
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "What hypothesis was tested?" in report
    assert "Can the exact experiment be reproduced?" in report


def test_policy_never_silently_promotes_failure():
    decision = evaluate_promotion(
        experiment_id="exp_test",
        from_stage=PromotionStage.RESEARCH,
        metrics={
            "oos_sharpe": -1.0,
            "max_drawdown": -0.5,
            "n_observations": 10,
            "cost_adjusted_return": -0.2,
        },
        validation={"leakage_tests_pass": False, "stress_tests_pass": False},
        thresholds=PolicyThresholds(),
    )
    assert decision.passed is False
    assert decision.to_stage is PromotionStage.REJECTED
    assert decision.to_dict()["verdict"] == "FAIL"


def test_policy_pass_promotes_one_stage():
    decision = evaluate_promotion(
        experiment_id="exp_ok",
        from_stage=PromotionStage.RESEARCH,
        metrics={
            "oos_sharpe": 1.2,
            "max_drawdown": -0.05,
            "n_observations": 200,
            "cost_adjusted_return": 0.1,
        },
        validation={"leakage_tests_pass": True, "stress_tests_pass": True},
        thresholds=PolicyThresholds(min_oos_sharpe=0.5),
    )
    assert decision.passed is True
    assert decision.to_stage is PromotionStage.CANDIDATE
    assert decision.to_dict()["verdict"] == "PASS"


def test_control_plane_kill_and_audit(tmp_path: Path):
    audit_path = tmp_path / "audit.jsonl"
    plane = ControlPlane(AuditLog(audit_path))
    dep = Deployment(strategy_id="mom", experiment_id="exp_1", human_approved=True, state=DeploymentState.PAPER)
    plane.deploy(dep)
    alerts = plane.check_risk(dep.deployment_id, drawdown=-0.20, daily_pnl=-0.01)
    assert alerts
    plane.kill(dep.deployment_id, "drawdown stop", FailureClass.RISK_LIMIT)
    assert plane.deployments[dep.deployment_id].state is DeploymentState.KILLED
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 3
    parsed = [json.loads(line) for line in lines]
    assert {e["event_type"] for e in parsed} >= {"deploy", "alert", "kill_switch"}


def test_human_approval_gate(tmp_path: Path):
    plane = ControlPlane(AuditLog(tmp_path / "a.jsonl"))
    dep = Deployment(strategy_id="x", experiment_id="e", state=DeploymentState.LIVE, human_approved=False)
    with pytest.raises(PermissionError):
        plane.deploy(dep)


def test_pass_demo_config_can_pass(tmp_path: Path):
    config = load_config("configs/pass_demo.yaml")
    result = run_experiment(synthetic_fx_data(periods=400), config)
    write_artifacts(result, tmp_path)
    assert result.validation["leakage_tests_pass"] is True
    assert result.policy_decision["verdict"] == "PASS"
    assert result.policy_decision["to_stage"] == "candidate"


def test_fail_demo_config_is_rejected(tmp_path: Path):
    config = load_config("configs/fail_demo.yaml")
    result = run_experiment(synthetic_fx_data(periods=400), config)
    write_artifacts(result, tmp_path)
    assert result.policy_decision["verdict"] == "FAIL"
    assert result.policy_decision["to_stage"] == "rejected"
