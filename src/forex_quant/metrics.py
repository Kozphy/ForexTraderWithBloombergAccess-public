"""Institutional-style performance metrics for research evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def sharpe_ratio(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    r = returns.dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(np.sqrt(periods) * r.mean() / r.std(ddof=1))


def sortino_ratio(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    r = returns.dropna()
    downside = r[r < 0]
    if len(downside) < 2 or downside.std(ddof=1) == 0:
        return float("nan")
    return float(np.sqrt(periods) * r.mean() / downside.std(ddof=1))


def max_drawdown(returns: pd.Series) -> float:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    peak = wealth.cummax()
    drawdown = wealth / peak - 1.0
    return float(drawdown.min())


def cagr(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    r = returns.fillna(0.0)
    if len(r) == 0:
        return float("nan")
    wealth = float((1.0 + r).prod())
    years = len(r) / float(periods)
    if years <= 0 or wealth <= 0:
        return float("nan")
    return float(wealth ** (1.0 / years) - 1.0)


def calmar_ratio(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    dd = abs(max_drawdown(returns))
    if dd == 0:
        return float("nan")
    return float(cagr(returns, periods=periods) / dd)


def hit_rate(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) == 0:
        return float("nan")
    return float((r > 0).mean())


def average_exposure(positions: pd.Series) -> float:
    p = positions.dropna()
    if len(p) == 0:
        return float("nan")
    return float(p.abs().mean())


def performance_summary(
    returns: pd.Series,
    turnover: pd.Series | None = None,
    positions: pd.Series | None = None,
    *,
    periods: int = TRADING_DAYS,
) -> dict[str, float]:
    r = returns.dropna()
    annual_return = float(r.mean() * periods) if len(r) else float("nan")
    annual_vol = float(r.std(ddof=1) * np.sqrt(periods)) if len(r) > 1 else float("nan")
    result = {
        "annualized_return": annual_return,
        "annualized_volatility": annual_vol,
        "cagr": cagr(r, periods=periods),
        "sharpe": sharpe_ratio(r, periods=periods),
        "sortino": sortino_ratio(r, periods=periods),
        "max_drawdown": max_drawdown(r),
        "calmar": calmar_ratio(r, periods=periods),
        "hit_rate": hit_rate(r),
        "n_observations": float(len(r)),
    }
    if turnover is not None:
        result["average_turnover"] = float(turnover.dropna().mean())
    if positions is not None:
        result["average_exposure"] = average_exposure(positions)
    return result
