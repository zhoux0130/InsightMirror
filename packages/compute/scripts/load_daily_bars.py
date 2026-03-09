from __future__ import annotations

import argparse
from datetime import date

import pandas as pd
from sqlalchemy import text

from app.db.connection import get_db
from scripts.common import chunked, daily_snapshot_path, parse_symbols_arg


LIST_SECURITY_SQL = text(
    """
    SELECT symbol, list_date
    FROM security_master
    ORDER BY symbol
    """
)

UPSERT_DAILY_BAR_SQL = text(
    """
    INSERT INTO daily_bar (
        symbol, trade_date, open, high, low, close, volume, amount, turnover, pct_change
    ) VALUES (
        :symbol, :trade_date, :open, :high, :low, :close, :volume, :amount, :turnover, :pct_change
    )
    ON CONFLICT (symbol, trade_date) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume,
        amount = EXCLUDED.amount,
        turnover = EXCLUDED.turnover,
        pct_change = EXCLUDED.pct_change
    """
)


COLUMN_MAP = {
    "trade_date": "日期",
    "open": "开盘",
    "high": "最高",
    "low": "最低",
    "close": "收盘",
    "volume": "成交量",
    "amount": "成交额",
    "turnover": "换手率",
    "pct_change": "涨跌幅",
}


def _pick_column(raw: pd.DataFrame, english: str) -> str:
    if english in raw.columns:
        return english
    chinese = COLUMN_MAP[english]
    if chinese in raw.columns:
        return chinese
    raise KeyError(f"Missing required column for {english}")


def normalize_daily_bars_frame(
    symbol: str,
    raw: pd.DataFrame,
    list_date: date | None = None,
) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "turnover",
                "pct_change",
            ]
        )

    normalized = pd.DataFrame(
        {
            "symbol": symbol,
            "trade_date": pd.to_datetime(raw[_pick_column(raw, "trade_date")]).dt.date,
            "open": pd.to_numeric(raw[_pick_column(raw, "open")], errors="coerce"),
            "high": pd.to_numeric(raw[_pick_column(raw, "high")], errors="coerce"),
            "low": pd.to_numeric(raw[_pick_column(raw, "low")], errors="coerce"),
            "close": pd.to_numeric(raw[_pick_column(raw, "close")], errors="coerce"),
            "volume": pd.to_numeric(raw[_pick_column(raw, "volume")], errors="coerce").fillna(0).astype(int),
            "amount": pd.to_numeric(raw.get(_pick_column(raw, "amount")), errors="coerce"),
            "turnover": pd.to_numeric(raw.get(_pick_column(raw, "turnover")), errors="coerce"),
            "pct_change": pd.to_numeric(raw.get(_pick_column(raw, "pct_change")), errors="coerce"),
        }
    )
    normalized = normalized.dropna(subset=["trade_date", "open", "high", "low", "close"])
    if list_date is not None:
        normalized = normalized[normalized["trade_date"] >= list_date]
    normalized = normalized.sort_values("trade_date").drop_duplicates(subset=["trade_date"], keep="last")
    return normalized.reset_index(drop=True)


def load_security_master_symbols(symbols: list[str] | None = None) -> list[tuple[str, date | None]]:
    with get_db() as db:
        rows = db.execute(LIST_SECURITY_SQL).fetchall()
    if symbols:
        wanted = set(symbols)
        rows = [row for row in rows if row[0] in wanted]
    return [(row[0], row[1]) for row in rows]


def upsert_daily_bar_rows(rows: list[dict]) -> int:
    if not rows:
        return 0
    with get_db() as db:
        for batch in chunked(rows, size=1000):
            db.execute(UPSERT_DAILY_BAR_SQL, batch)
    return len(rows)


def load_daily_bars(symbols: list[str] | None = None) -> dict:
    loaded = 0
    per_symbol: dict[str, int] = {}
    for symbol, list_date in load_security_master_symbols(symbols):
        path = daily_snapshot_path(symbol)
        if not path.exists():
            continue
        raw = pd.read_csv(path)
        normalized = normalize_daily_bars_frame(symbol=symbol, raw=raw, list_date=list_date)
        records = normalized.to_dict("records")
        count = upsert_daily_bar_rows(records)
        per_symbol[symbol] = count
        loaded += count
    return {"rows": loaded, "per_symbol": per_symbol}


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize raw snapshots and load daily_bar")
    parser.add_argument("--symbols", help="Comma-separated A-share symbols")
    args = parser.parse_args()

    result = load_daily_bars(symbols=parse_symbols_arg(args.symbols))
    print(f"daily_bar rows loaded: {result['rows']}")
    for symbol, count in result["per_symbol"].items():
        print(f"  {symbol}: {count}")


if __name__ == "__main__":
    main()
