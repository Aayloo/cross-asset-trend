"""核心不变量：没有未来函数、成本只发生在成交日、权重守约束、净值恒等式。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from catrend import backtest, portfolio, signals

PARAMS = {
    "lookback_days": 60,
    "vol_window_days": 20,
    "vol_floor_ann": 0.04,
    "target_vol_ann": 0.10,
    "max_abs_weight": 0.35,
    "max_gross": 2.0,
    "vol_target_mode": "covariance",
    "allow_short": True,
}


def _panel(n_days: int = 400, n_assets: int = 4, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-01", periods=n_days)
    return pd.DataFrame(rng.normal(0, 0.01, (n_days, n_assets)),
                        index=idx, columns=[f"A{i}" for i in range(n_assets)])


# --------------------------------------------------------------- 未来函数
def test_weights_ignore_future_data():
    R = _panel()
    i = 300
    base = portfolio.target_weights_at(R, i, PARAMS)

    R_future = R.copy()
    R_future.iloc[i + 1:] *= 25.0            # 放大未来，不应影响今天的权重
    assert np.allclose(base.values, portfolio.target_weights_at(R_future, i, PARAMS).values)

    R_past = R.copy()
    R_past.iloc[:i] *= 0.5                   # 改过去，必须影响今天的权重
    assert not np.allclose(base.values, portfolio.target_weights_at(R_past, i, PARAMS).values)


def test_weight_path_applies_with_lag():
    R = _panel(n_days=8, n_assets=2)
    tickers = list(R.columns)
    target = pd.Series([0.5, -0.5], index=tickers)
    signal_day = R.index[2]
    W, turnover = backtest.build_weight_path(R, {signal_day: target}, lag_days=1)

    # t+1 收盘成交：t+1 当天仍是旧权重（0），t+2 起才持有目标权重
    assert np.allclose(W.loc[R.index[3]].values, 0.0)
    assert np.allclose(W.loc[R.index[4]].values, target.values)
    assert turnover.loc[R.index[3]] == pytest.approx(1.0)
    assert turnover.drop(R.index[3]).sum() == pytest.approx(0.0)


def test_turnover_only_on_rebalance_days():
    R = _panel(n_days=120, n_assets=3)
    dates = portfolio.rebalance_signal_dates(R.index, "monthly")
    targets = {d: pd.Series([0.3, 0.3, 0.3], index=R.columns) for d in dates}
    W, turnover = backtest.build_weight_path(R, targets, lag_days=1)
    # 目标权重恒定，但账面会随价格漂移，所以每次再平衡都会产生换手；
    # 换手只允许出现在「信号日 + 1 个交易日」这些成交日上
    pos = {d: i for i, d in enumerate(R.index)}
    scheduled = {R.index[pos[d] + 1] for d in dates if pos.get(d) is not None
                 and pos[d] + 1 < len(R.index)}
    traded = set(turnover[turnover > 1e-9].index)
    assert traded == scheduled
    assert turnover[~turnover.index.isin(scheduled)].abs().sum() == 0


# --------------------------------------------------------------- 约束
def test_weights_respect_caps():
    R = _panel()
    for i in (200, 250, 300, 399):
        w = portfolio.target_weights_at(R, i, PARAMS)
        assert w.abs().max() <= PARAMS["max_abs_weight"] + 1e-9
        assert w.abs().sum() <= PARAMS["max_gross"] + 1e-9


def test_long_only_has_no_negative_weights():
    R = _panel()
    p = dict(PARAMS, allow_short=False)
    w = portfolio.target_weights_at(R, 399, p)
    assert (w >= -1e-12).all()


# --------------------------------------------------------------- 恒等式
def test_net_equals_gross_minus_costs():
    R = _panel(n_days=200, n_assets=3)
    dates = portfolio.rebalance_signal_dates(R.index, "monthly")
    targets = {d: pd.Series([0.5, -0.3, 0.2], index=R.columns) for d in dates}
    W, turnover = backtest.build_weight_path(R, targets)
    pnl = backtest.net_returns(R, W, turnover, {t: 3.0 for t in R.columns},
                               cost_multiplier=1.0)
    lhs = pnl["net"] + pnl["cost"] + pnl["financing"]
    assert np.allclose(lhs.values, pnl["gross"].values)
    assert pnl["cost"].sum() > 0


def test_higher_costs_lower_net():
    R = _panel(n_days=300, n_assets=4)
    dates = portfolio.rebalance_signal_dates(R.index, "monthly")
    targets = {d: pd.Series([0.4, -0.4, 0.2, -0.2], index=R.columns) for d in dates}
    W, turnover = backtest.build_weight_path(R, targets)
    cheap = backtest.net_returns(R, W, turnover, {t: 1.0 for t in R.columns})["net"].sum()
    dear = backtest.net_returns(R, W, turnover, {t: 10.0 for t in R.columns})["net"].sum()
    assert cheap > dear


# --------------------------------------------------------------- 快慢对拍
def test_momentum_matches_bruteforce():
    R = _panel(n_days=200, n_assets=3)
    lb = 60
    fast = signals.momentum(R, lb)
    slow = (1.0 + R).rolling(lb).apply(np.prod, raw=True) - 1.0
    common = fast.dropna().index
    assert np.allclose(fast.loc[common].values, slow.loc[common].values, atol=1e-10)


def test_vectorized_build_targets_matches_reference():
    R = _panel(n_days=320, n_assets=4)
    dates = portfolio.rebalance_signal_dates(R.index, "monthly")
    fast = portfolio.build_targets(R, PARAMS, dates)
    assert fast, "至少应该有一个信号日通过预热"
    for d, w in fast.items():
        i = R.index.get_loc(d)
        ref = portfolio.target_weights_at(R, i, PARAMS)
        assert np.allclose(w.values, ref.values, atol=1e-9)
