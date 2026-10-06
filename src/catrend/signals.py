"""信号层：时序动量 + 已实现波动。

全部指标在 t 日**只使用截至 t 日收盘**的信息；权重在 t+1 日收盘成交，
从 t+2 日起才承担收益（见 backtest.build_weight_path）。这个滞后是刻意的，
也是 tests/test_no_lookahead.py 要证明的东西。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def momentum(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """过去 lookback 日的累计收益（含当日）。

    用对数收益的累加实现——和逐窗连乘等价，但快两个数量级。
    仍然是纯向后看的：第 t 行只用到 t-lookback+1 … t 的数据。
    """
    lr = np.log1p(returns)
    cs = lr.cumsum()
    out = cs - cs.shift(lookback)
    out.iloc[:lookback] = np.nan
    return np.expm1(out)


def realized_vol(returns: pd.DataFrame, window: int, floor: float) -> pd.DataFrame:
    """年化已实现波动，带下限（避免除以极小值产生巨大仓位）。"""
    vol = returns.rolling(window, min_periods=window).std() * np.sqrt(252.0)
    return vol.clip(lower=floor)


def direction(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """把动量转成方向：+1 做多、-1 做空、0 数据不足。"""
    m = momentum(returns, lookback)
    return np.sign(m).where(m.notna(), 0.0)
