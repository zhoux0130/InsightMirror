"""Yahoo Finance data source for US stocks."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any

import requests

from app.data.base import DataSource

logger = logging.getLogger(__name__)

BASE_URL = "https://query1.finance.yahoo.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}

# Major US exchanges
EXCHANGE_MAP = {
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NYQ": "NYSE",
    "NYS": "NYSE",
    "PCX": "ARCA",
    "ASE": "AMEX",
    "BTS": "BATS",
}


def _ts_to_date(ts: int) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")


def _date_to_ts(d: date | str) -> int:
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    return int(datetime(d.year, d.month, d.day).timestamp())


def _fetch_json(url: str, retries: int = 2) -> dict:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                time.sleep(1 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Yahoo Finance request failed: {last_exc}")


class YahooFinanceDataSource(DataSource):
    """DataSource implementation backed by Yahoo Finance v8 API."""

    def get_stock_list(self) -> list[dict]:
        """Not applicable for Yahoo — use explicit symbol lists instead."""
        raise NotImplementedError(
            "Yahoo Finance does not provide a full stock list. "
            "Pass explicit symbols via --symbols."
        )

    def get_stock_metadata(self, symbol: str) -> dict:
        url = f"{BASE_URL}/v8/finance/chart/{symbol}?interval=1d&range=1d"
        data = _fetch_json(url)

        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return {}

        meta = result[0].get("meta", {})
        exchange_code = meta.get("exchangeName", "")
        exchange = EXCHANGE_MAP.get(exchange_code, exchange_code)

        return {
            "symbol": meta.get("symbol", symbol),
            "name": meta.get("shortName") or meta.get("longName") or symbol,
            "exchange": exchange,
            "list_date": None,
            "delist_date": None,
            "list_status": "listed",
            "source": "yahoo",
            "market": "US",
        }

    def fetch_daily(
        self,
        symbol: str,
        start_date: date | str,
        end_date: date | str,
    ) -> list[dict]:
        period1 = _date_to_ts(start_date)
        # Add 1 day to make end_date inclusive
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        period2 = int(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59).timestamp())

        url = (
            f"{BASE_URL}/v8/finance/chart/{symbol}"
            f"?period1={period1}&period2={period2}&interval=1d&events=history"
        )
        data = _fetch_json(url)

        chart_result = (data.get("chart") or {}).get("result") or []
        if not chart_result:
            logger.warning("No chart data for %s", symbol)
            return []

        result = chart_result[0]
        timestamps: list[int] = result.get("timestamp") or []
        quotes = (result.get("indicators") or {}).get("quote") or [{}]
        q = quotes[0] if quotes else {}

        rows: list[dict] = []
        prev_close: float | None = None

        for i, ts in enumerate(timestamps):
            o = q.get("open", [None])[i] if i < len(q.get("open", [])) else None
            h = q.get("high", [None])[i] if i < len(q.get("high", [])) else None
            lo = q.get("low", [None])[i] if i < len(q.get("low", [])) else None
            c = q.get("close", [None])[i] if i < len(q.get("close", [])) else None
            v = q.get("volume", [0])[i] if i < len(q.get("volume", [])) else 0

            if any(x is None for x in (o, h, lo, c)):
                continue

            pct_change = round((c - prev_close) / prev_close * 100, 4) if prev_close else 0.0

            rows.append({
                "symbol": symbol,
                "trade_date": _ts_to_date(ts),
                "market": "US",
                "open": round(o, 4),
                "high": round(h, 4),
                "low": round(lo, 4),
                "close": round(c, 4),
                "volume": int(v or 0),
                "amount": 0,
                "turnover": 0,
                "pct_change": pct_change,
            })
            prev_close = c

        return rows
