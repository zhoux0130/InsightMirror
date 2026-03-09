from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.config import settings
from app.data.akshare import canonicalize_a_share_symbol


def parse_symbols_arg(symbols: str | None) -> list[str] | None:
    if not symbols:
        return None
    normalized = [
        canonicalize_a_share_symbol(part)
        for part in symbols.split(",")
        if part.strip()
    ]
    return normalized or None


def raw_data_root() -> Path:
    root = Path(settings.raw_data_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[1] / root
    return root


def universe_snapshot_dir(snapshot_date: str) -> Path:
    return raw_data_root() / "akshare" / "universe" / snapshot_date


def daily_snapshot_path(symbol: str) -> Path:
    return raw_data_root() / "akshare" / "daily" / f"{canonicalize_a_share_symbol(symbol)}.csv"


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def chunked(items: Iterable[dict], size: int) -> list[list[dict]]:
    chunk: list[dict] = []
    batches: list[list[dict]] = []
    for item in items:
        chunk.append(item)
        if len(chunk) >= size:
            batches.append(chunk)
            chunk = []
    if chunk:
        batches.append(chunk)
    return batches
