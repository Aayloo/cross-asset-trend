"""入口：一条命令复现全部结果。

    python run.py --config config/base.yml --out reports/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from catrend import config as cfg_mod  # noqa: E402
from catrend import pipeline  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-asset trend following research run")
    ap.add_argument("--config", default="config/base.yml")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--force-data", action="store_true", help="重新下载原始数据")
    ap.add_argument("--skip-figures", action="store_true")
    args = ap.parse_args()

    cfg = cfg_mod.load(ROOT / args.config if not Path(args.config).is_absolute() else args.config)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out

    result = pipeline.run_all(cfg, out, force_data=args.force_data,
                              skip_figures=args.skip_figures)

    s = result["summary"]
    cols = ["name", "start", "end", "years", "cagr_pct", "vol_pct", "sharpe",
            "max_dd_pct", "turnover_two_way_pa", "avg_gross_exposure"]
    print("\n=== 结果汇总（净口径，含成本）===")
    print(s[[c for c in cols if c in s.columns]].to_string(index=False))
    print(f"\nbreak-even 成本倍数: {result['manifest']['break_even_cost_multiplier']}")
    print(f"容量（5% ADV 限制）: {result['capacity'].get('capacity_usd_mm')} 百万美元，"
          f"约束资产 {result['capacity'].get('binding_asset')}")
    print(f"\nmanifest: {out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
