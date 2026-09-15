import numpy as np
import pandas as pd

from forex_quant.institutional import (
    benjamini_hochberg,
    bootstrap_mean_ci,
    deflated_sharpe_ratio,
    monte_carlo_stress,
    purged_walk_forward_splits,
    square_root_market_impact,
    volatility_target_weights,
)


def test_purged_walk_forward_has_no_overlap():
    folds = purged_walk_forward_splits(120, train_size=40, test_size=10, purge=5, embargo=3)
    assert folds
    for fold in folds:
        assert fold.train_idx.max() < fold.test_idx.min()
        assert fold.test_idx.min() - fold.train_idx.max() >= 6


def test_bh_rejects_smallest_hypotheses():
    reject = benjamini_hochberg([0.001, 0.01, 0.2, 0.9], alpha=0.05)
    assert reject.tolist() == [True, True, False, False]


def test_bootstrap_ci_is_ordered():
    s = pd.Series(np.linspace(-0.01, 0.02, 100))
    lo, hi = bootstrap_mean_ci(s, n_boot=200, seed=1)
    assert lo < hi


def test_deflated_sharpe_returns_probability():
    p = deflated_sharpe_ratio(1.2, n_obs=252, n_trials=20, sharpe_std_across_trials=0.25)
    assert 0.0 <= p <= 1.0


def test_vol_target_weights_are_finite():
    rng = np.random.default_rng(0)
    r = pd.DataFrame(rng.normal(0, 0.01, size=(100, 3)), columns=list("ABC"))
    w = volatility_target_weights(r, lookback=20)
    assert np.isfinite(w.to_numpy()).all()


def test_market_impact_increases_with_participation():
    p = pd.Series([0.01, 0.04])
    vol = pd.Series([0.02, 0.02])
    impact = square_root_market_impact(p, vol)
    assert impact.iloc[1] > impact.iloc[0]


def test_monte_carlo_stress_shape():
    s = pd.Series(np.linspace(-0.01, 0.01, 50))
    stress = monte_carlo_stress(s, horizon=5, n_paths=100, seed=1)
    assert list(stress.columns) == ["terminal_return", "max_drawdown"]
    assert len(stress) == 100
