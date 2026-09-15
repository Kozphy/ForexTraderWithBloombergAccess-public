"""Reproducible experiment runner with manifests and train/val/OOS separation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .backtest import ExecutionModel, LeakageError, assert_no_lookahead_positions, assert_train_oos_separation, realistic_backtest
from .data import DataLineage, DatasetBundle, MissingDataPolicy, build_dataset
from .institutional import bootstrap_mean_ci, monte_carlo_stress, purged_walk_forward_splits
from .metrics import performance_summary
from .policy import PolicyThresholds, PromotionStage, evaluate_promotion
from .research import (
    CostModel,
    add_causal_features,
    build_signal,
    equal_weight_portfolio,
    regime_analysis,
    signal_significance,
    walk_forward_splits,
)


def git_commit_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"


def make_experiment_id(seed: int, fingerprint: str, name: str) -> str:
    raw = f"{name}|{seed}|{fingerprint}|{git_commit_sha()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"exp_{digest}"


@dataclass
class ExperimentManifest:
    experiment_id: str
    hypothesis: str
    dataset_version: str
    dataset_fingerprint: str
    config: dict[str, Any]
    random_seed: int
    git_commit_sha: str
    execution_timestamp: str
    ablation: dict[str, Any] = field(default_factory=dict)
    benchmark: str = "equal_weight_momentum_lag1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


@dataclass
class ExperimentResult:
    manifest: ExperimentManifest
    metrics: dict[str, float]
    validation: dict[str, Any]
    risk: dict[str, Any]
    policy_decision: dict[str, Any]
    equity_curve: pd.Series
    portfolio: pd.DataFrame


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _zero_signal_benchmark(frame: pd.DataFrame, execution: ExecutionModel) -> pd.DataFrame:
    out = frame.copy()
    out["signal"] = 0.0
    return equal_weight_portfolio(realistic_backtest(out, execution))


def _buy_hold_benchmark(frame: pd.DataFrame, execution: ExecutionModel) -> pd.DataFrame:
    out = frame.copy()
    out["signal"] = 1.0
    return equal_weight_portfolio(realistic_backtest(out, execution))


def run_experiment(
    raw: pd.DataFrame,
    config: dict[str, Any],
    *,
    hypothesis: str = "Lagged momentum differential has positive risk-adjusted OOS edge after costs.",
    ablation: dict[str, Any] | None = None,
    stage: PromotionStage = PromotionStage.RESEARCH,
    policy: PolicyThresholds | None = None,
) -> ExperimentResult:
    """Deterministic research run with train/validation/OOS separation."""
    seed = int(config.get("experiment", {}).get("seed", 7))
    np.random.default_rng(seed)

    data_cfg = config.get("data", {})
    lineage = DataLineage(
        source=str(data_cfg.get("source", "unknown")),
        dataset_version=str(data_cfg.get("dataset_version", "v0")),
        timezone=str(data_cfg.get("timezone", "UTC")),
        point_in_time_required=bool(data_cfg.get("point_in_time_required", True)),
        missing_policy=MissingDataPolicy(data_cfg.get("missing_policy", "reject")),
        notes=str(data_cfg.get("notes", "synthetic or research dataset")),
        transformations=("normalize_timestamps", "golden_schema_validate"),
    )
    bundle: DatasetBundle = build_dataset(raw, lineage)

    feat_cfg = config.get("features", {})
    fast = int(feat_cfg.get("fast_window", 5))
    slow = int(feat_cfg.get("slow_window", 20))
    if ablation and "fast_window" in ablation:
        fast = int(ablation["fast_window"])
    if ablation and "slow_window" in ablation:
        slow = int(ablation["slow_window"])

    featured = add_causal_features(bundle.frame, fast=fast, slow=slow)
    signaled = build_signal(featured)

    bt_cfg = config.get("backtest", {})
    execution = ExecutionModel(
        cost=CostModel(
            spread_bps=float(bt_cfg.get("spread_bps", 0.8)),
            slippage_bps=float(bt_cfg.get("slippage_bps", 0.4)),
            commission_bps=float(bt_cfg.get("commission_bps", 0.0)),
        ),
        execution_delay_bars=int(bt_cfg.get("position_lag", 1)),
        max_participation=float(bt_cfg.get("max_participation", 0.10)),
        enforce_liquidity=bool(bt_cfg.get("enforce_liquidity", True)),
    )

    # Chronological split: 70% train/val development, 30% final OOS holdout.
    timestamps = np.array(sorted(signaled["timestamp"].unique()))
    n = len(timestamps)
    if n < 50:
        raise ValueError("insufficient history for train/val/OOS split")
    train_end_idx = int(n * 0.55)
    val_end_idx = int(n * 0.70)
    train_ts = timestamps[:train_end_idx]
    val_ts = timestamps[train_end_idx:val_end_idx]
    oos_ts = timestamps[val_end_idx:]
    assert_train_oos_separation(pd.Timestamp(train_ts[-1]), pd.Timestamp(oos_ts[0]), embargo_bars=0)

    def slice_panel(ts_values: np.ndarray) -> pd.DataFrame:
        return signaled.loc[signaled["timestamp"].isin(ts_values)].copy()

    train_panel = slice_panel(train_ts)
    val_panel = slice_panel(val_ts)
    oos_panel = slice_panel(oos_ts)

    # Walk-forward on development window (train+val timestamps).
    val_cfg = config.get("validation", {})
    train_size = int(val_cfg.get("train_size", 120))
    test_size = int(val_cfg.get("test_size", 40))
    purge = int(val_cfg.get("purge", 5))
    embargo = int(val_cfg.get("embargo", 3))
    dev_ts = timestamps[:val_end_idx]
    folds = purged_walk_forward_splits(len(dev_ts), train_size, test_size, purge=purge, embargo=embargo)
    wf_sharpes: list[float] = []
    for fold in folds:
        test_slice = signaled.loc[signaled["timestamp"].isin(dev_ts[fold.test_idx])]
        port = equal_weight_portfolio(realistic_backtest(test_slice, execution))
        wf_sharpes.append(performance_summary(port["net_return"], port["turnover"])["sharpe"])

    # Also expose classic chronological splits for smoke coverage.
    _ = list(walk_forward_splits(len(dev_ts), min(train_size, len(dev_ts) // 2), min(test_size, 10)))

    oos_bt = realistic_backtest(oos_panel, execution)
    assert_no_lookahead_positions(oos_bt, delay_bars=execution.execution_delay_bars)
    oos_port = equal_weight_portfolio(oos_bt)
    oos_metrics = performance_summary(oos_port["net_return"], oos_port["turnover"])

    train_port = equal_weight_portfolio(realistic_backtest(train_panel, execution))
    val_port = equal_weight_portfolio(realistic_backtest(val_panel, execution))
    train_metrics = performance_summary(train_port["net_return"], train_port["turnover"])
    val_metrics = performance_summary(val_port["net_return"], val_port["turnover"])

    zero_bm = _zero_signal_benchmark(oos_panel, execution)
    bh_bm = _buy_hold_benchmark(oos_panel, execution)
    zero_m = performance_summary(zero_bm["net_return"], zero_bm["turnover"])
    bh_m = performance_summary(bh_bm["net_return"], bh_bm["turnover"])

    significance = signal_significance(signaled)
    regimes = regime_analysis(oos_port)

    stress = monte_carlo_stress(oos_port["net_return"], horizon=10, n_paths=200, seed=seed)
    stress_p05 = float(stress["terminal_return"].quantile(0.05))
    stress_pass = stress_p05 > -0.20

    try:
        ci_lo, ci_hi = bootstrap_mean_ci(oos_port["net_return"], n_boot=300, seed=seed)
        bootstrap = {"mean_return_ci_low": ci_lo, "mean_return_ci_high": ci_hi}
    except ValueError:
        bootstrap = {"mean_return_ci_low": float("nan"), "mean_return_ci_high": float("nan")}

    leakage_tests_pass = True
    try:
        assert_no_lookahead_positions(oos_bt, delay_bars=execution.execution_delay_bars)
        assert_train_oos_separation(pd.Timestamp(train_ts[-1]), pd.Timestamp(oos_ts[0]))
    except LeakageError:
        leakage_tests_pass = False

    cost_adjusted_return = float((1.0 + oos_port["net_return"]).prod() - 1.0)
    metrics = {
        **{f"oos_{k}": v for k, v in oos_metrics.items()},
        **{f"train_{k}": v for k, v in train_metrics.items()},
        **{f"val_{k}": v for k, v in val_metrics.items()},
        "oos_sharpe": oos_metrics["sharpe"],
        "max_drawdown": oos_metrics["max_drawdown"],
        "n_observations": oos_metrics["n_observations"],
        "cost_adjusted_return": cost_adjusted_return,
        "average_turnover": oos_metrics.get("average_turnover", float("nan")),
        "walk_forward_mean_sharpe": float(np.nanmean(wf_sharpes)) if wf_sharpes else float("nan"),
        "benchmark_zero_sharpe": zero_m["sharpe"],
        "benchmark_buyhold_sharpe": bh_m["sharpe"],
        "transaction_cost_drag": float(oos_port["cost"].sum()),
    }

    validation = {
        "leakage_tests_pass": leakage_tests_pass,
        "stress_tests_pass": stress_pass,
        "significance": significance,
        "walk_forward_folds": len(folds),
        "walk_forward_sharpes": [float(x) if x == x else None for x in wf_sharpes],
        "bootstrap": bootstrap,
        "train_end": str(train_ts[-1]),
        "val_end": str(val_ts[-1]) if len(val_ts) else None,
        "oos_start": str(oos_ts[0]),
        "purge": purge,
        "embargo": embargo,
    }

    risk = {
        "regimes": regimes,
        "stress_terminal_p05": stress_p05,
        "stress_max_drawdown_p05": float(stress["max_drawdown"].quantile(0.05)),
        "liquidity_enforced": execution.enforce_liquidity,
        "max_participation": execution.max_participation,
    }

    experiment_id = make_experiment_id(seed, bundle.fingerprint, config.get("experiment", {}).get("name", "unnamed"))
    if policy is None:
        pcfg = config.get("policy", {})
        policy = PolicyThresholds(
            min_oos_sharpe=float(pcfg.get("min_oos_sharpe", 0.5)),
            max_drawdown=float(pcfg.get("max_drawdown", -0.25)),
            min_observations=int(pcfg.get("min_observations", 60)),
            require_leakage_pass=bool(pcfg.get("require_leakage_pass", True)),
            require_stress_pass=bool(pcfg.get("require_stress_pass", True)),
            require_cost_adjusted_positive=bool(pcfg.get("require_cost_adjusted_positive", True)),
            min_cost_adjusted_return=float(pcfg.get("min_cost_adjusted_return", 0.0)),
        )
    decision = evaluate_promotion(
        experiment_id=experiment_id,
        from_stage=stage,
        metrics=metrics,
        validation=validation,
        thresholds=policy,
    )

    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        dataset_version=lineage.dataset_version,
        dataset_fingerprint=bundle.fingerprint,
        config=config,
        random_seed=seed,
        git_commit_sha=git_commit_sha(),
        execution_timestamp=datetime.now(timezone.utc).isoformat(),
        ablation=ablation or {},
        benchmark="zero_signal + buy_hold",
    )
    return ExperimentResult(
        manifest=manifest,
        metrics=metrics,
        validation=validation,
        risk=risk,
        policy_decision=decision.to_dict(),
        equity_curve=(1.0 + oos_port["net_return"].fillna(0.0)).cumprod(),
        portfolio=oos_port,
    )
