"""图表规范 v2 —— 机构研究部（chart pack）标准。

参考的是大型资管研究部门（BlackRock Investment Institute 一类）公开发布的
chart pack 惯例：

  1. **一句话标题就是结论**，不是"图 3"；副标题补充口径。
  2. 每张图有 **Exhibit 编号**，贯穿全篇。
  3. 调色板克制：近黑的墨色 + 一个强调色，其余为低饱和辅助色。
  4. **事件区间用底色阴影**（危机、加息周期），时间轴上直接可读。
  5. 曲线尽量**端点直接标注**，而不是靠图例来回找。
  6. 左下角永远有 **来源行**；口径与假设写在副标题里。
  7. 字体层级固定：15 / 10 / 8.5 pt，全篇一致。

同时保留工程约束：透明背景、无边框、图例放在坐标区下方、
`audit()` 用包围盒两两求交做重叠自检（看不到渲染结果时的替代检查）。
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

# ------------------------------------------------------------------ 色板
INK = "#14171A"          # 近黑：标题与轴线
MUTED = "#6B7280"        # 次级文字
FAINT = "#9AA1A9"
GRID = "#E8EAED"
RULE = "#D4D8DD"
ACCENT = "#C8102E"       # 强调色：主策略
BLUE = "#1F4E79"         # 对照：60/40
TEAL = "#0E7C7B"         # 只做多
GOLD = "#B8860B"         # 等权
SLATE = "#8A94A6"        # 毛收益 / 背景
SHADE = "#F2F3F5"        # 事件阴影

FONT_STACK = ["Noto Sans SC", "Microsoft YaHei", "Segoe UI", "Aptos", "DejaVu Sans"]
HALO = [pe.withStroke(linewidth=2.6, foreground="white")]

SIZE_TITLE = 14.5
SIZE_SUB = 9.8
SIZE_SOURCE = 7.8
SIZE_LABEL = 10.0
SIZE_TICK = 9.2


def apply() -> None:
    plt.rcParams.update({
        "figure.dpi": 160, "savefig.dpi": 300, "savefig.transparent": True,
        "font.family": "sans-serif", "font.sans-serif": FONT_STACK,
        "axes.unicode_minus": False,
        "axes.edgecolor": RULE, "axes.linewidth": 0.9,
        "axes.labelcolor": MUTED, "axes.labelsize": SIZE_LABEL,
        "axes.titlesize": SIZE_TITLE, "axes.titleweight": "600",
        "axes.titlelocation": "left", "axes.titlepad": 30,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "grid.linestyle": (0, (1, 3)),
        "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": SIZE_TICK, "ytick.labelsize": SIZE_TICK,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "legend.frameon": False, "legend.fontsize": SIZE_TICK - 0.2,
        "lines.linewidth": 2.0, "path.simplify": False,
        "svg.hashsalt": "catrend",
    })


def tidy(ax, *, grid_axis: str = "y", keep_left: bool = False) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_visible(keep_left)
    ax.spines["bottom"].set_color(RULE)
    if grid_axis == "none":
        ax.grid(False)
    else:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, linestyle=(0, (1, 3)))
        ax.grid(axis=("x" if grid_axis == "y" else "y"), visible=False)
    ax.set_axisbelow(True)


def frame(fig, ax, headline: str, subhead: str | None = None, *,
          exhibit: str | None = None, pad: float = 34) -> None:
    """标题=结论；副标题=口径。exhibit 给 "Exhibit 3" 这类编号。"""
    text = f"{exhibit} | {headline}" if exhibit else headline
    ax.set_title(text, loc="left", fontsize=SIZE_TITLE, fontweight="600",
                 color=INK, pad=pad)
    parts = [p for p in [subhead] if p]
    if parts:
        h = max(ax.get_position().height * fig.get_figheight() * 72.0, 1.0)
        ax.text(0.0, 1.0 + 17.5 / h, "   ".join(parts), transform=ax.transAxes,
                fontsize=SIZE_SUB, color=MUTED, va="bottom", ha="left")


def source(fig, text: str, *, x: float = 0.008, y: float = 0.012) -> None:
    fig.text(x, y, text, fontsize=SIZE_SOURCE, color=FAINT, ha="left", va="bottom")


def legend(ax, *, ncol: int = 2, y: float = -0.20):
    ax.legend(loc="upper left", bbox_to_anchor=(0, y), ncol=ncol, frameon=False,
              handlelength=1.5, columnspacing=1.6, borderaxespad=0)


def end_label(ax, x, y, text: str, color: str, *, dx: float = 6, dy: float = 0,
              size: float | None = None) -> None:
    """曲线端点直接标注：机构 chart pack 的标准做法，省掉来回找图例。"""
    ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points",
                color=color, fontsize=size or SIZE_TICK, fontweight="600",
                va="center", ha="left", path_effects=HALO)


def shade_events(ax, events: list[tuple], *, alpha: float = 0.9) -> None:
    """给危机 / 加息这类区间铺底色。events 里每一项是 (start, end, label|None)。"""
    for start, end, label in events:
        ax.axvspan(start, end, color=SHADE, alpha=alpha, zorder=0, linewidth=0)
        if label:
            ax.text(start, ax.get_ylim()[1], f" {label}", fontsize=SIZE_TICK - 1.0,
                    color=FAINT, ha="left", va="top", zorder=1)


def save(fig, path) -> None:
    for ext in ("svg", "png"):
        fig.savefig(str(path) + "." + ext, bbox_inches="tight", transparent=True,
                    metadata={"Date": None})
    plt.close(fig)


def tight(fig, *, top=0.84, bottom=0.13, left=0.085, right=0.985, hspace=None, wspace=None):
    kw = {"top": top, "bottom": bottom, "left": left, "right": right}
    if hspace is not None:
        kw["hspace"] = hspace
    if wspace is not None:
        kw["wspace"] = wspace
    fig.subplots_adjust(**kw)


def audit(fig, name: str, *, verbose: bool = True) -> list:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts, legends = [], []

    def add(a, prefix=""):
        s = (a.get_text() or "").strip()
        if not s:
            return
        try:
            texts.append((prefix + s[:18], a.get_window_extent(renderer)))
        except Exception:
            pass

    for ax in fig.axes:
        for t in list(ax.texts) + list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
            add(t)
        add(ax.xaxis.label, "轴:")
        add(ax.yaxis.label, "轴:")
        add(ax.title, "题:")
        leg = ax.get_legend()
        if leg is not None:
            legends.append(("图例", leg.get_window_extent(renderer)))
    for t in fig.texts:
        add(t, "说明:")

    def hit(a, b):
        if not a.overlaps(b):
            return False
        inter = (min(a.x1, b.x1) - max(a.x0, b.x0)) * (min(a.y1, b.y1) - max(a.y0, b.y0))
        return inter > 14

    bad = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if hit(texts[i][1], texts[j][1]):
                bad.append((texts[i][0], texts[j][0]))
    for lname, lb in legends:
        for s, tb in texts:
            if hit(lb, tb):
                bad.append((f"{lname}压住", s))
    if verbose:
        print(f"  {'⚠' if bad else '✓'} {name}: "
              + (f"{len(bad)} 处重叠 → {bad[:4]}" if bad else "无文字重叠"))
    return bad
