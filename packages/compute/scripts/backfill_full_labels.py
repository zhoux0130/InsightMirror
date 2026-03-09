from __future__ import annotations

import argparse

import numpy as np
from sqlalchemy import text

from app.db.connection import get_db
from scripts.common import parse_symbols_arg


LIST_PENDING_SQL = text(
    """
    SELECT sfl.segment_id, si.symbol, si.end_date, sfl.future_days
    FROM segment_future_label sfl
    JOIN segment_index si ON si.id = sfl.segment_id
    WHERE sfl.label_status = 'pending'
    ORDER BY si.symbol, si.end_date
    """
)

BASE_CLOSE_SQL = text(
    """
    SELECT close
    FROM daily_bar
    WHERE symbol = :symbol AND trade_date = :end_date
    """
)

FUTURE_ROWS_SQL = text(
    """
    SELECT trade_date, close
    FROM daily_bar
    WHERE symbol = :symbol AND trade_date > :end_date
    ORDER BY trade_date ASC
    LIMIT :limit
    """
)

UPDATE_LABEL_SQL = text(
    """
    UPDATE segment_future_label
    SET return_rate = :return_rate,
        max_drawdown = :max_drawdown,
        max_profit = :max_profit,
        sharpe_ratio = :sharpe_ratio,
        win_flag = :win_flag,
        label_status = :label_status,
        filled_at = CASE WHEN :label_status = 'filled' THEN NOW() ELSE filled_at END
    WHERE segment_id = :segment_id
    """
)


def compute_future_label(
    segment_id: int,
    future_rows: list[dict],
    future_days: int,
    base_close: float | None = None,
) -> dict:
    if len(future_rows) < future_days:
        return {"segment_id": segment_id, "label_status": "na"}

    prices = np.array([float(row["close"]) for row in future_rows[:future_days]], dtype=np.float64)
    start_price = float(base_close) if base_close is not None else float(prices[0])
    returns = (prices - start_price) / start_price
    path = np.concatenate([[start_price], prices])
    daily_returns = np.diff(path) / path[:-1]
    sharpe = 0.0
    if len(daily_returns) > 1 and np.std(daily_returns) > 1e-10:
        sharpe = float(np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252))

    return {
        "segment_id": segment_id,
        "return_rate": round(float(returns[-1]), 4),
        "max_drawdown": round(float(np.min(returns)), 4),
        "max_profit": round(float(np.max(returns)), 4),
        "sharpe_ratio": round(sharpe, 4),
        "win_flag": bool(returns[-1] > 0),
        "label_status": "filled",
    }


def backfill_full_labels(symbols: list[str] | None = None) -> dict:
    updated = 0
    per_symbol: dict[str, int] = {}
    with get_db() as db:
        pending = db.execute(LIST_PENDING_SQL).fetchall()
        if symbols:
            wanted = set(symbols)
            pending = [row for row in pending if row[1] in wanted]
        for segment_id, symbol, end_date, future_days in pending:
            base_close_row = db.execute(
                BASE_CLOSE_SQL,
                {"symbol": symbol, "end_date": end_date},
            ).fetchone()
            future_rows = [
                {"trade_date": row[0], "close": float(row[1])}
                for row in db.execute(
                    FUTURE_ROWS_SQL,
                    {"symbol": symbol, "end_date": end_date, "limit": future_days},
                ).fetchall()
            ]
            label = compute_future_label(
                segment_id=segment_id,
                future_rows=future_rows,
                future_days=future_days,
                base_close=float(base_close_row[0]) if base_close_row else None,
            )
            db.execute(
                UPDATE_LABEL_SQL,
                {
                    "segment_id": label["segment_id"],
                    "return_rate": label.get("return_rate"),
                    "max_drawdown": label.get("max_drawdown"),
                    "max_profit": label.get("max_profit"),
                    "sharpe_ratio": label.get("sharpe_ratio"),
                    "win_flag": label.get("win_flag"),
                    "label_status": label["label_status"],
                },
            )
            updated += 1
            per_symbol[symbol] = per_symbol.get(symbol, 0) + 1
    return {"rows": updated, "per_symbol": per_symbol}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill future labels using trading-day windows")
    parser.add_argument("--symbols", help="Comma-separated A-share symbols")
    args = parser.parse_args()

    result = backfill_full_labels(symbols=parse_symbols_arg(args.symbols))
    print(f"labels backfilled: {result['rows']}")
    for symbol, count in result["per_symbol"].items():
        print(f"  {symbol}: {count}")


if __name__ == "__main__":
    main()
