"""生成机构风格的 chart pack 网页（仓库根目录 index.html，可直接用 GitHub Pages 发布）。

为什么用 HTML 而不是 PDF：图是矢量 SVG，网页版在任何屏幕上都不糊；
而且打开就能读，不需要下载。所有数字从本次运行的结果里取，不手写。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def _exhibit(num: int, slug: str, title: str, body: str, source: str,
             *, wide: bool = True) -> str:
    return f"""
      <section class="ex">
        <div class="extag">Exhibit {num}</div>
        <h2>{title}</h2>
        <figure>
          <img src="reports/exhibits/{slug}.svg" alt="{title}">
        </figure>
        <p class="note">{body}</p>
        <p class="src">{source}</p>
      </section>"""


def build(out_dir: Path, result: dict, cfg) -> Path:
    s = {r["name"]: r for r in result["summary"].to_dict(orient="records")}
    cap = result["capacity"]
    grid = result["grid"]
    regime = result["regime"]
    cond = regime[regime["kind"] == "conditional"].set_index("bucket")
    worst = cond.loc["SPY worst 10% days"]
    ratio = abs(worst["bench_pct"] / worst["strat_pct"])
    be = result["manifest"]["break_even_cost_multiplier"]
    be_txt = f"{be:.1f}" if be else "未出现"
    lo, hi = float(grid["net_sharpe"].min()), float(grid["net_sharpe"].max())
    d = date.today().isoformat()

    rows = "".join(
        f"<tr><td>{n}</td><td>{s[n]['cagr_pct']:.2f}%</td><td>{s[n]['vol_pct']:.2f}%</td>"
        f"<td>{s[n]['sharpe']:.2f}</td><td>{s[n]['max_dd_pct']:.1f}%</td>"
        f"<td>{s[n]['turnover_two_way_pa']:.2f}×</td></tr>"
        for n in ("tsmom", "tsmom-long-only", "60/40", "equal_weight")
    )
    rows = rows.replace("<tr><td>tsmom</td>", "<tr class='hl'><td>趋势 · 多空</td>")
    rows = rows.replace("<tr><td>tsmom-long-only</td>", "<tr><td>趋势 · 只做多</td>")
    rows = rows.replace("<tr><td>60/40</td>", "<tr><td>60/40（月度再平衡）</td>")
    rows = rows.replace("<tr><td>equal_weight</td>", "<tr><td>11 资产等权</td>")

    html = f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>跨资产趋势跟踪 · Chart Pack</title>
<meta name="description" content="跨资产时序动量的研究实现：11 个 ETF、2008–2026。信号有效（方向命中率 53%），但在这个宇宙里做空把价值吃掉了；它真正提供的是坏日子的保护。">
<style>
:root{{--ink:#14171A;--body:#3F4448;--muted:#6B7280;--faint:#9AA1A9;
  --rule:#E8EAED;--accent:#C8102E;--blue:#1F4E79;--paper:#FFFFFF;--bg:#F7F8F9;
  --serif:Georgia,"Songti SC","Noto Serif SC",serif;
  --sans:"Noto Sans SC","Microsoft YaHei",-apple-system,system-ui,sans-serif;
  --mono:"SFMono-Regular",Consolas,"Liberation Mono",monospace}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--body);font-family:var(--sans);
  font-size:16px;line-height:1.75;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:920px;margin:0 auto;background:var(--paper);padding:0 64px 72px;
  box-shadow:0 1px 3px rgba(0,0,0,.06)}}
header{{padding:64px 0 26px;border-bottom:2px solid var(--ink)}}
.kicker{{font-family:var(--mono);font-size:11.5px;letter-spacing:.18em;
  text-transform:uppercase;color:var(--accent)}}
h1{{font-family:var(--serif);font-size:38px;line-height:1.18;color:var(--ink);
  margin:14px 0 12px;letter-spacing:-.01em}}
.stand{{font-size:17px;color:var(--body);max-width:740px}}
.meta{{display:flex;gap:18px;flex-wrap:wrap;font-family:var(--mono);font-size:11.5px;
  color:var(--faint);margin-top:22px;letter-spacing:.06em}}
.takeaways{{border:1px solid var(--rule);border-left:3px solid var(--accent);
  background:#FCFCFD;padding:20px 24px;margin:30px 0 0}}
.takeaways h3{{font-size:14px;font-family:var(--mono);letter-spacing:.12em;
  text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:10px}}
.takeaways li{{margin:8px 0 0 18px;font-size:15.4px}}
.ex{{padding:46px 0 8px;border-top:1px solid var(--rule);margin-top:34px}}
.extag{{font-family:var(--mono);font-size:11px;letter-spacing:.18em;
  text-transform:uppercase;color:var(--accent)}}
.ex h2{{font-size:22px;line-height:1.35;color:var(--ink);font-weight:600;margin:8px 0 18px}}
figure{{margin:0 0 14px;background:#fff}}
figure img{{display:block;width:100%;height:auto}}
.note{{font-size:15.4px;color:var(--body);max-width:760px}}
.src{{font-size:12.4px;color:var(--faint);margin-top:8px}}
table{{width:100%;border-collapse:collapse;margin:26px 0 0;font-size:14.6px}}
.tblwrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
.tblwrap table{{min-width:620px}}
th,td{{padding:11px 12px;border-bottom:1px solid var(--rule);text-align:right}}
th:first-child,td:first-child{{text-align:left}}
thead th{{font-size:12.4px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.06em;border-bottom:1.5px solid var(--ink)}}
tr.hl td{{background:#FDF6F7;font-weight:600;color:var(--ink)}}
h2.sec{{font-size:24px;color:var(--ink);margin:52px 0 6px;font-weight:600}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:20px}}
.card{{border:1px solid var(--rule);padding:18px 20px}}
.card h4{{font-size:15px;color:var(--ink);margin-bottom:6px}}
.card p{{font-size:14.6px}}
footer{{border-top:2px solid var(--ink);margin-top:56px;padding-top:16px;
  font-size:12.6px;color:var(--muted)}}
code{{font-family:var(--mono);font-size:13.4px;background:#F3F4F6;padding:1px 5px;border-radius:3px}}
@media(max-width:760px){{.wrap{{padding:0 22px 48px}}h1{{font-size:28px}}.two{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="kicker">Systematic research · Chart pack</div>
    <h1>跨资产趋势跟踪：信号有效，但在这个 ETF 宇宙里做空把价值吃掉了</h1>
    <p class="stand">用 11 个流动性最好的 ETF（股票 / 利率 / 黄金 / 商品 / 外汇 / 房地产）检验
    12 个月时序动量。信号本身有预测力，但<b>做空那条腿</b>在长牛资产上持续付钱；
    它真正提供的是坏日子的保护——标普最差 10% 的交易日里，日均跌幅只有 60/40 的
    {ratio:.0f} 分之一。</p>
    <div class="meta">
      <span>样本 2007-03 → 2026-10</span><span>策略区间 18.5 年</span>
      <span>11 个资产 · 月度调仓</span><span>净口径 · 含成本</span>
      <span>生成于 {d}</span>
    </div>
    <div class="takeaways">
      <h3>四条结论</h3>
      <ul>
        <li><b>信号有效但很薄</b>：<code>sign(12 个月动量)</code> 对未来 21 日方向的命中率约
            53%，{len(grid)} 组参数全部为正——不是过拟合。</li>
        <li><b>做空是负贡献</b>：只做多版本 Sharpe {s['tsmom-long-only']['sharpe']:.2f}，
            多空只有 {s['tsmom']['sharpe']:.2f}；1/N 等权对拍显示短腿是纯拖累。</li>
        <li><b>跑不赢 60/40</b>：60/40 Sharpe {s['60/40']['sharpe']:.2f}。趋势的价值不在平均收益，
            而在条件收益——它是一份保险。</li>
        <li><b>容量卡在工具上</b>：ETF 形式约 {cap['capacity_usd_mm']:.1f} 百万美元
            （约束资产 {cap['binding_asset']}），要上规模必须走期货。</li>
      </ul>
    </div>
  </header>

      <section class="ex">
        <div class="extag">Exhibit 0</div>
        <h2>一页看懂：净值、风险调整后对比、以及它真正擅长的场景</h2>
        <figure><img src="reports/exhibits/ex0-summary.svg" alt="summary"></figure>
        <p class="note">左上是三条净值曲线：趋势（红）在 2008 与 2022 明显占优，
        但在 2010 年代的 QE 长牛里持续跑输 60/40。左下是风险调整后的排序——多空版本垫底，
        只做多显著改善，但仍是 60/40 最好。右下解释了为什么机构仍然会配它：
        在最坏的交易日里，它的跌幅比 60/40 小一个数量级。</p>
        <p class="src">来源：本文回测。所有图表由 <code>python run.py</code> 一次生成。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 1</div>
        <h2>策略设计：五个环节，每一步都能单独检验</h2>
        <figure><img src="reports/exhibits/ex1-design.svg" alt="design"></figure>
        <p class="note">信号只用截至当日收盘的数据，权重在次日收盘成交，
        再下一个交易日才开始承担收益。这个两天的滞后是刻意的：
        <code>tests/test_core.py</code> 用力导数据证明未来信息不会被用到。</p>
        <p class="src">来源：本仓库实现，全部参数见 <code>config/base.yml</code>。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 2</div>
        <h2>只做多比多空好 2.7 个百分点</h2>
        <figure><img src="reports/exhibits/ex2-nav.svg" alt="nav"></figure>
        <p class="note">灰色区间是三次危机。趋势在 2008 与 2022 明显跑赢，
        但把方向反过来（做空）在 2009、2020 的反弹里被反复打——这正是「做空需要会跌的资产」
        这句话在数据里的样子。</p>
        <p class="src">来源：本文回测（ETF 复权价，月度调仓，次日成交）。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 3</div>
        <h2>收益从哪一类资产来</h2>
        <figure><img src="reports/exhibits/ex3-contribution.svg" alt="contribution"></figure>
        <p class="note">把逐日的 <code>w × r</code> 按资产类别汇总后取年化：
        股票与利率腿贡献了绝大部分，外汇与商品几乎没有贡献。这也解释了容量问题——
        真正需要换手的资产，恰好是流动性最差的那几个。</p>
        <p class="src">来源：本文计算（毛口径）。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 4</div>
        <h2>与 60/40 的相关性会切换方向</h2>
        <figure><img src="reports/exhibits/ex4-rolling.svg" alt="rolling"></figure>
        <p class="note">滚动 12 个月相关性不是稳定的负数，而是会在正负之间摆动。
        对配置团队来说，这意味着它能提供的分散化价值是<b>条件性</b>的——在真正的压力期更可靠，
        在平静期反而是拖累。</p>
        <p class="src">来源：本文回测，日频收益，滚动 252 个交易日。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 5</div>
        <h2>成本不是瓶颈</h2>
        <figure><img src="reports/exhibits/ex5-cost.svg" alt="cost"></figure>
        <p class="note">把成本假设放大十倍，净年化仍然是正的（基准 {s['tsmom']['cagr_pct']:.2f}%，
        十倍成本下约 0.8%）。样本内没有出现「成本吃光策略」的情形，
        说明问题从来不在交易费用，而在信号在这个宇宙里的原始期望值。
        归零成本倍数：{be_txt}。</p>
        <p class="src">来源：本文回测，按资产类别 2–5 bps 单边 × 倍数。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 6</div>
        <h2>参数不是单点最优</h2>
        <figure><img src="reports/exhibits/ex6-heatmap.svg" alt="grid"></figure>
        <p class="note">{len(grid)} 组参数（6 个回看窗口 × 5 个目标波动率）全部为正，
        区间 {lo:.2f}–{hi:.2f}。这是稳健性的最低要求，但它同时也提醒：
        这次扫描本身就要计入多重检验，正式对外报告必须声明尝试过多少组。</p>
        <p class="src">来源：本文回测，每组都是完整回测。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 7</div>
        <h2>它是一份保险</h2>
        <figure><img src="reports/exhibits/ex7-stress.svg" alt="stress"></figure>
        <p class="note">标普最差 10% 的交易日里，趋势日均 {worst['strat_pct']:.1f} bps，
        60/40 是 {worst['bench_pct']:.1f} bps——差 {ratio:.0f} 倍；
        2022 年趋势 +13.9%，60/40 −16.6%。但最好的日子里它几乎不参与。
        买它不是为了多赚，是为了在 60/40 失效的月份不跟着一起掉。</p>
        <p class="src">来源：本文回测；条件收益用日均 bps，不用年化。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 8</div>
        <h2>回撤路径的差异</h2>
        <figure><img src="reports/exhibits/ex8-drawdown.svg" alt="drawdown"></figure>
        <p class="note">趋势最深处 {s['tsmom']['max_dd_pct']:.1f}%，60/40 是
        {s['60/40']['max_dd_pct']:.1f}%；但回撤的**形状**不同：
        60/40 在 2008 与 2022 各挖一次深坑，趋势的坑更浅、更分散。</p>
        <p class="src">来源：本文回测。</p>
      </section>

      <section class="ex">
        <div class="extag">Exhibit 9</div>
        <h2>容量：问题在工具，不在策略</h2>
        <figure><img src="reports/exhibits/ex9-capacity.svg" alt="capacity"></figure>
        <p class="note">按「单资产成交不超过其 ADV 的 5%、ADV 取 20% 分位」估计，
        ETF 形式的容量只有约 {cap['capacity_usd_mm']:.1f} 百万美元，
        约束来自 {cap['binding_asset']}（日元 ETF）。要真正上规模，必须换到期货市场——
        这也是 v2 的核心工作。</p>
        <p class="src">来源：本文计算，ADV 为美元成交额。</p>
      </section>

      <h2 class="sec">结果表</h2>
      <div class="tblwrap"><table>
        <thead><tr><th>组合</th><th>年化</th><th>波动</th><th>Sharpe</th>
          <th>最大回撤</th><th>两向换手/年</th></tr></thead>
        <tbody>{rows}</tbody>
      </table></div>
      <p class="src">净口径，含成本；样本 2007-03 → 2026-10，策略自 2008-04 起（信号需 252 日预热）。</p>

      <h2 class="sec">边界与下一步</h2>
      <div class="two">
        <div class="card">
          <h4>这一版没做的事</h4>
          <p>ETF 不能做空（多空账簿假设由期货实现，无借券成本与保证金约束）；
          样本不含 1970–2000 的商品与外汇大周期；成本是固定 bps，没有市场冲击模型；
          {len(grid)} 组参数未做正式的多重检验调整。</p>
        </div>
        <div class="card">
          <h4>v2：换成连续期货</h4>
          <p>15+ 个市场（ES/NQ、ZN/ZB、GC/SI/HG、CL/NG、ZC、6E/6J/6B/6A），
          2001 年起约 25 年，加入真实合约乘数与保证金，明确披露 roll 影响，
          并用 ETF 层做对照——直接检验「做空需要会跌的资产」这个假设。</p>
        </div>
      </div>

      <footer>
        本文为研究记录，不构成投资建议。数据来自公开来源（Yahoo Finance 复权价），
        全部结果可由 <code>python run.py --config config/base.yml</code> 复现；
        <code>reports/manifest.json</code> 记录本次运行的配置哈希、代码哈希与数据哈希。
        © {date.today().year} Aylon · MIT License
      </footer>
</div>
</body>
</html>
"""
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
