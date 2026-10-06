"""把数据 → 信号 → 组合 → 回测 → 评估 → 图表串起来，并写 run manifest。

一次运行产出的所有数字都来自同一次执行；manifest 记录 git hash、config hash
与数据文件 hash，任何一处变了都看得出来。
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import data, evaluation, figures, style
from .config import Config


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:12]


def _git_hash(root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def run_all(cfg: Config, out_dir: Path, *, force_data: bool = False,
            skip_figures: bool = False) -> dict:
    out_dir = Path(out_dir)
    ex_dir, res_dir = out_dir / "exhibits", out_dir / "results"
    ex_dir.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 1. 数据 ----------
    data.fetch(cfg, force=force_data)
    prices, volume = data.load_raw(cfg)
    qc = data.validate(prices, volume, cfg)
    (res_dir / "data_quality.json").write_text(
        json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    panel = data.build_panel(cfg)
    data.save_panel(cfg, panel)
    print(f"[data] 共同交易日 {qc['common_start']} → {qc['common_end']}"
          f"（{qc['n_rows_complete']} 天，{len(cfg.tickers)} 个资产）")

    # ---------- 2. 主策略与对照 ----------
    main = evaluation.run(panel, cfg, label="tsmom")
    long_only = evaluation.run(panel, cfg, params={"allow_short": False}, label="tsmom-long-only")
    bench = {
        "60/40": evaluation.run_benchmark(panel, cfg, "60/40"),
        "equal_weight": evaluation.run_benchmark(panel, cfg, "equal_weight"),
    }

    # ---------- 3. 成本、参数、制度、容量 ----------
    sweep = evaluation.cost_sweep(panel, cfg, cfg.get("robustness", "cost_multipliers",
                                                       default=[0.0, 1, 2, 3, 5]))
    be = evaluation.break_even_multiplier(sweep)
    grid = evaluation.param_grid(panel, cfg)
    regime = evaluation.regime_table(panel, main["pnl"], bench["60/40"]["pnl"])
    cap = evaluation.capacity(panel, main)

    # ---------- 4. 落表 ----------
    summary = pd.DataFrame([
        main["stats"], long_only["stats"],
        bench["60/40"]["stats"], bench["equal_weight"]["stats"],
    ])
    summary.to_csv(res_dir / "summary.csv", index=False, encoding="utf-8-sig")
    sweep.to_csv(res_dir / "cost_sweep.csv", index=False, encoding="utf-8-sig")
    grid.to_csv(res_dir / "param_grid.csv", index=False, encoding="utf-8-sig")
    regime.to_csv(res_dir / "regime.csv", index=False, encoding="utf-8-sig")
    (res_dir / "capacity.json").write_text(
        json.dumps(cap, ensure_ascii=False, indent=2), encoding="utf-8")

    navs = pd.DataFrame({
        "tsmom_net": main["pnl"]["net"],
        "tsmom_gross": main["pnl"]["gross"],
        "bench_60_40": bench["60/40"]["pnl"]["net"],
        "bench_equal_weight": bench["equal_weight"]["pnl"]["net"],
    })
    navs.to_csv(res_dir / "daily_returns.csv", encoding="utf-8-sig")
    main["weights"].to_csv(res_dir / "weights_daily.csv", encoding="utf-8-sig")

    # ---------- 5. 图表 ----------
    if not skip_figures:
        style.apply()
        figures.ex1_design(ex_dir)
        figures.ex2_nav(ex_dir, {"tsmom": main, "long_only": long_only}, bench)
        figures.ex3_contribution(ex_dir, panel, main, cfg)
        figures.ex4_rolling(ex_dir, main, bench)
        figures.ex5_cost(ex_dir, sweep, be)
        figures.ex6_heatmap(ex_dir, grid)
        figures.ex7_stress(ex_dir, regime)
        figures.ex8_drawdown(ex_dir, main, bench)
        figures.ex9_capacity(ex_dir, panel, main)

    # ---------- 6. manifest ----------
    manifest = {
        "project": cfg.get("project"),
        "version": cfg.get("version"),
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "config_path": str(cfg.path),
        "config_hash": cfg.hash(),
        "git_hash": _git_hash(cfg.root),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "data_file_hash": _sha(cfg.path_of("data", "raw_dir") / "prices.parquet"),
        "sample": {"start": qc["common_start"], "end": qc["common_end"],
                   "n_days": qc["n_rows_complete"], "n_assets": len(cfg.tickers)},
        "break_even_cost_multiplier": be,
        "capacity": cap,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"summary": summary, "sweep": sweep, "grid": grid, "regime": regime,
            "capacity": cap, "manifest": manifest, "qc": qc,
            "main": main, "bench": bench}
