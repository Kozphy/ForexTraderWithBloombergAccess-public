"""Leakage injection tests — framework must reject look-ahead."""

import pandas as pd
import pytest

from forex_quant.backtest import (
    ExecutionModel,
    LeakageError,
    assert_no_lookahead_positions,
    assert_train_oos_separation,
    inject_lookahead_leakage,
    realistic_backtest,
)
from forex_quant.pipeline import synthetic_fx_data
from forex_quant.research import add_causal_features, build_signal


def _signaled(periods: int = 80):
    return build_signal(add_causal_features(synthetic_fx_data(periods=periods)))


def test_realistic_backtest_passes_leakage_guard():
    frame = _signaled()
    bt = realistic_backtest(frame, ExecutionModel())
    assert_no_lookahead_positions(bt, delay_bars=1)


def test_injected_lookahead_is_rejected():
    frame = _signaled()
    leaked = inject_lookahead_leakage(frame)
    with pytest.raises(LeakageError):
        assert_no_lookahead_positions(leaked, delay_bars=1)


def test_train_oos_overlap_rejected():
    idx = pd.date_range("2020-01-01", periods=10, freq="B", tz="UTC")
    with pytest.raises(LeakageError):
        assert_train_oos_separation(idx[5], idx[4])


def test_execution_delay_must_be_at_least_one():
    with pytest.raises(ValueError, match="execution_delay_bars"):
        ExecutionModel(execution_delay_bars=0)
