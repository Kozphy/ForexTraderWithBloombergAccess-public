from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PurgedFold:
    train_idx: np.ndarray
    test_idx: np.ndarray


def purged_walk_forward_splits(
    n_samples: int,
    train_size: int,
    test_size: int,
    purge: int = 0,
    embargo: int = 0,
) -> list[PurgedFold]:
    """Create chronological folds with explicit purge and post-test embargo gaps."""
    if min(n_samples, train_size, test_size) <= 0:
        raise ValueError("sample and window sizes must be positive")
    if purge < 0 or embargo < 0:
        raise ValueError("purge and embargo must be non-negative")

    folds: list[PurgedFold] = []
    test_start = train_size
    while test_start + test_size <= n_samples:
        train_end = max(0, test_start - purge)
        train_start = max(0, train_end - train_size)
        train_idx = np.arange(train_start, train_end)
        test_idx = np.arange(test_start, test_start + test_size)
        if len(train_idx) > 0:
            folds.append(PurgedFold(train_idx=train_idx, test_idx=test_idx))
        test_start += test_size + embargo
    return folds


def benjamini_hochberg(p_values: Iterable[float], alpha: float = 0.05) -> np.ndarray:
    """False-discovery-rate control for multiple signal hypotheses."""
    p = np.asarray(list(p_values), dtype=float)
    if p.ndim != 1 or len(p) == 0:
        raise ValueError("p_values must be a non-empty 1D sequence")
    if np.any((p < 0) | (p > 1)):
        raise ValueError("p-values must lie in [0, 1]")
    order = np.argsort(p)
    ranked = p[order]
    thresholds = alpha * np.arange(1, len(p) + 1) / len(p)
    passed = ranked <= thresholds
    reject = np.zeros(len(p), dtype=bool)
    if np.any(passed):
        k = np.where(passed)[0].max()
        reject[order[: k + 1]] = True
    return reject


def bootstrap_mean_ci(
    returns: pd.Series,
    confidence: float = 0.95,
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap confidence interval for mean periodic return."""
    x = returns.dropna().to_numpy(dtype=float)
    if len(x) < 2:
        raise ValueError("at least two observations are required")
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for i in range(n_boot):
        means[i] = rng.choice(x, size=len(x), replace=True).mean()
    tail = (1.0 - confidence) / 2.0
    return float(np.quantile(means, tail)), float(np.quantile(means, 1.0 - tail))


def probabilistic_sharpe_ratio(
    sharpe: float,
    benchmark_sharpe: float,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Bailey/Lopez-de-Prado style probability that Sharpe exceeds a benchmark."""
    if n_obs <= 1:
        raise ValueError("n_obs must be greater than 1")
    denom_term = 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe**2
    if denom_term <= 0:
        return float("nan")
    z = (sharpe - benchmark_sharpe) * math.sqrt(n_obs - 1) / math.sqrt(denom_term)
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def deflated_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    n_trials: int,
    sharpe_std_across_trials: float,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Conservative Sharpe significance proxy adjusted for strategy selection."""
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    if n_trials == 1 or sharpe_std_across_trials <= 0:
        benchmark = 0.0
    else:
        # Extreme-value approximation for expected maximum Sharpe under selection.
        gamma = 0.5772156649015329
        z = math.sqrt(2.0 * math.log(n_trials))
        benchmark = sharpe_std_across_trials * ((1.0 - gamma) * z + gamma * (z - (math.log(math.log(n_trials)) + math.log(4.0 * math.pi)) / (2.0 * z)))
    return probabilistic_sharpe_ratio(sharpe, benchmark, n_obs, skew, kurtosis)


def volatility_target_weights(
    returns: pd.DataFrame,
    target_annual_vol: float = 0.10,
    lookback: int = 20,
    periods_per_year: int = 252,
    max_leverage: float = 2.0,
) -> pd.DataFrame:
    """Inverse-volatility weights rescaled to a portfolio volatility target."""
    vol = returns.rolling(lookback).std() * math.sqrt(periods_per_year)
    inv = 1.0 / vol.replace(0.0, np.nan)
    base = inv.div(inv.sum(axis=1), axis=0)
    port_vol_proxy = (base * vol).sum(axis=1)
    scale = (target_annual_vol / port_vol_proxy).clip(upper=max_leverage)
    return base.mul(scale, axis=0).fillna(0.0)


def square_root_market_impact(
    participation_rate: pd.Series,
    daily_volatility: pd.Series,
    coefficient: float = 0.5,
) -> pd.Series:
    """Simple square-root impact model, expressed as fractional return cost."""
    p = participation_rate.clip(lower=0.0)
    return coefficient * daily_volatility.abs() * np.sqrt(p)


def monte_carlo_stress(
    returns: pd.Series,
    horizon: int = 20,
    n_paths: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    """Bootstrap path stress test preserving the empirical one-period distribution."""
    x = returns.dropna().to_numpy(dtype=float)
    if len(x) < 2:
        raise ValueError("at least two observations are required")
    rng = np.random.default_rng(seed)
    draws = rng.choice(x, size=(n_paths, horizon), replace=True)
    terminal = np.prod(1.0 + draws, axis=1) - 1.0
    running = np.cumprod(1.0 + draws, axis=1)
    peaks = np.maximum.accumulate(running, axis=1)
    max_dd = (running / peaks - 1.0).min(axis=1)
    return pd.DataFrame({"terminal_return": terminal, "max_drawdown": max_dd})


@dataclass
class ExperimentRecord:
    experiment_id: str
    hypothesis: str
    config: dict
    metrics: dict
    code_revision: str | None = None
    data_fingerprint: str | None = None

    @staticmethod
    def fingerprint_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2, sort_keys=True), encoding="utf-8")
