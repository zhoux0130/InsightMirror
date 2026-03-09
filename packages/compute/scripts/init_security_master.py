from __future__ import annotations

import argparse
from datetime import date

import pandas as pd
from sqlalchemy import text

from app.data.factory import get_data_source
from app.db.connection import get_db
from scripts.common import ensure_parent, parse_symbols_arg, universe_snapshot_dir


UPSERT_SECURITY_MASTER_SQL = text(
    """
    INSERT INTO security_master (
        symbol, name, exchange, list_date, delist_date, list_status, source, updated_at
    ) VALUES (
        :symbol, :name, :exchange, :list_date, :delist_date, :list_status, :source, NOW()
    )
    ON CONFLICT (symbol) DO UPDATE SET
        name = EXCLUDED.name,
        exchange = EXCLUDED.exchange,
        list_date = COALESCE(EXCLUDED.list_date, security_master.list_date),
        delist_date = COALESCE(EXCLUDED.delist_date, security_master.delist_date),
        list_status = EXCLUDED.list_status,
        source = EXCLUDED.source,
        updated_at = NOW()
    """
)


def build_security_master_rows(symbols: list[str] | None = None) -> list[dict]:
    source = get_data_source()
    base_rows = source.get_stock_list()
    if symbols:
        wanted = set(symbols)
        base_rows = [row for row in base_rows if row["symbol"] in wanted]

    rows: list[dict] = []
    fetch_metadata = bool(symbols)
    for row in base_rows:
        merged = dict(row)
        if fetch_metadata:
            try:
                metadata = source.get_stock_metadata(row["symbol"])
            except Exception:
                metadata = {}
            if metadata:
                merged.update({key: value for key, value in metadata.items() if value is not None})
        merged.setdefault("list_date", None)
        merged.setdefault("delist_date", None)
        rows.append(merged)
    return rows


def write_universe_snapshot(rows: list[dict], snapshot_date: str | None = None) -> str:
    snapshot_date = snapshot_date or date.today().isoformat()
    directory = universe_snapshot_dir(snapshot_date)
    path = ensure_parent(directory / "stocks.csv")
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def upsert_security_master(rows: list[dict]) -> int:
    if not rows:
        return 0
    with get_db() as db:
        db.execute(UPSERT_SECURITY_MASTER_SQL, rows)
    return len(rows)


def init_security_master(symbols: list[str] | None = None, snapshot_date: str | None = None) -> dict:
    rows = build_security_master_rows(symbols=symbols)
    snapshot_path = write_universe_snapshot(rows, snapshot_date=snapshot_date)
    count = upsert_security_master(rows)
    return {"rows": count, "snapshot_path": snapshot_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize security_master from data source")
    parser.add_argument("--symbols", help="Comma-separated A-share symbols, e.g. 300750.SZ")
    parser.add_argument("--snapshot-date", help="Snapshot date directory, defaults to today")
    args = parser.parse_args()

    result = init_security_master(
        symbols=parse_symbols_arg(args.symbols),
        snapshot_date=args.snapshot_date,
    )
    print(f"security_master upserted: {result['rows']}")
    print(f"snapshot: {result['snapshot_path']}")


if __name__ == "__main__":
    main()
