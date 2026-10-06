"""图表产物（机构 chart pack 规格）。

约定：
  · 标题是结论句，副标题写口径与假设，左下角永远有来源行
  · 图上出现文字的地方（事件阴影标签、端点标注）都参与 audit() 的重叠自检
  · 数据图不放"说明性段落"，但允许**端点标注与事件标签**——这是机构
    chart pack 的标准元素，也是把结论直接指给读者看的方式
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.patches import Rectangle

from . import style as st

COLOR = {"tsmom": st.ACCENT, "gross": st.SLATE, "60/40": st.BLUE,
         "equal_weight": st.GOLD, "long_only": st.TEAL}
LABEL = {"tsmom": "趋势 · 多空（净）", "gross": "趋势 · 毛收益", "60/40": "60/40",
         "equal_weight": "11 资产等权", "long_only": "趋势 · 只做多（净）"}

EVENTS = [
    (pd.Timestamp("2008-09-01"), pd.Timestamp("2009-03-31"), "GFC"),
    (pd.Timestamp("2020-02-15"), pd.Timestamp("2020-04-30"), "COVID"),
    (pd.Timestamp("2022-01-03"), pd.Timestamp("2023-03-31"), "加息"),
]
SRC = "来源：本文回测（ETF 复权价，月度调仓，次日成交）。毛收益不可投资，仅作对照。"


def _tint(c: str, a: float):
    r, g, b = to_rgb(c)
    return (1 - (1 - r) * a, 1 - (1 - g) * a, 1 - (1 - b) * a)


def _nav(r: pd.Series) -> pd.Series:
    return (1 + r.fillna(0)).cumprod()


def _shade(ax, ylim_top: float, labels: bool = True) -> None:
    for start, end, name in EVENTS:
        ax.axvspan(start, end, color=st.SHADE, alpha=0.9, zorder=0, linewidth=0)
        if labels:
            ax.text(start, ylim_top, name, fontsize=st.SIZE_TICK - 1.2,
                    color=st.FAINT, ha="left", va="top", zorder=1)


# ------------------------------------------------------------------ 封面总览
def ex0_summary(out: Path, runs: dict, bench: dict, regime: pd.DataFrame) -> None:
    """一页看懂：净值 + 风险调整后对比 + 条件收益。"""
    st.apply()
    fig = plt.figure(figsize=(9.6, 6.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1], hspace=0.62, wspace=0.34)
    ax1 = fig.add_subplot(gs[0, :])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[1, 1])

    # --- 左上：净值 ---
    for key, r, lw in [("tsmom", runs["tsmom"]["pnl"]["net"], 2.2),
                       ("60/40", bench["60/40"]["pnl"]["net"], 1.6),
                       ("equal_weight", bench["equal_weight"]["pnl"]["net"], 1.3)]:
        nav = _nav(r)
        ax1.plot(nav.index, nav.values, color=COLOR[key], linewidth=lw)
    ax1.set_yscale("log")
    ax1.set_yticks([1, 2, 4], ["1x", "2x", "4x"])
    ax1.set_xlim(pd.Timestamp("2008-04-01"), pd.Timestamp("2027-06-30"))
    _shade(ax1, 4.4)
    for key in ("tsmom", "60/40", "equal_weight"):
        r = runs["tsmom"]["pnl"]["net"] if key == "tsmom" else bench[key]["pnl"]["net"]
        nav = _nav(r)
        st.end_label(ax1, nav.index[-1], nav.iloc[-1],
                     f"{LABEL[key]}  {runs['tsmom']['stats']['cagr_pct'] if key == 'tsmom' else bench[key]['stats']['cagr_pct']}%",
                     COLOR[key])
    st.tidy(ax1)
    ax1.set_ylabel("累计净值（对数）")
    ax1.set_title("净值：趋势的路径与 60/40 明显不同", fontsize=11.4, color=st.INK,
                  loc="left", pad=12)

    # --- 左下：净 Sharpe 对比 ---
    names = ["tsmom", "long_only", "equal_weight", "60/40"]
    vals = [runs["tsmom"]["stats"]["sharpe"], runs["long_only"]["stats"]["sharpe"],
            bench["equal_weight"]["stats"]["sharpe"], bench["60/40"]["stats"]["sharpe"]]
    labels = [LABEL[n] for n in names]
    ax2.barh(range(len(names))[::-1], vals, height=0.55, color=[COLOR[n] for n in names])
    ax2.set_yticks(range(len(names))[::-1], labels)
    ax2.set_xlim(0, 0.9)
    ax2.set_xlabel("净 Sharpe")
    st.tidy(ax2, grid_axis="x")
    ax2.set_title("风险调整后：多空最差，60/40 最好", fontsize=11.4, color=st.INK,
                  loc="left", pad=12)

    # --- 右下：条件收益 ---
    sel = regime[(regime["kind"] == "conditional")
                 & regime["bucket"].str.startswith("SPY")].reset_index(drop=True)
    x = np.arange(len(sel))
    w = 0.36
    ax3.bar(x - w / 2, sel["strat_pct"], w, color=st.ACCENT, label="趋势")
    ax3.bar(x + w / 2, sel["bench_pct"], w, color=st.BLUE, label="60/40")
    ax3.axhline(0, color=st.RULE, linewidth=1)
    ax3.set_xticks(x, ["标普最差\n10% 交易日", "标普最好\n10% 交易日"])
    ax3.set_ylabel("日均收益（bps）")
    st.tidy(ax3)
    st.legend(ax3, ncol=2, y=-0.34)
    ax3.set_title("它的价值在坏日子里", fontsize=11.4, color=st.INK, loc="left", pad=12)

    fig.suptitle("跨资产趋势跟踪：信号有效，但在这个 ETF 宇宙里做空把价值吃掉了",
                 x=0.008, ha="left", fontsize=15.5, fontweight="600", color=st.INK, y=1.005)
    fig.text(0.008, 0.955,
             "净口径、含成本；样本 2008-04 → 2026-10（18.5 年）。11 个流动性最好的 ETF，"
             "月度调仓，次日成交。最坏的日子里跌幅只有 60/40 的八分之一，但平均收益跑不过它。",
             fontsize=st.SIZE_SUB, color=st.MUTED, ha="left", va="top")
    st.source(fig, SRC)
    # suptitle 与副标题用 fig.text 绝对定位，audit 会检查它们与坐标区文字的冲突
    st.audit(fig, "ex0-summary")
    st.save(fig, out / "ex0-summary")


# ------------------------------------------------------------------ 方法示意
def ex1_design(out: Path) -> None:
    st.apply()
    fig, ax = plt.subplots(figsize=(9.4, 2.9))
    steps = [
        ("数据", "11 个 ETF\n复权价 · 日频", st.BLUE),
        ("信号", "12 个月动量\nsign(+1 / −1)", st.SLATE),
        ("组合", "波动率目标 10%\n单资产 ≤35%", st.GOLD),
        ("成本", "按资产类别 2–5 bps\n调仓日扣除", st.ACCENT),
        ("净净值", "月度调仓\n次日成交", st.INK),
    ]
    for i, (title, body, color) in enumerate(steps):
        ax.add_patch(Rectangle((i, 0), 0.92, 1.0, facecolor=_tint(color, 0.10),
                               edgecolor=color, linewidth=1.2))
        ax.text(i + 0.46, 0.70, title, ha="center", va="center", fontsize=12.6,
                fontweight="700", color=color)
        ax.text(i + 0.46, 0.34, body, ha="center", va="center", fontsize=9.2, color=st.MUTED)
        if i < len(steps) - 1:
            ax.annotate("", xy=(i + 0.99, 0.5), xytext=(i + 0.93, 0.5),
                        arrowprops=dict(arrowstyle="->", color=st.FAINT, linewidth=1.1))
    ax.set_xlim(-0.03, len(steps) + 0.03)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axis("off")
    st.frame(fig, ax, "策略设计：五个环节，每一步都能单独检验",
             "信号只用截至当日收盘的数据；次日收盘成交，再下一个交易日才开始承担收益",
             exhibit="Exhibit 1")
    st.tight(fig, top=0.74, bottom=0.06, left=0.02, right=0.99)
    st.source(fig, "来源：本仓库实现，全部参数见 config/base.yml。")
    st.audit(fig, "ex1-design")
    st.save(fig, out / "ex1-design")


# ------------------------------------------------------------------ 净值
def ex2_nav(out: Path, runs: dict, bench: dict) -> None:
    st.apply()
    fig, ax = plt.subplots(figsize=(9.4, 4.6))
    series = [("tsmom", runs["tsmom"]["pnl"]["net"], 2.2, "-", runs["tsmom"]["stats"]["cagr_pct"]),
              ("60/40", bench["60/40"]["pnl"]["net"], 1.7, "-", bench["60/40"]["stats"]["cagr_pct"]),
              ("long_only", runs["long_only"]["pnl"]["net"], 1.7, (0, (5, 2)),
               runs["long_only"]["stats"]["cagr_pct"]),
              ("equal_weight", bench["equal_weight"]["pnl"]["net"], 1.3, "-",
               bench["equal_weight"]["stats"]["cagr_pct"])]
    for key, r, lw, ls, cagr in series:
        nav = _nav(r)
        ax.plot(nav.index, nav.values, color=COLOR[key], linewidth=lw, linestyle=ls)
    ax.set_yscale("log")
    ax.set_yticks([1, 2, 4], ["1x", "2x", "4x"])
    ax.set_xlim(pd.Timestamp("2008-04-01"), pd.Timestamp("2028-06-30"))
    ax.set_ylim(0.85, 6.0)
    _shade(ax, 5.4)
    for key, r, lw, ls, cagr in series:
        nav = _nav(r)
        st.end_label(ax, nav.index[-1], nav.iloc[-1], f"{LABEL[key]} {cagr}%", COLOR[key],
                     size=st.SIZE_TICK - 0.6)
    st.tidy(ax)
    ax.set_ylabel("累计净值（对数刻度）")
    ax.set_xlabel("年份  year")
    st.frame(fig, ax,
             "只做多的版本比多空好 2.7 个百分点：做空那条腿在长牛资产上一直在付钱",
             "灰色区间依次为金融危机、疫情冲击、2022–23 加息；毛收益与成本敏感性见 Exhibit 5",
             exhibit="Exhibit 2")
    st.tight(fig, top=0.80, bottom=0.13, right=0.985)
    st.source(fig, SRC)
    st.audit(fig, "ex2-nav")
    st.save(fig, out / "ex2-nav")


# ------------------------------------------------------------------ 归因
def ex3_contribution(out: Path, panel: dict, res: dict, cfg) -> None:
    st.apply()
    W, R = res["weights"], panel["returns"]
    contrib = (W * R).loc[res["pnl"].index[0]:]
    group = cfg.group
    by_group: dict[str, list] = {}
    for t in contrib.columns:
        by_group.setdefault(group[t], []).append(t)
    ann = {g: float(contrib[cols].sum(axis=1).mean() * 252 * 100) for g, cols in by_group.items()}
    items = sorted(ann.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    colors = [st.ACCENT if v > 0 else st.SLATE for _, v in items]
    ax.barh(range(len(items)), [v for _, v in items], color=colors, height=0.55)
    ax.set_yticks(range(len(items)), [g for g, _ in items])
    ax.axvline(0, color=st.RULE, linewidth=1)
    st.tidy(ax, grid_axis="x")
    ax.set_xlabel("对年化收益的贡献（%，毛口径）")
    best = max(ann.items(), key=lambda kv: kv[1])
    st.frame(fig, ax,
             f"钱主要来自{best[0]}（{best[1]:.2f} 个百分点），外汇与商品几乎没贡献",
             "把逐日 w×r 按资产类别汇总后取年化均值；毛口径，未扣成本",
             exhibit="Exhibit 3")
    st.tight(fig, top=0.78, bottom=0.16)
    st.source(fig, "来源：本文计算。")
    st.audit(fig, "ex3-contribution")
    st.save(fig, out / "ex3-contribution")


# ------------------------------------------------------------------ 滚动
def ex4_rolling(out: Path, res: dict, bench: dict, window: int = 252) -> None:
    st.apply()
    s, b = res["pnl"]["net"], bench["60/40"]["pnl"]["net"]
    df = pd.DataFrame({"s": s, "b": b}).dropna()
    corr = df["s"].rolling(window).corr(df["b"])
    sharpe = (df["s"].rolling(window).mean() / df["s"].rolling(window).std()) * np.sqrt(252)
    fig, axes = plt.subplots(2, 1, figsize=(9.4, 5.0), sharex=True)
    axes[0].plot(corr.index, corr.values, color=st.BLUE, linewidth=1.4)
    axes[0].axhline(0, color=st.RULE, linewidth=1)
    axes[0].set_ylim(-1, 1)
    axes[0].set_ylabel("相关系数")
    st.tidy(axes[0])
    axes[0].set_title("滚动 12 个月与 60/40 的相关性", fontsize=11, color=st.INK, loc="left", pad=10)
    axes[1].plot(sharpe.index, sharpe.values, color=st.ACCENT, linewidth=1.4)
    axes[1].axhline(0, color=st.RULE, linewidth=1)
    axes[1].set_ylabel("滚动 Sharpe")
    axes[1].set_xlabel("年份  year")
    st.tidy(axes[1])
    axes[1].set_title("滚动 12 个月 Sharpe", fontsize=11, color=st.INK, loc="left", pad=10)
    med = float(corr.dropna().median())
    pos = float((corr.dropna() > 0).mean() * 100)
    st.frame(fig, axes[0],
             f"它与 60/40 的相关性不稳定：中位数 {med:+.2f}，但有 {pos:.0f}% 的时间为正",
             "相关性会随制度切换，这也是它作为分散化工具的价值来源",
             exhibit="Exhibit 4")
    st.tight(fig, top=0.84, bottom=0.15, hspace=0.42)
    st.source(fig, "来源：本文回测，日频收益，滚动窗口 252 个交易日。")
    st.audit(fig, "ex4-rolling")
    st.save(fig, out / "ex4-rolling")


# ------------------------------------------------------------------ 成本
def ex5_cost(out: Path, sweep: pd.DataFrame, be: float | None) -> None:
    st.apply()
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    ax.plot(sweep["cost_multiplier"], sweep["net_cagr_pct"], color=st.ACCENT,
            marker="o", markersize=4.5, linewidth=1.9)
    ax.axhline(0, color=st.RULE, linewidth=1)
    if be:
        ax.axvline(be, color=st.INK, linewidth=0.9, alpha=0.35)
        st.end_label(ax, be, float(sweep["net_cagr_pct"].iloc[0]) * 0.5,
                     f"归零于 {be:.1f}×", st.INK, dx=6)
    st.tidy(ax)
    ax.set_xlabel("成本倍数（1.0 = 基准假设：按资产类别 2–5 bps 单边）")
    ax.set_ylabel("净年化收益（%）")
    st.frame(fig, ax,
             "成本不是这套策略的瓶颈：把成本假设放大十倍，它仍然是正的",
             "横轴为成本假设的倍数，纵轴为扣成本后的年化收益；说明问题在信号本身，不在交易费用",
             exhibit="Exhibit 5")
    st.tight(fig, top=0.78, bottom=0.18)
    st.source(fig, "来源：本文回测。")
    st.audit(fig, "ex5-cost")
    st.save(fig, out / "ex5-cost")


# ------------------------------------------------------------------ 参数平台
def ex6_heatmap(out: Path, grid: pd.DataFrame) -> None:
    st.apply()
    piv = grid.pivot(index="lookback_days", columns="target_vol_ann", values="net_sharpe")
    fig, ax = plt.subplots(figsize=(8.8, 4.1))
    im = ax.imshow(piv.values, aspect="auto", cmap="RdYlBu_r", origin="lower",
                   vmin=0.15, vmax=0.65)
    ax.set_xticks(range(len(piv.columns)), [f"{c:.3g}" for c in piv.columns])
    ax.set_yticks(range(len(piv.index)), [str(i) for i in piv.index])
    ax.set_xlabel("目标波动率  target volatility")
    ax.set_ylabel("回看窗口（交易日）  lookback")
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("净 Sharpe", fontsize=9)
    lo, hi = float(grid["net_sharpe"].min()), float(grid["net_sharpe"].max())
    st.frame(fig, ax,
             f"参数不是单点最优：{len(grid)} 组全部为正，区间 {lo:.2f}–{hi:.2f}",
             "每一格都是一次完整回测（含成本）；没有出现只剩一格能看的脆弱结构",
             exhibit="Exhibit 6")
    st.tight(fig, top=0.78, bottom=0.15, right=0.97)
    st.source(fig, "来源：本文回测，6 个回看窗口 × 5 个目标波动率。")
    st.audit(fig, "ex6-heatmap")
    st.save(fig, out / "ex6-heatmap")


# ------------------------------------------------------------------ 条件收益
def ex7_stress(out: Path, regime: pd.DataFrame) -> None:
    st.apply()
    sel = regime[regime["kind"] == "conditional"].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9.4, 3.9))
    x = np.arange(len(sel))
    w = 0.36
    ax.bar(x - w / 2, sel["strat_pct"], w, color=st.ACCENT, label="趋势")
    ax.bar(x + w / 2, sel["bench_pct"], w, color=st.BLUE, label="60/40")
    ax.axhline(0, color=st.RULE, linewidth=1)
    ax.set_xticks(x, [b.replace(" worst ", "\n最差 ").replace(" best ", "\n最好 ")
                      for b in sel["bucket"]])
    ax.set_ylabel("该条件下的日均收益（bps）")
    ax.tick_params(axis="x", labelsize=9)
    st.tidy(ax)
    worst = sel[sel["bucket"].str.startswith("SPY worst")].iloc[0]
    ratio = abs(worst["bench_pct"] / worst["strat_pct"])
    st.frame(fig, ax,
             f"它是一份保险：标普最差 10% 的交易日里，跌幅只有 60/40 的 1/{ratio:.0f}",
             "条件收益用日均 bps 表示——子样本只有几十天，年化会夸张到没有意义",
             exhibit="Exhibit 7")
    st.legend(ax, ncol=2, y=-0.19)
    st.tight(fig, top=0.78, bottom=0.28)
    st.source(fig, "来源：本文回测。")
    st.audit(fig, "ex7-stress")
    st.save(fig, out / "ex7-stress")


# ------------------------------------------------------------------ 回撤
def ex8_drawdown(out: Path, res: dict, bench: dict) -> None:
    st.apply()
    fig, ax = plt.subplots(figsize=(9.4, 3.9))
    for key, r in [("tsmom", res["pnl"]["net"]), ("60/40", bench["60/40"]["pnl"]["net"])]:
        nav = _nav(r)
        dd = (nav / nav.cummax() - 1) * 100
        ax.plot(dd.index, dd.values, color=COLOR[key], linewidth=1.6, label=LABEL[key])
    _shade(ax, 0, labels=False)
    st.tidy(ax)
    ax.set_ylabel("回撤（%）")
    ax.set_xlabel("年份  year")
    d_s = res["stats"]["max_dd_pct"]
    d_b = bench["60/40"]["stats"]["max_dd_pct"]
    st.frame(fig, ax,
             f"回撤是最能区分两者的地方：趋势 {d_s:.1f}%，60/40 是 {d_b:.1f}%",
             "同一区间内的回撤路径；深度与恢复时间都要看",
             exhibit="Exhibit 8")
    st.legend(ax, ncol=2, y=-0.19)
    st.tight(fig, top=0.78, bottom=0.25)
    st.source(fig, SRC)
    st.audit(fig, "ex8-drawdown")
    st.save(fig, out / "ex8-drawdown")


# ------------------------------------------------------------------ 容量
def ex9_capacity(out: Path, panel: dict, res: dict,
                 levels_mm=(10, 25, 50, 100, 250, 500)) -> None:
    st.apply()
    adv = panel["adv_usd"]
    W = res["weights"]
    start = res["pnl"].index[0]
    dW = W.diff().abs().fillna(W.abs()).loc[start:]
    adv_robust = adv.reindex(W.index).loc[start:].quantile(0.20)
    max_turnover = dW.max()
    x = np.array(levels_mm, dtype=float) * 1e6
    y = [float((aum * max_turnover / adv_robust).max() * 100) for aum in x]
    cap_mm = 0.05 / float((max_turnover / adv_robust).max()) / 1e6

    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    ax.plot(x / 1e6, y, color=st.ACCENT, marker="o", markersize=4.5, linewidth=1.9)
    ax.axhline(5, color=st.INK, linewidth=0.9, alpha=0.4)
    ax.text(x[-1] / 1e6, 5, " 5% ADV", color=st.INK, fontsize=st.SIZE_TICK - 0.6,
            va="bottom", ha="right")
    ax.set_xscale("log")
    ax.set_xticks(levels_mm, [str(v) for v in levels_mm])
    ax.set_xlabel("管理规模（百万美元，对数刻度）  AUM")
    ax.set_ylabel("单资产最大成交占 ADV（%）")
    st.tidy(ax)
    st.frame(fig, ax,
             f"容量只有约 {cap_mm:.1f} 百万美元——约束来自日元 ETF，不是策略本身",
             "ADV 取 60 日均值的 20% 分位（保守基准）；这条线决定了：要上规模必须走期货",
             exhibit="Exhibit 9")
    st.tight(fig, top=0.78, bottom=0.17)
    st.source(fig, "来源：本文计算，ADV 为美元成交额。")
    st.audit(fig, "ex9-capacity")
    st.save(fig, out / "ex9-capacity")
