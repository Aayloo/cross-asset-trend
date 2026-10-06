"""评估层：跑策略、对照组合、成本扫描、参数稳健性、制度分解、容量。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import backtest, portfolio
from .config import Config


# ------------------------------------------------------------------ 基础运行
def cost_bps_map(cfg: Config) -> dict[str, float]:
    table = cfg.get("costs", "one_way_bps", default={})
    return {a.ticker: float(table.get(a.asset_class, 0.0)) for a in cfg.assets}


def _targets(returns: pd.DataFrame, cfg: Config, params: dict, freq: str) -> dict:
    dates = portfolio.rebalance_signal_dates(returns.index, freq)
    return portfolio.build_targets(returns, params, dates)


def run(
    panel: dict,
    cfg: Config,
    *,
    params: dict | None = None,
    cost_multiplier: float | None = None,
    label: str = "tsmom",
) -> dict:
    returns = panel["returns"]
    p = dict(cfg.get("portfolio", default={}))
    p.update(cfg.get("signal", default={}))
    if params:
        p.update(params)

    freq = p.get("rebalance", "monthly")
    targets = _targets(returns, cfg, p, freq)
    W, turnover = backtest.build_weight_path(
        returns, targets, lag_days=int(cfg.get("backtest", "tradable_lag_days", default=1)))

    cm = float(cfg.get("costs", "multiplier", default=1.0)) if cost_multiplier is None \
        else float(cost_multiplier)
    pnl = backtest.net_returns(
        returns, W, turnover, cost_bps_map(cfg),
        cost_multiplier=cm,
        financing_bps_pa=float(cfg.get("costs", "financing_bps_pa", default=0.0)),
        borrow_bps_pa=float(cfg.get("costs", "borrow_bps_pa", default=0.0)),
        allow_short=bool(p.get("allow_short", True)),
    )
    gross_exp = W.abs().sum(axis=1)
    live = gross_exp[gross_exp > 1e-9]
    start = live.index[0] if len(live) else returns.index[0]
    pnl = pnl.loc[start:]
    W_live, tr_live = W.loc[start:], turnover.loc[start:]

    stats = backtest.perf_stats(pnl["net"], name=label)
    stats.update(backtest.turnover_stats(tr_live, W_live))
    stats["gross_cagr_pct"] = backtest.perf_stats(pnl["gross"], name=label + "-gross")["cagr_pct"]
    stats["gross_sharpe"] = backtest.perf_stats(pnl["gross"], name=label + "-gross")["sharpe"]
    stats["cost_drag_pct_pa"] = round(
        float(pnl["cost"].sum() / max(len(pnl) / 252.0, 1e-9) * 100), 2)
    stats["cost_multiplier"] = cm
    return {"stats": stats, "pnl": pnl, "weights": W, "turnover": turnover,
            "targets": targets, "params": p}


# ------------------------------------------------------------------ 对照组合
def benchmark_weights(panel: dict, kind: str) -> dict:
    returns = panel["returns"]
    dates = portfolio.rebalance_signal_dates(returns.index, "monthly")
    tickers = list(returns.columns)
    if kind == "60/40":
        w = pd.Series(0.0, index=tickers)
        w["SPY"], w["IEF"] = 0.60, 0.40
    elif kind == "equal_weight":
        w = pd.Series(1.0 / len(tickers), index=tickers)
    elif kind == "cash":
        w = pd.Series(0.0, index=tickers)
    else:
        raise ValueError(kind)
    return {d: w.copy() for d in dates}


def run_benchmark(panel: dict, cfg: Config, kind: str, *, cost_multiplier: float | None = None) -> dict:
    returns = panel["returns"]
    targets = benchmark_weights(panel, kind)
    W, turnover = backtest.build_weight_path(
        returns, targets, lag_days=int(cfg.get("backtest", "tradable_lag_days", default=1)))
    cm = float(cfg.get("costs", "multiplier", default=1.0)) if cost_multiplier is None \
        else float(cost_multiplier)
    pnl = backtest.net_returns(returns, W, turnover, cost_bps_map(cfg), cost_multiplier=cm)
    live = W.abs().sum(axis=1)
    start = live[live > 1e-9].index[0]
    pnl = pnl.loc[start:]
    stats = backtest.perf_stats(pnl["net"], name=kind)
    stats.update(backtest.turnover_stats(turnover.loc[start:], W.loc[start:]))
    return {"stats": stats, "pnl": pnl, "weights": W, "turnover": turnover}


# ------------------------------------------------------------------ 成本敏感性
def cost_sweep(panel: dict, cfg: Config, multipliers: list[float]) -> pd.DataFrame:
    rows = []
    for m in multipliers:
        res = run(panel, cfg, cost_multiplier=m, label=f"cost x{m}")
        s = res["stats"]
        rows.append({"cost_multiplier": m,
                     "gross_cagr_pct": s["gross_cagr_pct"],
                     "net_cagr_pct": s["cagr_pct"],
                     "net_sharpe": s["sharpe"],
                     "cost_drag_pct_pa": s["cost_drag_pct_pa"],
                     "max_dd_pct": s["max_dd_pct"]})
    return pd.DataFrame(rows)


def break_even_multiplier(sweep: pd.DataFrame) -> float | None:
    """净年化降到 0 的成本倍数（线性插值）。"""
    x = sweep["cost_multiplier"].values.astype(float)
    y = sweep["net_cagr_pct"].values.astype(float)
    order = np.argsort(x)
    x, y = x[order], y[order]
    for i in range(1, len(x)):
        if y[i - 1] > 0 >= y[i]:
            return float(x[i - 1] + (0 - y[i - 1]) * (x[i] - x[i - 1]) / (y[i] - y[i - 1]))
    return None


# ------------------------------------------------------------------ 参数稳健性
def param_grid(panel: dict, cfg: Config) -> pd.DataFrame:
    lookbacks = cfg.get("robustness", "lookbacks", default=[252])
    vols = cfg.get("robustness", "target_vols", default=[0.10])
    rows = []
    for lb in lookbacks:
        for tv in vols:
            res = run(panel, cfg, params={"lookback_days": int(lb), "target_vol_ann": float(tv)},
                      label=f"lb{lb}-tv{tv}")
            s = res["stats"]
            rows.append({"lookback_days": int(lb), "target_vol_ann": float(tv),
                         "net_cagr_pct": s["cagr_pct"], "net_sharpe": s["sharpe"],
                         "vol_pct": s["vol_pct"], "max_dd_pct": s["max_dd_pct"],
                         "turnover_two_way_pa": s["turnover_two_way_pa"]})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 制度分解
def regime_table(panel: dict, strategy_pnl: pd.DataFrame, bench_pnl: pd.DataFrame) -> pd.DataFrame:
    """按年份、以及「谁最惨的那些天」分组。

    年份给年化百分比；条件分组给**日均 bps**——把只有几十天的子样本年化会
    夸张到没有意义（-300% 这种数字），用日均 bps 才读得出来。
    """
    r = strategy_pnl["net"]
    b = bench_pnl["net"]
    spy = panel["returns"]["SPY"]
    df = pd.DataFrame({"strat": r, "bench": b, "spy": spy}).dropna()
    years = df.index.year
    rows = []
    for y in sorted(set(years)):
        sub = df[years == y]
        rows.append({"bucket": str(y), "kind": "year", "unit": "pct_pa",
                     "strat_pct": round(float((1 + sub["strat"]).prod() - 1) * 100, 2),
                     "bench_pct": round(float((1 + sub["bench"]).prod() - 1) * 100, 2),
                     "spy_pct": round(float((1 + sub["spy"]).prod() - 1) * 100, 2)})
    buckets = [
        ("SPY worst 10% days", df["spy"] <= df["spy"].quantile(0.10)),
        ("SPY best 10% days", df["spy"] >= df["spy"].quantile(0.90)),
        ("60/40 worst 10% days", df["bench"] <= df["bench"].quantile(0.10)),
        ("60/40 best 10% days", df["bench"] >= df["bench"].quantile(0.90)),
    ]
    for label, mask in buckets:
        sub = df[mask]
        rows.append({"bucket": label, "kind": "conditional", "unit": "bps_per_day",
                     "strat_pct": round(float(sub["strat"].mean() * 1e4), 1),
                     "bench_pct": round(float(sub["bench"].mean() * 1e4), 1),
                     "spy_pct": round(float(sub["spy"].mean() * 1e4), 1)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 容量
def capacity(panel: dict, res: dict, participation: float = 0.05,
             adv_quantile: float = 0.20) -> dict:
    """在「单资产成交不超过其 ADV 的 participation」假设下估容量上限。

    用 ADV 的 20% 分位（而不是逐日最小值）作为流动性基准：真实交易不会
    恰好撞上流动性最差的那一天，用最小值会把容量压到没有意义。
    这是假设，不是事实——所以把基准和分位都写进返回值。
    """
    adv_df = panel.get("adv_usd")
    if adv_df is None:
        return {"capacity_usd_mm": None, "note": "没有成交量数据"}
    W = res["weights"]
    dW = W.diff().abs().fillna(W.abs())
    start = res["pnl"].index[0]
    dW = dW.loc[start:]
    adv_robust = adv_df.reindex(W.index).loc[start:].quantile(adv_quantile)
    dmax = dW.max()                                        # 每个资产的最大换手
    per_asset_cap = (participation * adv_robust / dmax).replace([np.inf, -np.inf], np.nan).dropna()
    if per_asset_cap.empty:
        return {"capacity_usd_mm": None, "note": "换手为 0"}
    binding = per_asset_cap.idxmin()
    table = pd.DataFrame({
        "adv_robust_usd_mm": (adv_robust / 1e6).round(1),
        "max_turnover_abs": dmax.round(4),
        "capacity_usd_mm": (per_asset_cap / 1e6).round(1),
    }).sort_values("capacity_usd_mm")
    return {
        "participation_limit": participation,
        "adv_quantile": adv_quantile,
        "capacity_usd_mm": round(float(per_asset_cap.min() / 1e6), 1),
        "binding_asset": str(binding),
        "binding_adv_usd_mm": round(float(adv_robust[binding] / 1e6), 1),
        "binding_max_turnover": round(float(dmax[binding]), 4),
        "top5_binding": table.head(5).to_dict(orient="index"),
    }
