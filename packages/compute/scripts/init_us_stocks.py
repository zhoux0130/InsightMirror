"""Initialize US stock data via Yahoo Finance.

Usage:
    python -m scripts.init_us_stocks --symbols AAPL,MSFT,TSLA --start 2020-01-01
    python -m scripts.init_us_stocks --symbols AAPL --skip-hnsw
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date

from sqlalchemy import text

from app.config import settings
from app.data.yahoo import YahooFinanceDataSource
from app.db.connection import get_db
from scripts.build_full_segments import build_full_segments
from scripts.backfill_full_labels import backfill_full_labels
from scripts.init_db import build_hnsw_index

logger = logging.getLogger(__name__)

UPSERT_SECURITY_MASTER_SQL = text(
    """
    INSERT INTO security_master (symbol, name, exchange, market, list_status, source)
    VALUES (:symbol, :name, :exchange, :market, :list_status, :source)
    ON CONFLICT (symbol) DO UPDATE SET
        name = EXCLUDED.name,
        exchange = EXCLUDED.exchange,
        market = EXCLUDED.market,
        source = EXCLUDED.source,
        updated_at = NOW()
    """
)

UPSERT_DAILY_BAR_SQL = text(
    """
    INSERT INTO daily_bar (symbol, trade_date, market, open, high, low, close, volume, amount, turnover, pct_change)
    VALUES (:symbol, :trade_date, :market, :open, :high, :low, :close, :volume, :amount, :turnover, :pct_change)
    ON CONFLICT (symbol, trade_date) DO UPDATE SET
        open = EXCLUDED.open, high = EXCLUDED.high,
        low = EXCLUDED.low, close = EXCLUDED.close,
        volume = EXCLUDED.volume, amount = EXCLUDED.amount,
        pct_change = EXCLUDED.pct_change,
        market = EXCLUDED.market
    """
)


def parse_us_symbols(symbols_arg: str) -> list[str]:
    """Parse comma-separated US stock symbols (e.g. 'AAPL,MSFT,TSLA')."""
    return [s.strip().upper() for s in symbols_arg.split(",") if s.strip()]


def init_us_security_master(symbols: list[str]) -> dict:
    """Fetch metadata from Yahoo and upsert into security_master."""
    ds = YahooFinanceDataSource()
    results: dict[str, str] = {}

    with get_db() as db:
        for symbol in symbols:
            try:
                meta = ds.get_stock_metadata(symbol)
                if not meta:
                    results[symbol] = "not_found"
                    continue

                db.execute(UPSERT_SECURITY_MASTER_SQL, {
                    "symbol": meta["symbol"],
                    "name": meta["name"],
                    "exchange": meta["exchange"],
                    "market": "US",
                    "list_status": meta.get("list_status", "listed"),
                    "source": "yahoo",
                })
                results[symbol] = "ok"
                logger.info("Security master: %s (%s)", symbol, meta["name"])
            except Exception as exc:
                results[symbol] = f"error: {exc}"
                logger.warning("Failed to init security master for %s: %s", symbol, exc)

    return results


def fetch_us_daily_bars(
    symbols: list[str],
    start_date: str,
    end_date: str | None = None,
) -> dict:
    """Fetch historical daily bars from Yahoo Finance and store in DB."""
    ds = YahooFinanceDataSource()
    end = end_date or date.today().isoformat()
    results: dict[str, int] = {}

    for symbol in symbols:
        try:
            bars = ds.fetch_daily(symbol, start_date, end)
            if not bars:
                results[symbol] = 0
                continue

            with get_db() as db:
                for bar in bars:
                    db.execute(UPSERT_DAILY_BAR_SQL, {
                        "symbol": bar["symbol"],
                        "trade_date": bar["trade_date"],
                        "market": "US",
                        "open": bar["open"],
                        "high": bar["high"],
                        "low": bar["low"],
                        "close": bar["close"],
                        "volume": bar["volume"],
                        "amount": bar.get("amount", 0),
                        "turnover": bar.get("turnover", 0),
                        "pct_change": bar.get("pct_change", 0),
                    })

            results[symbol] = len(bars)
            logger.info("Fetched %d bars for %s", len(bars), symbol)

            # Rate limit: avoid hitting Yahoo too fast
            time.sleep(0.5)
        except Exception as exc:
            results[symbol] = 0
            logger.warning("Failed to fetch daily bars for %s: %s", symbol, exc)

    return results


def init_us_stocks(
    symbols: list[str],
    start_date: str,
    end_date: str | None = None,
    skip_hnsw: bool = False,
) -> dict:
    """Full initialization pipeline for US stocks.

    Steps:
        1. Register symbols in security_master (market='US')
        2. Fetch historical daily bars from Yahoo Finance
        3. Build segment index + feature vectors (reuses CN logic)
        4. Backfill future labels
        5. Rebuild HNSW index (optional)
    """
    print(f"=== US Stock Init: {', '.join(symbols)} ===")
    print(f"    Date range: {start_date} ~ {end_date or 'today'}")
    print()

    # Step 1: Security Master
    print("[1/5] Initializing security master...")
    sm_result = init_us_security_master(symbols)
    for sym, status in sm_result.items():
        print(f"  {sym}: {status}")
    print()

    # Step 2: Daily Bars
    print("[2/5] Fetching daily bars from Yahoo Finance...")
    bars_result = fetch_us_daily_bars(symbols, start_date, end_date)
    for sym, count in bars_result.items():
        print(f"  {sym}: {count} bars")
    print()

    # Step 3: Segments & Vectors
    print("[3/5] Building segments and feature vectors...")
    seg_result = build_full_segments(symbols=symbols)
    print(f"  Total segments: {seg_result['rows']}")
    print()

    # Step 4: Labels
    print("[4/5] Backfilling future labels...")
    label_result = backfill_full_labels(symbols=symbols)
    print(f"  Labels: {label_result}")
    print()

    # Step 5: HNSW
    if not skip_hnsw:
        print("[5/5] Rebuilding HNSW index...")
        build_hnsw_index()
        print("  Done")
    else:
        print("[5/5] Skipping HNSW rebuild (--skip-hnsw)")

    print()
    print("=== US Stock Init Complete ===")

    return {
        "security_master": sm_result,
        "daily_bars": bars_result,
        "segments": seg_result,
        "labels": label_result,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Initialize US stock data via Yahoo Finance")
    parser.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated US stock symbols (e.g. AAPL,MSFT,TSLA)",
    )
    parser.add_argument("--start", dest="start_date", default="2020-01-01")
    parser.add_argument("--end", dest="end_date", default=None)
    parser.add_argument("--skip-hnsw", action="store_true")
    args = parser.parse_args()

    symbols = parse_us_symbols(args.symbols)
    if not symbols:
        parser.error("At least one symbol is required")

    init_us_stocks(
        symbols=symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        skip_hnsw=args.skip_hnsw,
    )


if __name__ == "__main__":
    main()
