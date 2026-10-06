"""图表产物。每张图一个结论式标题，解释文字放在图外。"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.patches import Rectangle

from . import style as st

COLOR = {"tsmom": st.PRIMARY, "gross": st.TERTIARY, "60/40": st.SECOND,
         "equal_weight": st.GOLD, "long_only": "#3F7A5A"}
LABEL = {"tsmom": "Trend, net (long-short)", "gross": "Trend, gross", "60/40": "60/40",
         "equal_weight": "Equal weight (11)", "long_only": "Trend, net (long-only)"}


def _tint(c: str, a: float):
    r, g, b = to_rgb(c)
    return (1 - (1 - r) * a, 1 - (1 - g) * a, 1 - (1 - b) * a)


def ex1_design(out: Path) -> None:
    """示意图：文字就是内容，不适用「图内不放文字」。"""
    st.apply()
    fig, ax = plt.subplots(figsize=(9.2, 3.0))
    steps = [
        ("数据", "11 个 ETF\n复权价 · 日频", st.SECOND),
        ("信号", "12 个月动量\nsign(+1 / -1)", st.TERTIARY),
        ("组合", "波动率目标 10%\n单资产上限 35%", st.GOLD),
        ("成本", "换手 × 分類 bps\n按调仓日扣", st.PRIMARY),
        ("净净值", "月度调仓\n次日成交", st.INK),
    ]
    for i, (title, body, color) in enumerate(steps):
        ax.add_patch(Rectangle((i, 0), 0.92, 1.0, facecolor=_tint(color, 0.12),
                               edgecolor=color, linewidth=1.3))
        ax.text(i + 0.46, 0.68, title, ha="center", va="center", fontsize=13,
                fontweight="700", color=color)
        ax.text(i + 0.46, 0.33, body, ha="center", va="center", fontsize=9.4, color=st.MUTED)
        if i < len(steps) - 1:
            ax.annotate("", xy=(i + 0.99, 0.5), xytext=(i + 0.93, 0.5),
                        arrowprops=dict(arrowstyle="->", color=st.MUTED, linewidth=1.2))
    ax.set_xlim(-0.03, len(steps) + 0.03)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axis("off")
    st.frame(fig, ax, "策略设计：五个环节，每一步都能单独检验",
             "信号只用截至当日的收盘数据；次日收盘成交，再下一个交易日才开始承担收益")
    st.tight(fig, top=0.76, bottom=0.06, left=0.02, right=0.99)
    st.source(fig, "来源：本文实现（config/base.yml 定义全部参数）。")
    st.audit(fig, "ex1-design")
    st.save(fig, out / "ex1-design")


def ex2_nav(out: Path, runs: dict, bench: dict) -> None:
    st.apply()
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    series = [("tsmom", runs["tsmom"]["pnl"]["net"], 2.2, "-", runs["tsmom"]["stats"]["cagr_pct"]),
              ("60/40", bench["60/40"]["pnl"]["net"], 1.6, "-", bench["60/40"]["stats"]["cagr_pct"]),
              ("equal_weight", bench["equal_weight"]["pnl"]["net"], 1.4, "-",
               bench["equal_weight"]["stats"]["cagr_pct"]),
              ("long_only", runs["long_only"]["pnl"]["net"], 1.6, (0, (1, 2)),
               runs["long_only"]["stats"]["cagr_pct"]),
              ("gross", runs["tsmom"]["pnl"]["gross"], 1.4, (0, (4, 3)),
               runs["tsmom"]["stats"]["gross_cagr_pct"])]
    for key, r, lw, ls, cagr in series:
        nav = (1 + r.fillna(0)).cumprod()
        ax.plot(nav.index, nav.values, color=COLOR[key], linewidth=lw, linestyle=ls,
                label=f"{LABEL[key]}  CAGR {cagr}%")
    ax.set_yscale("log")
    st.tidy(ax)
    ax.set_xlabel("年份  year")
    ax.set_ylabel("累计净值（对数刻度）")
    st.frame(fig, ax, "成本之后：趋势的净收益低于毛收益，但路径与 60/40 明显不同",
             "同一份数据、同样的成本假设与成交滞后；毛收益仅作对照，不可投资")
    st.legend(ax, ncol=3, y=-0.20)
    st.tight(fig, top=0.80, bottom=0.27)
    st.source(fig, "来源：本文回测，ETF 复权价，月度调仓，次日成交。")
    st.audit(fig, "ex2-nav")
    st.save(fig, out / "ex2-nav")


def ex3_contribution(out: Path, panel: dict, res: dict, cfg) -> None:
    st.apply()
    W, R = res["weights"], panel["returns"]
    contrib = (W * R).loc[res["pnl"].index[0]:]
    group = cfg.group
    by_group = {}
    for t in contrib.columns:
        by_group.setdefault(group[t], []).append(t)
    ann = {g: float(contrib[cols].sum(axis=1).mean() * 252 * 100) for g, cols in by_group.items()}
    items = sorted(ann.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    colors = [st.PRIMARY if v > 0 else st.TERTIARY for _, v in items]
    ax.barh(range(len(items)), [v for _, v in items], color=colors, height=0.55)
    ax.set_yticks(range(len(items)), [g for g, _ in items])
    ax.axvline(0, color=st.RULE, linewidth=1)
    st.tidy(ax, grid_axis="x")
    ax.set_xlabel("对年化收益的贡献（%，毛口径）")
    total = sum(ann.values())
    best = max(ann.items(), key=lambda kv: kv[1])
    st.frame(fig, ax, f"钱是从哪一类资产赚来的：{best[0]} 贡献 {best[1]:.2f} 个百分点",
             f"毛贡献合计 {total:.2f}%（毛口径，未扣成本）；分资产类别汇总")
    st.tight(fig, top=0.79, bottom=0.16)
    st.source(fig, "来源：本文计算，逐日 w × r 的年化均值。")
    st.audit(fig, "ex3-contribution")
    st.save(fig, out / "ex3-contribution")


def ex4_rolling(out: Path, res: dict, bench: dict, window: int = 252) -> None:
    st.apply()
    s = res["pnl"]["net"]
    b = bench["60/40"]["pnl"]["net"]
    df = pd.DataFrame({"s": s, "b": b}).dropna()
    corr = df["s"].rolling(window).corr(df["b"])
    sharpe = (df["s"].rolling(window).mean() / df["s"].rolling(window).std()) * np.sqrt(252)
    fig, axes = plt.subplots(2, 1, figsize=(9.2, 4.8), sharex=True)
    axes[0].plot(corr.index, corr.values, color=st.SECOND, linewidth=1.4)
    axes[0].axhline(0, color=st.RULE, linewidth=1)
    axes[0].set_ylim(-1, 1)
    axes[0].set_ylabel("相关系数")
    st.tidy(axes[0])
    axes[0].set_title("滚动 12 个月与 60/40 的相关性", fontsize=10.6, color=st.MUTED, loc="left", pad=10)
    axes[1].plot(sharpe.index, sharpe.values, color=st.PRIMARY, linewidth=1.4)
    axes[1].axhline(0, color=st.RULE, linewidth=1)
    axes[1].set_ylabel("滚动 Sharpe")
    axes[1].set_xlabel("年份  year")
    st.tidy(axes[1])
    axes[1].set_title("滚动 12 个月 Sharpe", fontsize=10.6, color=st.MUTED, loc="left", pad=10)
    med = float(corr.dropna().median())
    st.frame(fig, axes[0], "它与 60/40 的相关性不是稳定的，中位数落在 0 附近",
             f"滚动 12 个月相关性中位数 {med:+.2f}；下图为策略自身的滚动 Sharpe")
    st.tight(fig, top=0.84, bottom=0.16, hspace=0.42)
    st.source(fig, "来源：本文回测，日频收益，滚动窗口 252 个交易日。")
    st.audit(fig, "ex4-rolling")
    st.save(fig, out / "ex4-rolling")


def ex5_cost(out: Path, sweep: pd.DataFrame, be: float | None) -> None:
    st.apply()
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    ax.plot(sweep["cost_multiplier"], sweep["net_cagr_pct"], color=st.PRIMARY,
            marker="o", markersize=4, linewidth=1.8)
    ax.axhline(0, color=st.RULE, linewidth=1)
    if be:
        ax.axvline(be, color=st.INK, linewidth=0.9, alpha=0.35)
    st.tidy(ax)
    ax.set_xlabel("成本倍数（1.0 = 基准假设）")
    ax.set_ylabel("净年化收益（%）")
    be_txt = f"净收益归零在 {be:.1f} 倍成本假设" if be else "样本内未出现归零"
    st.frame(fig, ax, f"这套策略对成本的容忍度：{be_txt}", "横轴为成本假设的倍数，纵轴为扣除成本后的年化收益")
    st.tight(fig, top=0.79, bottom=0.20)
    st.source(fig, "来源：本文回测，按资产类别的单边 bps 乘以倍数。")
    st.audit(fig, "ex5-cost")
    st.save(fig, out / "ex5-cost")


def ex6_heatmap(out: Path, grid: pd.DataFrame) -> None:
    st.apply()
    piv = grid.pivot(index="lookback_days", columns="target_vol_ann", values="net_sharpe")
    fig, ax = plt.subplots(figsize=(8.6, 3.9))
    im = ax.imshow(piv.values, aspect="auto", cmap="RdYlBu_r", origin="lower")
    ax.set_xticks(range(len(piv.columns)), [f"{c:.3g}" for c in piv.columns])
    ax.set_yticks(range(len(piv.index)), [str(i) for i in piv.index])
    ax.set_xlabel("目标波动率  target vol")
    ax.set_ylabel("回看窗口（交易日）  lookback")
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("净 Sharpe", fontsize=9)
    st.frame(fig, ax, "参数不是单点最优，而是一片平台——这是稳健性的最低要求",
             "净 Sharpe 对回看窗口 × 目标波动率的敏感性；每一格都是完整回测")
    st.tight(fig, top=0.78, bottom=0.14, right=0.97)
    st.source(fig, "来源：本文回测，含成本。")
    st.audit(fig, "ex6-heatmap")
    st.save(fig, out / "ex6-heatmap")


def ex7_stress(out: Path, regime: pd.DataFrame) -> None:
    st.apply()
    sel = regime[regime["kind"] == "conditional"].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9.4, 3.9))
    x = np.arange(len(sel))
    w = 0.36
    ax.bar(x - w / 2, sel["strat_pct"], w, color=st.PRIMARY, label="Trend")
    ax.bar(x + w / 2, sel["bench_pct"], w, color=st.SECOND, label="60/40")
    ax.axhline(0, color=st.RULE, linewidth=1)
    ax.set_xticks(x, [b.replace(" worst ", "\nworst ").replace(" best ", "\nbest ")
                      for b in sel["bucket"]])
    ax.set_ylabel("该条件下的日均收益（bps）")
    ax.tick_params(axis="x", labelsize=9)
    st.tidy(ax)
    worst = sel[sel["bucket"].str.startswith("SPY worst")].iloc[0]
    ratio = abs(worst["bench_pct"] / worst["strat_pct"]) if worst["strat_pct"] else float("nan")
    st.frame(fig, ax,
             f"最坏的那些天它确实能防：标普最差 10% 的交易日里，它跌得比 60/40 少 {ratio:.1f} 倍",
             "条件收益用日均 bps 表示（子样本只有几十天，年化会夸张到无意义）")
    st.legend(ax, ncol=2, y=-0.19)
    st.tight(fig, top=0.79, bottom=0.30)
    st.source(fig, "来源：本文回测。")
    st.audit(fig, "ex7-stress")
    st.save(fig, out / "ex7-stress")


def ex8_drawdown(out: Path, res: dict, bench: dict) -> None:
    st.apply()
    fig, ax = plt.subplots(figsize=(9.2, 3.8))
    for key, r in [("tsmom", res["pnl"]["net"]), ("60/40", bench["60/40"]["pnl"]["net"])]:
        nav = (1 + r.fillna(0)).cumprod()
        dd = (nav / nav.cummax() - 1) * 100
        ax.plot(dd.index, dd.values, color=COLOR[key], linewidth=1.6, label=LABEL[key])
    st.tidy(ax)
    ax.set_ylabel("回撤（%）")
    ax.set_xlabel("年份  year")
    st.frame(fig, ax, "回撤比收益更能区分这两条路径",
             "同一区间内的回撤曲线；深度与持续时间都要看")
    st.legend(ax, ncol=2, y=-0.19)
    st.tight(fig, top=0.79, bottom=0.24)
    st.source(fig, "来源：本文回测。")
    st.audit(fig, "ex8-drawdown")
    st.save(fig, out / "ex8-drawdown")


def ex9_capacity(out: Path, panel: dict, res: dict, levels_mm=(10, 25, 50, 100, 250, 500)) -> None:
    st.apply()
    adv = panel["adv_usd"]
    W = res["weights"]
    start = res["pnl"].index[0]
    dW = W.diff().abs().fillna(W.abs()).loc[start:]
    adv_robust = adv.reindex(W.index).loc[start:].quantile(0.20)
    max_turnover = dW.max()
    x = np.array(levels_mm, dtype=float) * 1e6
    y = [float((aum * max_turnover / adv_robust).max() * 100) for aum in x]
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    ax.plot(x / 1e6, y, color=st.PRIMARY, marker="o", markersize=4, linewidth=1.8)
    ax.axhline(5, color=st.INK, linewidth=0.9, alpha=0.35)
    ax.set_xlabel("管理规模（百万美元）  AUM")
    ax.set_ylabel("单资产最大成交占 ADV（%）")
    st.tidy(ax)
    st.frame(fig, ax, "容量约束来自最不流动的那个资产，不是来自策略本身",
             "ADV 取 20% 分位（保守的流动性基准）；横线为 5% 的常见参与率上限")
    st.tight(fig, top=0.79, bottom=0.20)
    st.source(fig, "来源：本文计算，ADV 为 60 日美元成交额均值的 20% 分位。")
    st.audit(fig, "ex9-capacity")
    st.save(fig, out / "ex9-capacity")
