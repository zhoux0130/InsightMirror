from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.data.factory import get_data_source
from app.db.connection import get_db
from scripts.common import daily_snapshot_path, ensure_parent, parse_symbols_arg


LIST_SYMBOLS_SQL = text(
    """
    SELECT symbol
    FROM security_master
    WHERE list_status IN ('listed', 'delisted', 'suspended')
    ORDER BY symbol
    """
)

UPDATE_LIST_DATE_SQL = text(
    """
    UPDATE security_master
    SET list_date = COALESCE(list_date, :list_date),
        updated_at = NOW()
    WHERE symbol = :symbol
    """
)


def list_symbols(symbols: list[str] | None = None) -> list[str]:
    if symbols:
        return symbols
    with get_db() as db:
        return [row[0] for row in db.execute(LIST_SYMBOLS_SQL).fetchall()]


def fetch_symbol_history(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str | None = None,
) -> Path | None:
    source = get_data_source()
    frame = source.fetch_daily_frame(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust or settings.history_adjust,
    )
    if frame.empty:
        return None

    path = ensure_parent(daily_snapshot_path(symbol))
    frame.to_csv(path, index=False)

    first_trade_date = str(frame.sort_values("日期").iloc[0]["日期"])
    with get_db() as db:
        db.execute(
            UPDATE_LIST_DATE_SQL,
            {"symbol": symbol, "list_date": first_trade_date},
        )

    return path


def fetch_full_history(
    symbols: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    start_date = start_date or settings.history_start_date
    end_date = end_date or settings.history_end_date
    target_symbols = list_symbols(symbols)

    written = 0
    failed: list[str] = []
    for symbol in target_symbols:
        path = fetch_symbol_history(symbol, start_date, end_date)
        if path is None:
            failed.append(symbol)
            continue
        written += 1

    return {"written": written, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch historical daily bars into raw snapshots")
    parser.add_argument("--symbols", help="Comma-separated A-share symbols")
    parser.add_argument("--start", dest="start_date", default=settings.history_start_date)
    parser.add_argument("--end", dest="end_date", default=settings.history_end_date)
    args = parser.parse_args()

    result = fetch_full_history(
        symbols=parse_symbols_arg(args.symbols),
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(f"snapshots written: {result['written']}")
    if result["failed"]:
        print("failed symbols:", ", ".join(result["failed"]))


if __name__ == "__main__":
    main()
