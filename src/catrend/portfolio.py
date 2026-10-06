"""组合层：把方向信号转成目标权重。

构造顺序（每一步都可解释，不做黑箱优化）：
  1. 方向：sign(动量)
  2. 风险预算：每个资产按 1/波动 分配，等风险贡献（在零相关假设下）
  3. 目标波动：用 60 日协方差把组合的事前波动校准到 target_vol
  4. 约束：单资产上限 + 总敞口上限
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import signals


def target_weights_at(returns: pd.DataFrame, i: int, p: dict) -> pd.Series:
    """第 i 行（含）为止的信息，生成权重。i 之前的样本不足则返回全 0。"""
    tickers = returns.columns
    lookback = int(p["lookback_days"])
    window = int(p["vol_window_days"])
    if i + 1 < max(lookback, window):
        return pd.Series(0.0, index=tickers)

    hist = returns.iloc[: i + 1]
    mom = signals.momentum(hist, lookback).iloc[-1]
    vol = signals.realized_vol(hist, window, float(p["vol_floor_ann"])).iloc[-1]
    cov = hist.tail(window).cov() * 252.0
    return _weights_from_signals(mom, vol, cov, p)


def _weights_from_signals(mom: pd.Series, vol: pd.Series, cov: pd.DataFrame,
                          p: dict) -> pd.Series:
    """核心构造：方向 → 风险预算 → 目标波动 → 约束。参照实现，单独可测。"""
    tickers = mom.index
    n = len(tickers)
    if p.get("allow_short", True):
        dirn = np.sign(mom)
    else:
        dirn = (mom > 0).astype(float)      # 只做多：ETF 可直接实现
    dirn = dirn.fillna(0.0)
    if vol.isna().any() or (vol <= 0).any():
        return pd.Series(0.0, index=tickers)

    raw = dirn * float(p["target_vol_ann"]) / (vol * np.sqrt(n))
    raw = raw.replace([np.inf, -np.inf], 0.0).fillna(0.0)

    if p.get("vol_target_mode", "covariance") == "covariance":
        c = cov.reindex(index=tickers, columns=tickers).fillna(0.0)
        var = float(raw.values @ c.values @ raw.values)
        if var > 0:
            raw = raw * (float(p["target_vol_ann"]) / np.sqrt(var))

    cap = float(p["max_abs_weight"])
    raw = raw.clip(-cap, cap)
    gross = float(raw.abs().sum())
    max_gross = float(p["max_gross"])
    if gross > max_gross:
        raw = raw * (max_gross / gross)
    return raw


def build_targets(returns: pd.DataFrame, p: dict,
                  signal_dates: list[pd.Timestamp]) -> dict:
    """向量化版本：动量与波动只算一次，再逐个信号日取行。

    与 target_weights_at() 等价（tests/test_core.py 里有对拍），
    但把 30 组参数扫描从「几十分钟」压到「十几秒」。
    """
    tickers = list(returns.columns)
    lookback = int(p["lookback_days"])
    window = int(p["vol_window_days"])
    mom_all = signals.momentum(returns, lookback)
    vol_all = signals.realized_vol(returns, window, float(p["vol_floor_ann"]))
    pos = {d: i for i, d in enumerate(returns.index)}
    out: dict = {}
    for d in signal_dates:
        i = pos.get(d)
        if i is None or i + 1 < max(lookback, window):
            continue
        m, v = mom_all.iloc[i], vol_all.iloc[i]
        if m.isna().any() or v.isna().any():
            continue
        cov = returns.iloc[max(0, i - window + 1): i + 1].cov() * 252.0
        w = _weights_from_signals(m, v, cov, p)
        if float(w.abs().sum()) > 0:
            out[d] = w
    return out


def rebalance_signal_dates(index: pd.DatetimeIndex, freq: str) -> list[pd.Timestamp]:
    """信号生成日：每个周期最后一个交易日（用当天的收盘价算信号）。"""
    s = pd.Series(index, index=index)
    if freq == "monthly":
        key = s.index.to_period("M")
    elif freq == "quarterly":
        key = s.index.to_period("Q")
    elif freq == "annual":
        key = s.index.to_period("Y")
    else:
        raise ValueError(f"不认识的 rebalance 频率: {freq}")
    last = pd.Series(s.index, index=key).groupby(level=0).last()
    return [pd.Timestamp(d) for d in last.sort_values()]
