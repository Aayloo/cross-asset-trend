"""回测引擎：权重路径、成本、净值、绩效指标。

时间线（每一个日期都写清楚，避免未来函数）：
  t    : 用截至 t 日收盘的数据算信号 → 目标权重
  t+1  : 收盘成交（lag_days=1），当天按 t+1 的换手扣成本
  t+2  : 新权重开始承担收益
  期间 : 权重随价格漂移，直到下一个成交日
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def build_weight_path(returns: pd.DataFrame, targets: dict[pd.Timestamp, pd.Series],
                      lag_days: int = 1) -> tuple[pd.DataFrame, pd.Series]:
    """把「信号日 → 目标权重」变成逐日权重路径与实际换手。"""
    dates = returns.index
    tickers = returns.columns
    pos = {d: i for i, d in enumerate(dates)}
    schedule: dict[pd.Timestamp, pd.Series] = {}
    for sd, w in targets.items():
        if sd not in pos:
            continue
        j = pos[sd] + int(lag_days)
        if j < len(dates):
            schedule[dates[j]] = w.reindex(tickers).fillna(0.0)

    W = pd.DataFrame(0.0, index=dates, columns=tickers)
    turnover = pd.Series(0.0, index=dates)
    cur = pd.Series(0.0, index=tickers)
    for d in dates:
        W.loc[d] = cur                       # 当天持有的是此前决定的权重
        r = returns.loc[d]
        denom = 1.0 + float((cur * r).sum())
        cur = (cur * (1.0 + r) / denom) if denom > 0 else cur
        if d in schedule:                    # 当天收盘调仓
            tgt = schedule[d]
            turnover.loc[d] = float((tgt - cur).abs().sum())
            cur = tgt.copy()
    return W, turnover


def net_returns(returns: pd.DataFrame, W: pd.DataFrame, turnover: pd.Series,
                bps: dict[str, float], *, cost_multiplier: float = 1.0,
                financing_bps_pa: float = 0.0, borrow_bps_pa: float = 0.0,
                allow_short: bool = True) -> pd.DataFrame:
    gross = (W * returns).sum(axis=1)
    cost_bps = pd.Series(0.0, index=returns.columns)
    for t in returns.columns:
        cost_bps[t] = float(bps.get(t, 0.0))
    # 按每个资产的成交额加权：turnover 已按 |Δw| 计，逐资产算更准确
    per_asset_turnover = (W.diff().abs().fillna(W.abs()))
    cost = (per_asset_turnover * cost_bps).sum(axis=1) / 1e4
    cost = cost * float(cost_multiplier)

    fin = 0.0
    if financing_bps_pa:
        lev = (W.abs().sum(axis=1) - 1.0).clip(lower=0.0) / 252.0
        fin = fin + lev * float(financing_bps_pa) / 1e4
    if borrow_bps_pa:
        short = (-W).clip(lower=0.0).sum(axis=1) / 252.0
        fin = fin + short * float(borrow_bps_pa) / 1e4
    return pd.DataFrame({"gross": gross, "cost": cost, "financing": fin,
                         "net": gross - cost - fin}, index=returns.index)


def nav_from_returns(r: pd.Series) -> pd.Series:
    return (1.0 + r.fillna(0.0)).cumprod()


def perf_stats(r: pd.Series, *, name: str = "", periods_per_year: int = 252) -> dict:
    r = r.dropna()
    if len(r) == 0:
        return {}
    nav = nav_from_returns(r)
    years = len(r) / periods_per_year
    cagr = float(nav.iloc[-1] ** (1.0 / years) - 1.0)
    vol = float(r.std(ddof=1) * np.sqrt(periods_per_year))
    dd = nav / nav.cummax() - 1.0
    downside = r[r < 0].std(ddof=1) * np.sqrt(periods_per_year)
    w12 = [float(np.prod(1.0 + r.iloc[i:i + periods_per_year]) - 1.0)
           for i in range(0, max(len(r) - periods_per_year, 0), 5)]
    return {
        "name": name,
        "start": r.index[0].date().isoformat(),
        "end": r.index[-1].date().isoformat(),
        "years": round(years, 2),
        "cagr_pct": round(cagr * 100, 2),
        "vol_pct": round(vol * 100, 2),
        "sharpe": round(cagr / vol, 3) if vol > 0 else None,
        "max_dd_pct": round(float(dd.min() * 100), 2),
        "worst_12m_pct": round(min(w12) * 100, 2) if w12 else None,
        "sortino": round(cagr / float(downside), 3) if downside and downside > 0 else None,
        "skew": round(float(r.skew()), 2),
        "hit_rate_pct": round(float((r > 0).mean() * 100), 1),
        "final_nav": round(float(nav.iloc[-1]), 3),
    }


def turnover_stats(turnover: pd.Series, W: pd.DataFrame, periods_per_year: int = 252) -> dict:
    tr = turnover.dropna()
    n_years = len(tr) / periods_per_year
    gross_pa = float(tr.sum() / max(n_years, 1e-9))          # 单边合计
    return {
        "turnover_two_way_pa": round(gross_pa / 2.0, 2),      # 行业惯例：两向口径
        "turnover_one_way_pa": round(gross_pa, 2),
        "avg_gross_exposure": round(float(W.abs().sum(axis=1).mean()), 2),
        "avg_net_exposure": round(float(W.sum(axis=1).mean()), 2),
        "avg_n_positions": round(float((W.abs() > 1e-6).sum(axis=1).mean()), 1),
        "n_rebalances": int((turnover > 1e-9).sum()),
    }
