"""Realistic cost-aware backtesting with leakage guards."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .research import CostModel


@dataclass(frozen=True)
class ExecutionModel:
    """Execution realism knobs layered on top of CostModel."""

    cost: CostModel = CostModel()
    execution_delay_bars: int = 1
    max_participation: float = 0.10
    adv_notional: float = 1e9
    order_notional: float = 1e6
    enforce_liquidity: bool = True

    def __post_init__(self) -> None:
        if self.execution_delay_bars < 1:
            raise ValueError("execution_delay_bars must be >= 1 to avoid look-ahead fills")
        if self.max_participation <= 0 or self.max_participation > 1:
            raise ValueError("max_participation must be in (0, 1]")


class LeakageError(ValueError):
    """Raised when a backtest configuration or panel admits look-ahead."""


def assert_no_lookahead_positions(frame: pd.DataFrame, *, delay_bars: int = 1) -> None:
    """Reject panels where position depends on same-bar or future signal."""
    if delay_bars < 1:
        raise LeakageError("delay_bars < 1 admits look-ahead fills")
    required = {"signal", "position"}
    missing = required.difference(frame.columns)
    if missing:
        raise LeakageError(f"Missing columns for leakage check: {sorted(missing)}")

    # Position at t must equal signal lagged by delay_bars.
    expected = frame.groupby("asset")["signal"].shift(delay_bars).fillna(0.0)
    actual = frame["position"].fillna(0.0)
    # Liquidity scaling may shrink magnitude but not change sign timing.
    if not np.allclose(np.sign(actual), np.sign(expected), equal_nan=True):
        raise LeakageError("position timing does not match lagged signal (possible look-ahead)")
    ratio = np.ones(len(actual))
    nonzero = expected.to_numpy() != 0
    ratio[nonzero] = actual.to_numpy()[nonzero] / expected.to_numpy()[nonzero]
    if len(ratio[nonzero]) and (ratio[nonzero].max() - ratio[nonzero].min() > 1e-9):
        raise LeakageError("inconsistent liquidity scaling across bars")
    if (np.abs(actual) > np.abs(expected) + 1e-12).any():
        raise LeakageError("position magnitude exceeds lagged signal (possible look-ahead)")


def assert_train_oos_separation(
    train_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    *,
    embargo_bars: int = 0,
    index: pd.DatetimeIndex | None = None,
) -> None:
    """Reject overlapping or insufficiently embargoed train/OOS windows."""
    if oos_start <= train_end:
        raise LeakageError("OOS start must be strictly after train end")
    if embargo_bars > 0 and index is not None:
        train_pos = index.get_indexer([train_end], method=None)[0]
        oos_pos = index.get_indexer([oos_start], method=None)[0]
        if train_pos < 0 or oos_pos < 0:
            raise LeakageError("train_end/oos_start not found in index")
        if oos_pos - train_pos - 1 < embargo_bars:
            raise LeakageError("Insufficient embargo between train and OOS")


def realistic_backtest(frame: pd.DataFrame, execution: ExecutionModel = ExecutionModel()) -> pd.DataFrame:
    """Cost-aware backtest with execution delay and optional liquidity caps."""
    out = frame.sort_values(["timestamp", "asset"]).copy()
    delay = execution.execution_delay_bars
    out["position"] = out.groupby("asset")["signal"].shift(delay).fillna(0.0)

    if execution.enforce_liquidity:
        participation = execution.order_notional / execution.adv_notional
        if participation > execution.max_participation:
            scale = execution.max_participation / participation
            out["position"] = out["position"] * scale
            out["liquidity_scale"] = scale
        else:
            out["liquidity_scale"] = 1.0
    else:
        out["liquidity_scale"] = 1.0

    out["gross_return"] = out["position"] * out["return_1d"].fillna(0.0)
    out["turnover"] = out.groupby("asset")["position"].diff().abs().fillna(out["position"].abs())
    out["cost"] = out["turnover"] * execution.cost.total_bps / 10_000.0
    out["net_return"] = out["gross_return"] - out["cost"]
    assert_no_lookahead_positions(out, delay_bars=delay)
    return out


def inject_lookahead_leakage(frame: pd.DataFrame) -> pd.DataFrame:
    """Intentionally create a leaking panel for negative tests."""
    out = frame.copy()
    # Same-bar execution: classic look-ahead / future-function bias.
    out["position"] = out["signal"].fillna(0.0)
    out["gross_return"] = out["position"] * out["return_1d"].fillna(0.0)
    out["turnover"] = out.groupby("asset")["position"].diff().abs().fillna(out["position"].abs())
    out["cost"] = 0.0
    out["net_return"] = out["gross_return"]
    return out
