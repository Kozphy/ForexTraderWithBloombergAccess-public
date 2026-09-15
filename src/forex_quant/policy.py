"""Machine-readable promotion policy with explicit PASS/FAIL evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class PromotionStage(str, Enum):
    RESEARCH = "research"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    SHADOW = "shadow"
    APPROVED = "approved"
    REJECTED = "rejected"


STAGE_ORDER = [
    PromotionStage.RESEARCH,
    PromotionStage.CANDIDATE,
    PromotionStage.VALIDATED,
    PromotionStage.SHADOW,
    PromotionStage.APPROVED,
]


@dataclass(frozen=True)
class PolicyThresholds:
    min_oos_sharpe: float = 0.5
    max_drawdown: float = -0.25
    min_observations: int = 60
    require_leakage_pass: bool = True
    require_stress_pass: bool = True
    require_cost_adjusted_positive: bool = True
    min_cost_adjusted_return: float = 0.0


@dataclass
class GateResult:
    name: str
    passed: bool
    observed: Any
    threshold: Any
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyDecision:
    experiment_id: str
    from_stage: PromotionStage
    to_stage: PromotionStage
    passed: bool
    gates: list[GateResult] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "from_stage": self.from_stage.value,
            "to_stage": self.to_stage.value,
            "passed": self.passed,
            "rationale": self.rationale,
            "gates": [g.to_dict() for g in self.gates],
            "verdict": "PASS" if self.passed else "FAIL",
        }


def evaluate_promotion(
    *,
    experiment_id: str,
    from_stage: PromotionStage,
    metrics: dict[str, float],
    validation: dict[str, Any],
    thresholds: PolicyThresholds = PolicyThresholds(),
) -> PolicyDecision:
    """Evaluate configurable gates; never silently promote on failure."""
    gates: list[GateResult] = []

    oos_sharpe = float(metrics.get("oos_sharpe", float("nan")))
    gates.append(
        GateResult(
            name="oos_sharpe",
            passed=oos_sharpe > thresholds.min_oos_sharpe,
            observed=oos_sharpe,
            threshold=thresholds.min_oos_sharpe,
            detail="Out-of-sample Sharpe must exceed threshold",
        )
    )

    max_dd = float(metrics.get("max_drawdown", 0.0))
    gates.append(
        GateResult(
            name="max_drawdown",
            passed=max_dd > thresholds.max_drawdown,
            observed=max_dd,
            threshold=thresholds.max_drawdown,
            detail="Max drawdown must be milder than configured floor",
        )
    )

    n_obs = int(metrics.get("n_observations", 0))
    gates.append(
        GateResult(
            name="min_observations",
            passed=n_obs >= thresholds.min_observations,
            observed=n_obs,
            threshold=thresholds.min_observations,
        )
    )

    leakage_ok = bool(validation.get("leakage_tests_pass", False))
    gates.append(
        GateResult(
            name="leakage_tests",
            passed=(leakage_ok if thresholds.require_leakage_pass else True),
            observed=leakage_ok,
            threshold=thresholds.require_leakage_pass,
        )
    )

    stress_ok = bool(validation.get("stress_tests_pass", False))
    gates.append(
        GateResult(
            name="stress_tests",
            passed=(stress_ok if thresholds.require_stress_pass else True),
            observed=stress_ok,
            threshold=thresholds.require_stress_pass,
        )
    )

    cost_adj = float(metrics.get("cost_adjusted_return", float("nan")))
    cost_ok = cost_adj > thresholds.min_cost_adjusted_return
    gates.append(
        GateResult(
            name="cost_adjusted_return",
            passed=(cost_ok if thresholds.require_cost_adjusted_positive else True),
            observed=cost_adj,
            threshold=thresholds.min_cost_adjusted_return,
        )
    )

    all_pass = all(g.passed for g in gates)
    if not all_pass:
        return PolicyDecision(
            experiment_id=experiment_id,
            from_stage=from_stage,
            to_stage=PromotionStage.REJECTED,
            passed=False,
            gates=gates,
            rationale="One or more promotion gates failed; strategy was not promoted.",
        )

    try:
        idx = STAGE_ORDER.index(from_stage)
    except ValueError as exc:
        raise ValueError(f"Cannot promote from terminal stage {from_stage}") from exc
    if idx >= len(STAGE_ORDER) - 1:
        next_stage = from_stage
    else:
        next_stage = STAGE_ORDER[idx + 1]

    return PolicyDecision(
        experiment_id=experiment_id,
        from_stage=from_stage,
        to_stage=next_stage,
        passed=True,
        gates=gates,
        rationale=f"All gates passed; promoted {from_stage.value} -> {next_stage.value}.",
    )
