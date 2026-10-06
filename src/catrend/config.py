"""配置加载与哈希。代码里不写死任何参数，全部从 YAML 来。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Asset:
    ticker: str
    name_zh: str
    name_en: str
    asset_class: str
    group: str


@dataclass
class Config:
    raw: dict[str, Any]
    path: Path
    root: Path
    assets: list[Asset] = field(default_factory=list)

    # ---- 便捷访问 ----
    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.raw
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    @property
    def tickers(self) -> list[str]:
        return [a.ticker for a in self.assets]

    @property
    def asset_class(self) -> dict[str, str]:
        return {a.ticker: a.asset_class for a in self.assets}

    @property
    def group(self) -> dict[str, str]:
        return {a.ticker: a.group for a in self.assets}

    def path_of(self, *keys: str) -> Path:
        rel = self.get(*keys)
        if rel is None:
            raise KeyError(f"config 缺少 {'/'.join(keys)}")
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p)

    def override(self, **kwargs: Any) -> "Config":
        """返回一个改了若干字段的副本（用于稳健性扫描）。键是顶层字段名。"""
        merged = json.loads(json.dumps(self.raw))
        for dotted, value in kwargs.items():
            node = merged
            parts = dotted.split(".")
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = value
        return Config(raw=merged, path=self.path, root=self.root, assets=self.assets)

    def hash(self) -> str:
        blob = json.dumps(self.raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:12]


def load(path: str | Path) -> Config:
    p = Path(path).resolve()
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    root = p.parent.parent if p.parent.name == "config" else p.parent
    assets = [Asset(**u) for u in raw.get("universe", [])]
    if not assets:
        raise ValueError(f"{p} 里没有 universe")
    return Config(raw=raw, path=p, root=root, assets=assets)
