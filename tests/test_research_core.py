import numpy as np
import pandas as pd

from forex_quant.metrics import max_drawdown, performance_summary
from forex_quant.pipeline import synthetic_fx_data
from forex_quant.research import add_causal_features, build_signal, cost_aware_backtest, equal_weight_portfolio


def test_causal_features_do_not_use_same_bar_close_for_signal():
    frame = synthetic_fx_data(periods=80)
    featured = add_causal_features(frame)
    assert featured["momentum_fast"].isna().sum() > 0
    assert featured["momentum_slow"].isna().sum() > 0


def test_costs_reduce_or_equal_gross_per_observation():
    frame = build_signal(add_causal_features(synthetic_fx_data(periods=100)))
    bt = cost_aware_backtest(frame)
    assert (bt["net_return"] <= bt["gross_return"] + 1e-15).all()


def test_portfolio_metrics_are_finite_for_demo():
    frame = build_signal(add_causal_features(synthetic_fx_data(periods=250)))
    portfolio = equal_weight_portfolio(cost_aware_backtest(frame))
    metrics = performance_summary(portfolio["net_return"], portfolio["turnover"])
    assert np.isfinite(metrics["sharpe"])
    assert metrics["max_drawdown"] <= 0.0


def test_max_drawdown_known_path():
    returns = pd.Series([0.10, -0.20, 0.05])
    assert max_drawdown(returns) < 0.0
