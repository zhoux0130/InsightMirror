"""Historical initialization entrypoint."""

from __future__ import annotations

import argparse

from sqlalchemy import text

from app.config import settings
from app.db.connection import get_db
from scripts.backfill_full_labels import backfill_full_labels
from scripts.build_full_segments import build_full_segments
from scripts.common import parse_symbols_arg
from scripts.fetch_full_history import fetch_full_history
from scripts.init_db import build_hnsw_index, ensure_pgvector_schema
from scripts.init_security_master import init_security_master
from scripts.load_daily_bars import load_daily_bars


SEED_FEATURE_VERSION_SQL = text(
    """
    INSERT INTO feature_version_config (
        version, description, feature_dim, feature_params, status, is_default
    )
    VALUES (
        'v1',
        'V1: 182-dim feature (price + return + volume + stats)',
        182,
        '{"w_P": 1.0, "w_R": 0.5, "w_V": 0.7, "w_S": 1.5, "window_size": 60}'::jsonb,
        'active',
        true
    )
    ON CONFLICT (version) DO NOTHING;
    """
)


def seed_feature_version_config() -> None:
    with get_db() as db:
        db.execute(SEED_FEATURE_VERSION_SQL)


def full_init(
    symbols: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    skip_hnsw: bool = False,
) -> dict:
    ensure_pgvector_schema(build_hnsw=False)
    seed_feature_version_config()

    steps = {
        "security_master": init_security_master(symbols=symbols),
        "history": fetch_full_history(symbols=symbols, start_date=start_date, end_date=end_date),
        "daily_bar": load_daily_bars(symbols=symbols),
        "segments": build_full_segments(symbols=symbols),
        "labels": backfill_full_labels(symbols=symbols),
    }
    if not skip_hnsw:
        build_hnsw_index()
        steps["hnsw"] = {"status": "built"}
    return steps


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full historical initialization")
    parser.add_argument("--symbols", help="Comma-separated A-share symbols")
    parser.add_argument("--start", dest="start_date", default=settings.history_start_date)
    parser.add_argument("--end", dest="end_date", default=settings.history_end_date)
    parser.add_argument("--skip-hnsw", action="store_true")
    args = parser.parse_args()

    result = full_init(
        symbols=parse_symbols_arg(args.symbols),
        start_date=args.start_date,
        end_date=args.end_date,
        skip_hnsw=args.skip_hnsw,
    )
    for step, payload in result.items():
        print(f"{step}: {payload}")


if __name__ == "__main__":
    main()
