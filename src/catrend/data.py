"""数据层：抓取、缓存、校验。

原则：
  1. 原始数据只落盘一次（raw parquet + 抓取元信息），之后所有计算读本地文件，
     保证「同样的输入 → 同样的输出」。
  2. 数据质量先出一份体检报告，再谈信号；缺失和异常不静默丢弃。
  3. 用 ETF 复权价（含分红）而不是连续期货：避免 roll 价差污染收益。
     代价是样本从 2007 年起、且无法做空——这两点写进报告，不藏起来。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config


# --------------------------------------------------------------------- 抓取
def fetch(cfg: Config, *, force: bool = False) -> Path:
    """下载原始数据到 data/raw/。已存在且非 force 时直接返回。"""
    raw_dir = cfg.path_of("data", "raw_dir")
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = raw_dir / "prices.parquet"
    meta_path = raw_dir / "fetch_meta.json"
    if out.exists() and not force:
        return out

    import yfinance as yf

    cache = cfg.path_of("data", "cache_dir")
    cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache))

    end = cfg.get("data", "end") or date.today().isoformat()
    start = cfg.get("data", "start")
    tickers = cfg.tickers
    print(f"[data] 下载 {len(tickers)} 个标的：{start} → {end}")
    raw = yf.download(tickers, start=start, end=end, progress=False,
                      auto_adjust=True, threads=False)
    if raw is None or len(raw) == 0:
        raise RuntimeError("下载为空：检查网络或 ticker")

    close = raw["Close"][tickers].copy()
    volume = raw["Volume"][tickers].copy() if "Volume" in raw else None
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    close = close.sort_index()
    close.to_parquet(raw_dir / "prices.parquet")
    if volume is not None:
        volume.index = close.index
        volume.to_parquet(raw_dir / "volume.parquet")

    meta = {
        "source": "yahoo finance (yfinance)",
        "auto_adjust": True,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "requested_start": start,
        "requested_end": end,
        "tickers": tickers,
        "rows": int(len(close)),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[data] 已写入 {out}（{len(close)} 行 × {len(tickers)} 列）")
    return out


def load_raw(cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    raw_dir = cfg.path_of("data", "raw_dir")
    prices = pd.read_parquet(raw_dir / "prices.parquet")
    vol_path = raw_dir / "volume.parquet"
    volume = pd.read_parquet(vol_path) if vol_path.exists() else None
    missing = [t for t in cfg.tickers if t not in prices.columns]
    if missing:
        raise KeyError(f"原始数据缺少 {missing}，先跑 fetch()")
    return prices[cfg.tickers], (volume[cfg.tickers] if volume is not None else None)


# --------------------------------------------------------------------- 校验
def validate(prices: pd.DataFrame, volume: pd.DataFrame | None, cfg: Config) -> dict:
    """数据体检。返回结构化报告，同时写 CSV 供人看。"""
    rets = prices.pct_change()
    rows = []
    for t in prices.columns:
        s = prices[t].dropna()
        r = rets[t].dropna()
        sigma = float(r.std())
        rows.append({
            "ticker": t,
            "first": s.index[0].date().isoformat() if len(s) else None,
            "last": s.index[-1].date().isoformat() if len(s) else None,
            "n_obs": int(len(s)),
            "n_missing_vs_calendar": int(prices[t].isna().sum()),
            "ann_vol_pct": round(sigma * np.sqrt(252) * 100, 2),
            "max_abs_daily_pct": round(float(r.abs().max() * 100), 2),
            "zero_return_days": int((r.abs() < 1e-10).sum()),
            "jumps_gt_8sigma": int((r.abs() > 8 * sigma).sum()) if sigma > 0 else 0,
            "adv_usd_mm": round(float((volume[t] * prices[t]).tail(60).mean() / 1e6), 1)
            if volume is not None and t in volume else None,
        })
    table = pd.DataFrame(rows).set_index("ticker")

    # 全体共同交易日：所有资产都有价格的日子。样本从这里开始。
    complete = prices.dropna(how="any")
    report = {
        "n_rows_raw": int(len(prices)),
        "n_rows_complete": int(len(complete)),
        "common_start": complete.index[0].date().isoformat() if len(complete) else None,
        "common_end": complete.index[-1].date().isoformat() if len(complete) else None,
        "duplicate_dates": int(prices.index.duplicated().sum()),
        "monotonic_index": bool(prices.index.is_monotonic_increasing),
        "assets": table.reset_index().to_dict(orient="records"),
        "min_obs_required": cfg.get("data", "min_obs"),
    }
    too_short = [r["ticker"] for r in report["assets"] if r["n_obs"] < report["min_obs_required"]]
    report["assets_below_min_obs"] = too_short

    out_dir = cfg.path_of("data", "processed_dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "data_quality.csv", encoding="utf-8-sig")
    return report


# --------------------------------------------------------------- 收益面板
def build_panel(cfg: Config, *, drop_incomplete: bool = True) -> dict:
    """产出回测用的干净面板：收益、价格、美元成交额（ADV）。"""
    prices, volume = load_raw(cfg)
    if drop_incomplete:
        prices = prices.dropna(how="any")
    rets = prices.pct_change()
    if drop_incomplete:
        rets = rets.iloc[1:]
    if volume is not None:
        adv = (volume * prices).rolling(60, min_periods=20).mean()
        adv = adv.reindex(prices.index)
    else:
        adv = None
    return {"prices": prices, "returns": rets, "adv_usd": adv}


def save_panel(cfg: Config, panel: dict) -> None:
    out = cfg.path_of("data", "processed_dir")
    out.mkdir(parents=True, exist_ok=True)
    panel["returns"].to_parquet(out / "returns.parquet")
    panel["prices"].to_parquet(out / "prices_panel.parquet")
    if panel.get("adv_usd") is not None:
        panel["adv_usd"].to_parquet(out / "adv_usd.parquet")
