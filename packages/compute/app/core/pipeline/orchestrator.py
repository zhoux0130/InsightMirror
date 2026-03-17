"""EOD Pipeline Orchestrator.

Steps: fetch_daily_bar → compute_features → store_vectors → backfill_labels
"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session
import numpy as np

from app.config import settings
from app.core.feature import registry as feature_registry
from app.data.factory import get_data_source

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self, db: Session):
        self.db = db

    def run_eod(self, run_date: date | None = None, market: str = "CN") -> dict:
        """Run the end-of-day pipeline.

        Args:
            run_date: The date to run the pipeline for.
            market: 'CN' for A-shares (via akshare) or 'US' for US stocks (via yahoo).
        """
        run_date = run_date or date.today()
        results = {}

        steps = [
            ("fetch_daily_bar", self._step_fetch_daily_bar),
            ("compute_features", self._step_compute_features),
            ("store_vectors", self._step_store_vectors),
            ("backfill_labels", self._step_backfill_labels),
        ]

        for step_name, step_fn in steps:
            self._log_step(run_date, step_name, "running", market=market)
            try:
                count = step_fn(run_date, market=market)
                self._log_step(run_date, step_name, "success", count, market=market)
                results[step_name] = {"status": "success", "records": count}
            except Exception as e:
                logger.error(f"Pipeline step {step_name} failed: {e}")
                self._log_step(run_date, step_name, "failed", error=str(e), market=market)
                results[step_name] = {"status": "failed", "error": str(e)}
                break  # Stop pipeline on failure

        return results

    def _step_fetch_daily_bar(self, run_date: date, *, market: str = "CN") -> int:
        """Fetch daily bars from data source and store in DB."""
        source_name = "yahoo" if market == "US" else None
        try:
            ds = get_data_source(source_name)
        except Exception as exc:
            logger.warning("Data source unavailable, skipping fetch: %s", exc)
            return 0

        sql = text("""
            SELECT symbol
            FROM security_master
            WHERE list_status IN ('listed', 'suspended')
              AND market = :market
            ORDER BY symbol
        """)
        symbols = [row[0] for row in self.db.execute(sql, {"market": market}).fetchall()]

        count = 0
        for symbol in symbols:
            try:
                bars = ds.fetch_daily(symbol, run_date, run_date)
                for bar in bars:
                    self.db.execute(text("""
                        INSERT INTO daily_bar (symbol, trade_date, market, open, high, low, close, volume, amount, turnover, pct_change)
                        VALUES (:symbol, :trade_date, :market, :open, :high, :low, :close, :volume, :amount, :turnover, :pct_change)
                        ON CONFLICT (symbol, trade_date) DO UPDATE SET
                            open = EXCLUDED.open, high = EXCLUDED.high,
                            low = EXCLUDED.low, close = EXCLUDED.close,
                            volume = EXCLUDED.volume, amount = EXCLUDED.amount,
                            turnover = EXCLUDED.turnover, pct_change = EXCLUDED.pct_change
                    """), {
                        **bar,
                        "market": market,
                        "trade_date": bar["trade_date"],
                    })
                    count += 1
                self.db.commit()
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")

        return count

    def _step_compute_features(self, run_date: date, *, market: str = "CN") -> int:
        """Compute feature vectors for new segments."""
        calculator = feature_registry.get(settings.default_feature_version)
        window_size = settings.default_window_size

        # Find symbols with enough data but no segment for this date
        sql = text("""
            SELECT DISTINCT db.symbol
            FROM daily_bar db
            WHERE db.trade_date <= :run_date
            AND NOT EXISTS (
                SELECT 1 FROM segment_index si
                WHERE si.symbol = db.symbol
                AND si.end_date = :run_date
                AND si.window_size = :window_size
                AND si.feature_version = :feature_version
            )
            GROUP BY db.symbol
            HAVING COUNT(*) >= :window_size
        """)
        symbols = [
            row[0]
            for row in self.db.execute(sql, {
                "run_date": run_date,
                "window_size": window_size,
                "feature_version": calculator.version,
            }).fetchall()
        ]

        count = 0
        for symbol in symbols:
            try:
                count += self._compute_symbol_feature(
                    symbol, run_date, window_size, calculator
                )
            except Exception as e:
                logger.warning(f"Feature compute failed for {symbol}: {e}")

        return count

    def _compute_symbol_feature(self, symbol, run_date, window_size, calculator):
        """Compute and store feature for a single symbol."""
        # Fetch recent bars
        sql = text("""
            SELECT trade_date, open, high, low, close, volume
            FROM daily_bar
            WHERE symbol = :symbol AND trade_date <= :run_date
            ORDER BY trade_date DESC
            LIMIT :limit
        """)
        rows = self.db.execute(sql, {
            "symbol": symbol,
            "run_date": run_date,
            "limit": window_size,
        }).fetchall()

        if len(rows) < window_size:
            return 0

        # Reverse to chronological order
        rows = rows[::-1]

        close = np.array([float(r[4]) for r in rows])
        volume = np.array([float(r[5]) for r in rows])
        high = np.array([float(r[2]) for r in rows])
        low = np.array([float(r[3]) for r in rows])

        start_date = rows[0][0]
        end_date = rows[-1][0]

        # Compute feature vector
        feature = calculator.calculate(close, volume, high, low)

        # Store segment index
        self.db.execute(text("""
            INSERT INTO segment_index (symbol, start_date, end_date, window_size, feature_version)
            VALUES (:symbol, :start_date, :end_date, :window_size, :feature_version)
            ON CONFLICT (symbol, end_date, window_size, feature_version) DO NOTHING
            RETURNING id
        """), {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "window_size": window_size,
            "feature_version": calculator.version,
        })
        self.db.commit()

        # Get the segment ID
        result = self.db.execute(text("""
            SELECT id FROM segment_index
            WHERE symbol = :symbol AND end_date = :end_date
            AND window_size = :window_size AND feature_version = :feature_version
        """), {
            "symbol": symbol,
            "end_date": end_date,
            "window_size": window_size,
            "feature_version": calculator.version,
        }).fetchone()

        if result is None:
            return 0

        segment_id = result[0]
        vector_str = "[" + ",".join(str(float(x)) for x in feature) + "]"
        norm = float(np.linalg.norm(feature))

        # Store feature vector
        self.db.execute(text("""
            INSERT INTO segment_feature (segment_id, feature_vector, norm)
            VALUES (:segment_id, CAST(:vector AS vector), :norm)
            ON CONFLICT (segment_id) DO UPDATE SET
                feature_vector = EXCLUDED.feature_vector,
                norm = EXCLUDED.norm
        """), {
            "segment_id": segment_id,
            "vector": vector_str,
            "norm": norm,
        })
        self.db.commit()

        # Create pending label
        self.db.execute(text("""
            INSERT INTO segment_future_label (segment_id)
            VALUES (:segment_id)
            ON CONFLICT (segment_id) DO NOTHING
        """), {"segment_id": segment_id})
        self.db.commit()

        return 1

    def _step_store_vectors(self, run_date: date, *, market: str = "CN") -> int:
        """Verify vectors are stored (already done in compute step)."""
        sql = text("""
            SELECT COUNT(*) FROM segment_feature sf
            JOIN segment_index si ON si.id = sf.segment_id
            WHERE si.end_date = :run_date
        """)
        result = self.db.execute(sql, {"run_date": run_date}).fetchone()
        return result[0] if result else 0

    def _step_backfill_labels(self, run_date: date, *, market: str = "CN") -> int:
        """Backfill future labels for segments that now have enough future data."""
        future_days = 20

        # Find segments needing label backfill
        target_date = run_date - timedelta(days=future_days + 10)  # Buffer for non-trading days

        sql = text("""
            SELECT sfl.segment_id, si.symbol, si.end_date
            FROM segment_future_label sfl
            JOIN segment_index si ON si.id = sfl.segment_id
            WHERE sfl.label_status = 'pending'
            AND si.end_date <= :target_date
        """)
        pending = self.db.execute(sql, {"target_date": target_date}).fetchall()

        count = 0
        for segment_id, symbol, end_date in pending:
            try:
                count += self._fill_label(segment_id, symbol, end_date, future_days)
            except Exception as e:
                logger.warning(f"Label backfill failed for segment {segment_id}: {e}")

        return count

    def _fill_label(self, segment_id, symbol, end_date, future_days):
        """Fill future label for a single segment."""
        # Get future bars
        sql = text("""
            SELECT trade_date, close
            FROM daily_bar
            WHERE symbol = :symbol AND trade_date > :end_date
            ORDER BY trade_date ASC
            LIMIT :limit
        """)
        rows = self.db.execute(sql, {
            "symbol": symbol,
            "end_date": end_date,
            "limit": future_days,
        }).fetchall()

        if len(rows) < future_days:
            self.db.execute(text("""
                UPDATE segment_future_label SET
                    label_status = 'na'
                WHERE segment_id = :segment_id
            """), {"segment_id": segment_id})
            self.db.commit()
            return 1

        prices = np.array([float(r[1]) for r in rows])
        base_row = self.db.execute(text("""
            SELECT close FROM daily_bar
            WHERE symbol = :symbol AND trade_date = :end_date
        """), {
            "symbol": symbol,
            "end_date": end_date,
        }).fetchone()
        base_price = float(base_row[0]) if base_row else float(prices[0])

        returns = (prices - base_price) / base_price
        final_return = returns[-1]
        max_drawdown = float(np.min(returns))
        max_profit = float(np.max(returns))

        # Simple Sharpe approximation
        daily_returns = np.diff(prices) / prices[:-1]
        sharpe = (float(np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252))
                  if np.std(daily_returns) > 1e-10 else 0.0)

        win_flag = final_return > 0

        self.db.execute(text("""
            UPDATE segment_future_label SET
                return_rate = :return_rate,
                max_drawdown = :max_drawdown,
                max_profit = :max_profit,
                sharpe_ratio = :sharpe_ratio,
                win_flag = :win_flag,
                label_status = 'filled',
                filled_at = NOW()
            WHERE segment_id = :segment_id
        """), {
            "segment_id": segment_id,
            "return_rate": round(float(final_return), 4),
            "max_drawdown": round(float(max_drawdown), 4),
            "max_profit": round(float(max_profit), 4),
            "sharpe_ratio": round(float(sharpe), 4),
            "win_flag": win_flag,
        })
        self.db.commit()

        return 1

    def _log_step(self, run_date, step_name, status, records=None, error=None, *, market: str = "CN"):
        """Log pipeline step execution."""
        now = datetime.now()
        if status == "running":
            self.db.execute(text("""
                INSERT INTO pipeline_run_log (run_date, market, step_name, status, started_at)
                VALUES (:run_date, :market, :step_name, :status, :started_at)
                ON CONFLICT (run_date, market, step_name) DO UPDATE SET
                    status = EXCLUDED.status,
                    started_at = EXCLUDED.started_at,
                    finished_at = NULL,
                    records_processed = NULL,
                    error_message = NULL
            """), {
                "run_date": run_date,
                "market": market,
                "step_name": step_name,
                "status": status,
                "started_at": now,
            })
        else:
            self.db.execute(text("""
                UPDATE pipeline_run_log SET
                    status = :status,
                    finished_at = :finished_at,
                    records_processed = :records,
                    error_message = :error
                WHERE run_date = :run_date AND market = :market AND step_name = :step_name
            """), {
                "run_date": run_date,
                "market": market,
                "step_name": step_name,
                "status": status,
                "finished_at": now,
                "records": records,
                "error": error,
            })
        self.db.commit()

    def get_status(self, run_date: date | None = None, *, market: str | None = None) -> list[dict]:
        """Get pipeline run status, optionally filtered by market."""
        params: dict = {}

        if run_date and market:
            sql = text("""
                SELECT step_name, market, status, started_at, finished_at, records_processed, error_message
                FROM pipeline_run_log
                WHERE run_date = :run_date AND market = :market
                ORDER BY started_at
            """)
            params = {"run_date": run_date, "market": market}
        elif run_date:
            sql = text("""
                SELECT step_name, market, status, started_at, finished_at, records_processed, error_message
                FROM pipeline_run_log
                WHERE run_date = :run_date
                ORDER BY started_at
            """)
            params = {"run_date": run_date}
        elif market:
            sql = text("""
                SELECT step_name, market, status, started_at, finished_at, records_processed, error_message
                FROM pipeline_run_log
                WHERE market = :market
                  AND run_date = (SELECT MAX(run_date) FROM pipeline_run_log WHERE market = :market)
                ORDER BY started_at
            """)
            params = {"market": market}
        else:
            sql = text("""
                SELECT step_name, market, status, started_at, finished_at, records_processed, error_message
                FROM pipeline_run_log
                WHERE run_date = (SELECT MAX(run_date) FROM pipeline_run_log)
                ORDER BY started_at
            """)

        rows = self.db.execute(sql, params).fetchall()

        return [
            {
                "step": row[0],
                "market": row[1],
                "status": row[2],
                "started_at": row[3].isoformat() if row[3] else None,
                "finished_at": row[4].isoformat() if row[4] else None,
                "records_processed": row[5],
                "error": row[6],
            }
            for row in rows
        ]
