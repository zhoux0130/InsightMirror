"""Tushare data source implementation."""

import logging
from datetime import date

from app.config import settings
from app.data.base import DataSource

logger = logging.getLogger(__name__)


class TushareDataSource(DataSource):
    def __init__(self):
        if not settings.tushare_token:
            raise ValueError("TUSHARE_TOKEN not configured")

        import tushare as ts
        ts.set_token(settings.tushare_token)
        self.pro = ts.pro_api()

    def fetch_daily(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict]:
        df = self.pro.daily(
            ts_code=symbol,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        if df is None or df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            result.append({
                "symbol": row["ts_code"],
                "trade_date": date(
                    int(row["trade_date"][:4]),
                    int(row["trade_date"][4:6]),
                    int(row["trade_date"][6:8]),
                ),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["vol"] * 100),  # Convert to shares
                "amount": float(row.get("amount", 0)) * 1000,  # Convert to yuan
                "turnover": float(row.get("turnover_rate", 0) or 0),
                "pct_change": float(row.get("pct_chg", 0) or 0),
            })
        return result

    def get_stock_list(self) -> list[dict]:
        df = self.pro.stock_basic(
            exchange="", list_status="L",
            fields="ts_code,symbol,name,area,industry,list_date"
        )
        return df.to_dict("records") if df is not None else []
