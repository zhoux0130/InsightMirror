from __future__ import annotations

import argparse
from datetime import date

import numpy as np
from sqlalchemy import text

from app.config import settings
from app.core.feature import registry as feature_registry
from app.db.connection import get_db
from scripts.common import parse_symbols_arg


LIST_SYMBOLS_SQL = text(
    """
    SELECT symbol
    FROM security_master
    ORDER BY symbol
    """
)

LIST_DAILY_ROWS_SQL = text(
    """
    SELECT trade_date, open, high, low, close, volume, amount, turnover, pct_change
    FROM daily_bar
    WHERE symbol = :symbol
    ORDER BY trade_date ASC
    """
)

INSERT_SEGMENT_SQL = text(
    """
    INSERT INTO segment_index (symbol, start_date, end_date, window_size, feature_version)
    VALUES (:symbol, :start_date, :end_date, :window_size, :feature_version)
    ON CONFLICT (symbol, end_date, window_size, feature_version) DO NOTHING
    RETURNING id
    """
)

SELECT_SEGMENT_ID_SQL = text(
    """
    SELECT id
    FROM segment_index
    WHERE symbol = :symbol
      AND end_date = :end_date
      AND window_size = :window_size
      AND feature_version = :feature_version
    """
)

UPSERT_FEATURE_SQL = text(
    """
    INSERT INTO segment_feature (segment_id, feature_vector, norm)
    VALUES (:segment_id, CAST(:vector AS vector), :norm)
    ON CONFLICT (segment_id) DO UPDATE SET
        feature_vector = EXCLUDED.feature_vector,
        norm = EXCLUDED.norm
    """
)

UPSERT_LABEL_SQL = text(
    """
    INSERT INTO segment_future_label (segment_id, future_days, label_status)
    VALUES (:segment_id, :future_days, :label_status)
    ON CONFLICT (segment_id) DO NOTHING
    """
)


def build_segments_for_history(
    symbol: str,
    rows: list[dict],
    feature_version: str,
    window_size: int,
    segment_id_start: int,
    future_days: int = 20,
) -> tuple[list[dict], list[dict], list[dict]]:
    calculator = feature_registry.get(feature_version)
    segments: list[dict] = []
    features: list[dict] = []
    labels: list[dict] = []

    next_segment_id = segment_id_start
    for index in range(window_size - 1, len(rows)):
        window = rows[index - window_size + 1 : index + 1]
        close = np.array([float(row["close"]) for row in window], dtype=np.float64)
        volume = np.array([float(row["volume"]) for row in window], dtype=np.float64)
        high = np.array([float(row["high"]) for row in window], dtype=np.float64)
        low = np.array([float(row["low"]) for row in window], dtype=np.float64)

        feature = calculator.calculate(close, volume, high, low)
        segments.append(
            {
                "id": next_segment_id,
                "symbol": symbol,
                "start_date": window[0]["trade_date"],
                "end_date": window[-1]["trade_date"],
                "window_size": window_size,
                "feature_version": feature_version,
            }
        )
        features.append(
            {
                "segment_id": next_segment_id,
                "feature": feature.tolist(),
                "norm": float(np.linalg.norm(feature)),
            }
        )
        labels.append(
            {
                "segment_id": next_segment_id,
                "future_days": future_days,
                "label_status": "pending",
            }
        )
        next_segment_id += 1

    return segments, features, labels


def _load_symbol_history(symbol: str) -> list[dict]:
    with get_db() as db:
        rows = db.execute(LIST_DAILY_ROWS_SQL, {"symbol": symbol}).fetchall()
    return [
        {
            "trade_date": row[0],
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": int(row[5]),
            "amount": float(row[6]) if row[6] is not None else None,
            "turnover": float(row[7]) if row[7] is not None else None,
            "pct_change": float(row[8]) if row[8] is not None else None,
        }
        for row in rows
    ]


def _upsert_symbol_segments(symbol: str, feature_version: str, window_size: int, future_days: int) -> int:
    rows = _load_symbol_history(symbol)
    if len(rows) < window_size:
        return 0

    calculator = feature_registry.get(feature_version)
    inserted = 0
    with get_db() as db:
        for index in range(window_size - 1, len(rows)):
            window = rows[index - window_size + 1 : index + 1]
            start_date = window[0]["trade_date"]
            end_date = window[-1]["trade_date"]
            close = np.array([float(row["close"]) for row in window], dtype=np.float64)
            volume = np.array([float(row["volume"]) for row in window], dtype=np.float64)
            high = np.array([float(row["high"]) for row in window], dtype=np.float64)
            low = np.array([float(row["low"]) for row in window], dtype=np.float64)
            feature = calculator.calculate(close, volume, high, low)

            result = db.execute(
                INSERT_SEGMENT_SQL,
                {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "window_size": window_size,
                    "feature_version": feature_version,
                },
            ).fetchone()
            if result is None:
                result = db.execute(
                    SELECT_SEGMENT_ID_SQL,
                    {
                        "symbol": symbol,
                        "end_date": end_date,
                        "window_size": window_size,
                        "feature_version": feature_version,
                    },
                ).fetchone()
            if result is None:
                continue

            segment_id = result[0]
            db.execute(
                UPSERT_FEATURE_SQL,
                {
                    "segment_id": segment_id,
                    "vector": "[" + ",".join(str(float(value)) for value in feature) + "]",
                    "norm": float(np.linalg.norm(feature)),
                },
            )
            db.execute(
                UPSERT_LABEL_SQL,
                {
                    "segment_id": segment_id,
                    "future_days": future_days,
                    "label_status": "pending",
                },
            )
            inserted += 1
    return inserted


def build_full_segments(
    symbols: list[str] | None = None,
    feature_version: str | None = None,
    window_size: int | None = None,
    future_days: int = 20,
) -> dict:
    feature_version = feature_version or settings.default_feature_version
    window_size = window_size or settings.default_window_size

    with get_db() as db:
        symbol_rows = db.execute(LIST_SYMBOLS_SQL).fetchall()
    target_symbols = [row[0] for row in symbol_rows]
    if symbols:
        wanted = set(symbols)
        target_symbols = [symbol for symbol in target_symbols if symbol in wanted]

    results: dict[str, int] = {}
    total = 0
    for symbol in target_symbols:
        count = _upsert_symbol_segments(symbol, feature_version, window_size, future_days)
        results[symbol] = count
        total += count
    return {"rows": total, "per_symbol": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build historical segments and vectors")
    parser.add_argument("--symbols", help="Comma-separated A-share symbols")
    parser.add_argument("--feature-version", default=settings.default_feature_version)
    parser.add_argument("--window-size", type=int, default=settings.default_window_size)
    parser.add_argument("--future-days", type=int, default=20)
    args = parser.parse_args()

    result = build_full_segments(
        symbols=parse_symbols_arg(args.symbols),
        feature_version=args.feature_version,
        window_size=args.window_size,
        future_days=args.future_days,
    )
    print(f"segments built: {result['rows']}")
    for symbol, count in result["per_symbol"].items():
        print(f"  {symbol}: {count}")


if __name__ == "__main__":
    main()
