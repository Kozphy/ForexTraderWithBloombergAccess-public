"""Production control plane: deployment, monitoring, kill switch, audit."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any
import uuid


class DeploymentState(str, Enum):
    SHADOW = "shadow"
    PAPER = "paper"
    LIVE = "live"
    KILLED = "killed"
    ROLLED_BACK = "rolled_back"


class FailureClass(str, Enum):
    DATA_QUALITY = "data_quality"
    LEAKAGE = "leakage"
    DRIFT = "drift"
    RISK_LIMIT = "risk_limit"
    EXECUTION = "execution"
    POLICY = "policy"
    INFRA = "infra"
    UNKNOWN = "unknown"


@dataclass
class RetryBudget:
    max_retries: int = 3
    used: int = 0

    def allow(self) -> bool:
        return self.used < self.max_retries

    def consume(self) -> None:
        if not self.allow():
            raise RuntimeError("retry budget exhausted")
        self.used += 1


@dataclass
class StoppingConditions:
    max_drawdown: float = -0.15
    max_daily_loss: float = -0.03
    drift_zscore: float = 3.0


@dataclass
class Alert:
    severity: str
    failure_class: FailureClass
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["failure_class"] = self.failure_class.value
        return d


@dataclass
class Deployment:
    strategy_id: str
    experiment_id: str
    state: DeploymentState = DeploymentState.SHADOW
    human_approved: bool = False
    retry_budget: RetryBudget = field(default_factory=RetryBudget)
    stopping: StoppingConditions = field(default_factory=StoppingConditions)
    deployment_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def require_human_approval(self) -> None:
        if not self.human_approved:
            raise PermissionError("human approval gate not satisfied")


class AuditLog:
    """Append-only JSONL audit trail."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


class ControlPlane:
    """Strategy lifecycle: deploy → monitor → alert → kill/rollback."""

    def __init__(self, audit: AuditLog) -> None:
        self.audit = audit
        self.deployments: dict[str, Deployment] = {}

    def deploy(self, deployment: Deployment) -> Deployment:
        if deployment.state in {DeploymentState.LIVE, DeploymentState.PAPER}:
            deployment.require_human_approval()
        self.deployments[deployment.deployment_id] = deployment
        self.audit.append(
            "deploy",
            {
                "deployment_id": deployment.deployment_id,
                "strategy_id": deployment.strategy_id,
                "experiment_id": deployment.experiment_id,
                "state": deployment.state.value,
                "human_approved": deployment.human_approved,
            },
        )
        return deployment

    def detect_drift(self, deployment_id: str, feature_zscore: float) -> Alert | None:
        dep = self.deployments[deployment_id]
        if abs(feature_zscore) >= dep.stopping.drift_zscore:
            alert = Alert(
                severity="high",
                failure_class=FailureClass.DRIFT,
                message=f"feature drift z={feature_zscore:.2f}",
            )
            self.audit.append("alert", {"deployment_id": deployment_id, **alert.to_dict()})
            return alert
        return None

    def check_risk(self, deployment_id: str, *, drawdown: float, daily_pnl: float) -> list[Alert]:
        dep = self.deployments[deployment_id]
        alerts: list[Alert] = []
        if drawdown <= dep.stopping.max_drawdown:
            alerts.append(
                Alert(
                    severity="critical",
                    failure_class=FailureClass.RISK_LIMIT,
                    message=f"drawdown {drawdown:.4f} breached stop",
                )
            )
        if daily_pnl <= dep.stopping.max_daily_loss:
            alerts.append(
                Alert(
                    severity="critical",
                    failure_class=FailureClass.RISK_LIMIT,
                    message=f"daily pnl {daily_pnl:.4f} breached stop",
                )
            )
        for alert in alerts:
            self.audit.append("alert", {"deployment_id": deployment_id, **alert.to_dict()})
        return alerts

    def kill(self, deployment_id: str, reason: str, failure_class: FailureClass = FailureClass.UNKNOWN) -> Deployment:
        dep = self.deployments[deployment_id]
        dep.state = DeploymentState.KILLED
        self.audit.append(
            "kill_switch",
            {
                "deployment_id": deployment_id,
                "reason": reason,
                "failure_class": failure_class.value,
            },
        )
        return dep

    def rollback(self, deployment_id: str, reason: str) -> Deployment:
        dep = self.deployments[deployment_id]
        dep.state = DeploymentState.ROLLED_BACK
        self.audit.append("rollback", {"deployment_id": deployment_id, "reason": reason})
        return dep

    def retry(self, deployment_id: str, failure_class: FailureClass) -> None:
        dep = self.deployments[deployment_id]
        if not dep.retry_budget.allow():
            self.kill(deployment_id, "retry budget exhausted", FailureClass.INFRA)
            raise RuntimeError("retry budget exhausted; deployment killed")
        dep.retry_budget.consume()
        self.audit.append(
            "retry",
            {
                "deployment_id": deployment_id,
                "used": dep.retry_budget.used,
                "max": dep.retry_budget.max_retries,
                "failure_class": failure_class.value,
            },
        )
