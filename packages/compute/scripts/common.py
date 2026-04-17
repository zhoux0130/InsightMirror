from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

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


# State Grid OSS key helpers

def state_grid_list_snapshot_key(api: str, task_id: str, page: int, dt: Optional[datetime] = None) -> str:
    """Generate OSS key for state grid list snapshot."""
    dt = dt or datetime.utcnow()
    date_str = dt.strftime("%Y/%m/%d")
    return f"{settings.state_grid_oss_prefix}/list/{api}/{date_str}/{task_id}-{page}.json"


def state_grid_detail_snapshot_key(notice_id: str, api: str, timestamp: str) -> str:
    """Generate OSS key for state grid detail snapshot."""
    return f"{settings.state_grid_oss_prefix}/detail/{notice_id}/{api}-{timestamp}.json"


def state_grid_file_key(notice_id: str, sha256: str, original_name: str) -> str:
    """Generate OSS key for state grid file attachment."""
    return f"{settings.state_grid_oss_prefix}/file/{notice_id}/{sha256[:8]}/{sha256}/{original_name}"


def state_grid_html_key(notice_id: str, api: str, timestamp: str) -> str:
    """Generate OSS key for state grid HTML content."""
    return f"{settings.state_grid_oss_prefix}/file/{notice_id}/render/{api}-{timestamp}.html"


def ensure_state_grid_raw_dir(subpath: str) -> Path:
    """Return a Path under the raw root for local state-grid staging."""
    return raw_data_root() / "state_grid" / subpath
