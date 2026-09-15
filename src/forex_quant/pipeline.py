"""End-to-end orchestration for research experiments and evidence generation."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .evidence import write_artifacts
from .experiment import load_config, run_experiment
from .metrics import performance_summary
from .policy import PolicyThresholds, PromotionStage
from .research import (
    CostModel,
    add_causal_features,
    build_signal,
    cost_aware_backtest,
    equal_weight_portfolio,
    regime_analysis,
    signal_significance,
)


def synthetic_fx_data(seed: int = 7, periods: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=periods, freq="B", tz="UTC")
    rows = []
    for asset, start in [("EURUSD", 1.10), ("GBPUSD", 1.30), ("USDJPY", 110.0)]:
        shocks = rng.normal(0.0, 0.004, size=periods)
        prices = start * np.exp(np.cumsum(shocks))
        rows.extend(
            {
                "timestamp": ts,
                "asset": asset,
                "close": float(price),
                "available_at": ts,
            }
            for ts, price in zip(dates, prices)
        )
    return pd.DataFrame(rows)


def run_research(frame: pd.DataFrame) -> dict:
    """Legacy smoke entrypoint preserved for backward compatibility."""
    featured = add_causal_features(frame)
    signaled = build_signal(featured)
    significance = signal_significance(signaled)
    bt = cost_aware_backtest(signaled, CostModel())
    portfolio = equal_weight_portfolio(bt)
    metrics = performance_summary(portfolio["net_return"], portfolio["turnover"])
    return {
        "metrics": metrics,
        "significance": significance,
        "regimes": regime_analysis(portfolio),
        "gross_total_return": float((1.0 + portfolio["gross_return"]).prod() - 1.0),
        "net_total_return": float((1.0 + portfolio["net_return"]).prod() - 1.0),
        "cost_drag": float(portfolio["cost"].sum()),
    }


def run_full_pipeline(
    config_path: str | Path,
    artifacts_root: str | Path = "artifacts",
    *,
    promote_from: PromotionStage = PromotionStage.RESEARCH,
    policy: PolicyThresholds | None = None,
) -> Path:
    config = load_config(config_path)
    seed = int(config.get("experiment", {}).get("seed", 7))
    periods = int(config.get("data", {}).get("periods", 800))
    raw = synthetic_fx_data(seed=seed, periods=periods)
    result = run_experiment(raw, config, stage=promote_from, policy=policy)
    return write_artifacts(result, artifacts_root)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run FX quant research pipeline")
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--legacy", action="store_true", help="Run legacy smoke summary only")
    args = parser.parse_args(argv)

    if args.legacy:
        result = run_research(synthetic_fx_data())
        for section, value in result.items():
            print(f"{section}: {value}")
        return

    out = run_full_pipeline(args.config, args.artifacts)
    print(f"Wrote evidence bundle to {out}")


if __name__ == "__main__":
    main()
