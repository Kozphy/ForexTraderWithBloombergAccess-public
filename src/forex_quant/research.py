from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class CostModel:
    spread_bps: float = 0.8
    slippage_bps: float = 0.4
    commission_bps: float = 0.0

    @property
    def total_bps(self) -> float:
        return self.spread_bps + self.slippage_bps + self.commission_bps


def validate_market_data(frame: pd.DataFrame) -> None:
    required = {"timestamp", "asset", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if frame[["timestamp", "asset"]].duplicated().any():
        raise ValueError("Duplicate asset/timestamp observations detected")
    if frame["close"].isna().any() or (frame["close"] <= 0).any():
        raise ValueError("Prices must be positive and non-null")


def add_causal_features(frame: pd.DataFrame, fast: int = 5, slow: int = 20) -> pd.DataFrame:
    validate_market_data(frame)
    out = frame.sort_values(["asset", "timestamp"]).copy()
    grouped = out.groupby("asset", group_keys=False)
    out["return_1d"] = grouped["close"].pct_change()
    out["momentum_fast"] = grouped["close"].pct_change(fast).shift(1)
    out["momentum_slow"] = grouped["close"].pct_change(slow).shift(1)
    out["volatility_20d"] = grouped["return_1d"].transform(
        lambda s: s.shift(1).rolling(20, min_periods=10).std()
    )
    return out


def build_signal(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    raw = np.sign(out["momentum_fast"] - out["momentum_slow"])
    out["signal"] = raw.fillna(0.0).clip(-1.0, 1.0)
    return out


def signal_significance(frame: pd.DataFrame) -> dict[str, float]:
    usable = frame[["signal", "return_1d"]].dropna()
    if len(usable) < 3:
        return {"n": float(len(usable)), "t_stat": float("nan"), "p_value": float("nan")}
    strategy_obs = usable["signal"] * usable["return_1d"]
    t_stat, p_value = stats.ttest_1samp(strategy_obs, popmean=0.0)
    return {"n": float(len(usable)), "t_stat": float(t_stat), "p_value": float(p_value)}


def walk_forward_splits(n: int, train_size: int, test_size: int, step: int | None = None):
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = test_size if step is None else step
    start = 0
    while start + train_size + test_size <= n:
        train = slice(start, start + train_size)
        test = slice(start + train_size, start + train_size + test_size)
        yield train, test
        start += step


def cost_aware_backtest(frame: pd.DataFrame, cost: CostModel = CostModel()) -> pd.DataFrame:
    out = frame.sort_values(["timestamp", "asset"]).copy()
    # Today's position uses yesterday's completed signal: no same-bar execution assumption.
    out["position"] = out.groupby("asset")["signal"].shift(1).fillna(0.0)
    out["gross_return"] = out["position"] * out["return_1d"].fillna(0.0)
    out["turnover"] = out.groupby("asset")["position"].diff().abs().fillna(out["position"].abs())
    out["cost"] = out["turnover"] * cost.total_bps / 10_000.0
    out["net_return"] = out["gross_return"] - out["cost"]
    return out


def equal_weight_portfolio(backtest: pd.DataFrame) -> pd.DataFrame:
    daily = backtest.groupby("timestamp", as_index=True).agg(
        gross_return=("gross_return", "mean"),
        net_return=("net_return", "mean"),
        turnover=("turnover", "mean"),
        cost=("cost", "mean"),
    )
    return daily.sort_index()


def regime_analysis(portfolio: pd.DataFrame) -> dict[str, dict[str, float]]:
    vol = portfolio["net_return"].rolling(20, min_periods=10).std()
    threshold = vol.median()
    regimes = pd.Series(np.where(vol > threshold, "high_vol", "normal"), index=portfolio.index)
    result: dict[str, dict[str, float]] = {}
    for regime in ["normal", "high_vol"]:
        sample = portfolio.loc[regimes == regime, "net_return"].dropna()
        result[regime] = {
            "observations": float(len(sample)),
            "mean_return": float(sample.mean()) if len(sample) else float("nan"),
            "volatility": float(sample.std(ddof=1)) if len(sample) > 1 else float("nan"),
        }
    return result
