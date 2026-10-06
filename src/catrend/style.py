"""图表规范（自包含，不依赖其它仓库）。

规则：数据图图内不放说明文字，解释写在图外的 caption 里；图例放坐标区下方；
透明背景；每张图一个结论式标题。audit() 用包围盒两两求交做重叠自检——
我看不到渲染结果，所以用几何检查代替肉眼。
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK = "#111827"
MUTED = "#6B7280"
GRID = "#E9EDF2"
RULE = "#D5DAE1"
PRIMARY = "#B23A1C"
SECOND = "#1F4E79"
TERTIARY = "#8A94A6"
GOLD = "#C9922E"
TINT = "#F7E6E0"

FONT_STACK = ["Noto Sans SC", "Microsoft YaHei", "Segoe UI", "Aptos", "DejaVu Sans"]


def apply() -> None:
    plt.rcParams.update({
        "figure.dpi": 160, "savefig.dpi": 300, "savefig.transparent": True,
        "font.family": "sans-serif", "font.sans-serif": FONT_STACK,
        "axes.unicode_minus": False, "axes.edgecolor": RULE, "axes.linewidth": 0.9,
        "axes.labelcolor": MUTED, "axes.labelsize": 10, "axes.titlesize": 12.4,
        "axes.titleweight": "600", "axes.titlelocation": "left", "axes.titlepad": 26,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "grid.linestyle": (0, (3, 4)), "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": 9.6, "ytick.labelsize": 9.6,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "legend.frameon": False, "legend.fontsize": 9.6, "lines.linewidth": 2.0,
        "path.simplify": False, "svg.hashsalt": "catrend",
    })


def tidy(ax, *, grid_axis: str = "y") -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    if grid_axis == "none":
        ax.grid(False)
    else:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, linestyle=(0, (3, 4)))
        ax.grid(axis=("x" if grid_axis == "y" else "y"), visible=False)
    ax.set_axisbelow(True)


def frame(fig, ax, headline: str, subtitle: str | None = None, *, pad: float = 34) -> None:
    ax.set_title(headline, loc="left", fontsize=12.4, fontweight="600", color=INK, pad=pad)
    if subtitle:
        h = max(ax.get_position().height * fig.get_figheight() * 72.0, 1.0)
        ax.text(0.0, 1.0 + 17.0 / h, subtitle, transform=ax.transAxes,
                fontsize=9.6, color=MUTED, va="bottom", ha="left")


def tight(fig, *, top=0.84, bottom=0.13, left=0.085, right=0.985, hspace=None, wspace=None):
    kw = {"top": top, "bottom": bottom, "left": left, "right": right}
    if hspace is not None:
        kw["hspace"] = hspace
    if wspace is not None:
        kw["wspace"] = wspace
    fig.subplots_adjust(**kw)


def source(fig, text: str, *, x: float = 0.008, y: float = 0.012) -> None:
    fig.text(x, y, text, fontsize=7.8, color=MUTED, ha="left", va="bottom")


def legend(ax, *, ncol: int = 2, y: float = -0.20):
    ax.legend(loc="upper left", bbox_to_anchor=(0, y), ncol=ncol, frameon=False,
              handlelength=1.6, columnspacing=1.6, borderaxespad=0)


def save(fig, path) -> None:
    for ext in ("svg", "png"):
        fig.savefig(str(path) + "." + ext, bbox_inches="tight", transparent=True,
                    metadata={"Date": None})
    plt.close(fig)


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
