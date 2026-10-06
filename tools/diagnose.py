"""诊断脚本：先确认信号本身有没有预测力，再谈组合构造。

跑法：python tools/diagnose.py

回答三个问题：
  1. sign(动量) 对下一期收益的命中率是多少（按资产、按回看窗口）？
  2. 把组合简化成 1/N 等权，多空是否比只做多更好？（即：择时加不加价值）
  3. 把方向反过来，结果是否对称？（符号约定的自检）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from catrend import backtest, config as cm, data, portfolio, signals  # noqa: E402


def main() -> None:
    cfg = cm.load(ROOT / "config" / "base.yml")
    panel = data.build_panel(cfg)
    R = panel["returns"]
    bps = {a.ticker: float(cfg.get("costs", "one_way_bps")[a.asset_class]) for a in cfg.assets}
    dates = portfolio.rebalance_signal_dates(R.index, "monthly")
    pos = {d: i for i, d in enumerate(R.index)}

    def run_weights(fn, label: str, lookback: int = 252) -> None:
        mom = signals.momentum(R, lookback)
        targets = {}
        for d in dates:
            m = mom.iloc[pos[d]]
            if m.isna().any():
                continue
            targets[d] = fn(m)
        W, tr = backtest.build_weight_path(R, targets, 1)
        pnl = backtest.net_returns(R, W, tr, bps)
        live = W.abs().sum(axis=1)
        s = live[live > 1e-9].index[0]
        net = backtest.perf_stats(pnl["net"].loc[s:], name=label)
        gro = backtest.perf_stats(pnl["gross"].loc[s:], name=label + " gross")
        print(f"{label:<26} gross CAGR {gro['cagr_pct']:6.2f}%  "
              f"gross Sharpe {gro['sharpe']:5.2f}  |  net CAGR {net['cagr_pct']:6.2f}%  "
              f"net Sharpe {net['sharpe']:5.2f}  maxDD {net['max_dd_pct']:6.1f}%")

    n = len(R.columns)
    print("=== 组合简化：信号方向不变，权重改成等权 ===")
    run_weights(lambda m: np.sign(m) / n, "long-short 1/N")
    run_weights(lambda m: (m > 0).astype(float) / n, "long-only 1/N (positive)")
    run_weights(lambda m: -np.sign(m) / n, "reversed 1/N (sanity check)")
    run_weights(lambda m: pd.Series(1.0 / n, index=m.index), "always long 1/N")

    print("\n=== 信号命中率（符号 vs 未来 21 个交易日收益）===")
    fwd = R.rolling(21).sum().shift(-21)
    for lb in (21, 63, 126, 252, 504):
        mom = signals.momentum(R, lb)
        hit = (np.sign(fwd) == np.sign(mom)).where(mom.notna() & fwd.notna())
        by_asset = hit.mean().round(3)
        print(f"lookback {lb:>4}: 平均命中率 {np.nanmean(hit.values):.3f}   "
              f"最低 {by_asset.min():.3f}  最高 {by_asset.max():.3f}")


if __name__ == "__main__":
    main()
