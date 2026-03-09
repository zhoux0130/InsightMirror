from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from app.data.base import DataSource


def canonicalize_a_share_symbol(symbol: str) -> str:
    raw = symbol.strip().upper()
    if raw.endswith((".SZ", ".SH")):
        return raw
    if raw.startswith(("SZ", "SH")) and len(raw) == 8:
        return f"{raw[2:]}.{raw[:2]}"

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) != 6:
        raise ValueError(f"Unsupported A-share symbol: {symbol}")

    suffix = "SH" if digits.startswith(("5", "6", "9")) else "SZ"
    return f"{digits}.{suffix}"


def infer_exchange(symbol: str) -> str:
    canonical = canonicalize_a_share_symbol(symbol)
    return "SSE" if canonical.endswith(".SH") else "SZSE"


def to_vendor_symbol(symbol: str) -> str:
    canonical = canonicalize_a_share_symbol(symbol)
    prefix = "sh" if canonical.endswith(".SH") else "sz"
    return f"{prefix}{canonical.split('.')[0]}"


def _format_akshare_date(value: date | str) -> str:
    if isinstance(value, str):
        return value.replace("-", "")
    return value.strftime("%Y%m%d")


def _parse_optional_date(value: Any) -> date | None:
    if value in (None, "", "-", "--"):
        return None
    text = str(value).strip()
    if text.isdigit() and len(text) == 8:
        return datetime.strptime(text, "%Y%m%d").date()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class AKShareDataSource(DataSource):
    def __init__(self, client: Any | None = None):
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import akshare as ak

            self._client = ak
        return self._client

    def get_stock_list(self) -> list[dict]:
        frame = self.client.stock_info_a_code_name()
        if frame is None or frame.empty:
            return []

        rows: list[dict] = []
        for record in frame.to_dict("records"):
            symbol = canonicalize_a_share_symbol(record["code"])
            rows.append(
                {
                    "symbol": symbol,
                    "name": str(record["name"]).strip(),
                    "exchange": infer_exchange(symbol),
                    "list_status": "listed",
                    "source": "akshare",
                }
            )
        return rows

    def get_stock_metadata(self, symbol: str) -> dict:
        code = canonicalize_a_share_symbol(symbol).split(".")[0]
        frame = self.client.stock_individual_info_em(symbol=code)
        if frame is None or frame.empty:
            return {}

        values = {}
        for row in frame.to_dict("records"):
            item = str(row.get("item") or row.get("项目") or "").strip()
            value = row.get("value") if "value" in row else row.get("值")
            if item:
                values[item] = value

        return {
            "symbol": canonicalize_a_share_symbol(code),
            "name": values.get("股票简称") or values.get("简称") or values.get("股票名称"),
            "exchange": infer_exchange(code),
            "list_date": _parse_optional_date(values.get("上市时间") or values.get("上市日期")),
            "delist_date": _parse_optional_date(values.get("退市时间") or values.get("退市日期")),
            "list_status": "delisted" if values.get("退市时间") or values.get("退市日期") else "listed",
            "source": "akshare",
        }

    def fetch_daily_frame(
        self,
        symbol: str,
        start_date: date | str,
        end_date: date | str,
        adjust: str = "",
    ) -> pd.DataFrame:
        canonical = canonicalize_a_share_symbol(symbol)
        code = canonical.split(".")[0]
        try:
            frame = self.client.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=_format_akshare_date(start_date),
                end_date=_format_akshare_date(end_date),
                adjust=adjust,
            )
        except Exception:
            frame = self._fetch_daily_frame_from_sina(
                symbol=canonical,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        if frame is None:
            return pd.DataFrame()
        return frame.copy()

    def _fetch_daily_frame_from_sina(
        self,
        symbol: str,
        start_date: date | str,
        end_date: date | str,
        adjust: str = "",
    ) -> pd.DataFrame:
        market_symbol = to_vendor_symbol(symbol)
        frame = self.client.stock_zh_a_daily(
            symbol=market_symbol,
            start_date=_format_akshare_date(start_date),
            end_date=_format_akshare_date(end_date),
            adjust=adjust,
        )
        if frame is None or frame.empty:
            return pd.DataFrame()

        normalized = frame.copy()
        normalized["日期"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
        normalized["开盘"] = pd.to_numeric(normalized["open"], errors="coerce")
        normalized["最高"] = pd.to_numeric(normalized["high"], errors="coerce")
        normalized["最低"] = pd.to_numeric(normalized["low"], errors="coerce")
        normalized["收盘"] = pd.to_numeric(normalized["close"], errors="coerce")
        normalized["成交量"] = pd.to_numeric(normalized["volume"], errors="coerce")
        normalized["成交额"] = pd.to_numeric(normalized["amount"], errors="coerce")
        normalized["换手率"] = pd.to_numeric(normalized.get("turnover"), errors="coerce")
        pct_change = normalized["收盘"].pct_change().fillna(0) * 100
        normalized["涨跌幅"] = pct_change.round(4)
        return normalized[
            ["日期", "开盘", "最高", "最低", "收盘", "成交量", "成交额", "换手率", "涨跌幅"]
        ]

    def fetch_daily(
        self,
        symbol: str,
        start_date: date | str,
        end_date: date | str,
    ) -> list[dict]:
        frame = self.fetch_daily_frame(symbol, start_date, end_date)
        if frame.empty:
            return []

        canonical = canonicalize_a_share_symbol(symbol)
        rows = []
        for row in frame.sort_values("日期").to_dict("records"):
            rows.append(
                {
                    "symbol": canonical,
                    "trade_date": str(row["日期"]),
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "close": float(row["收盘"]),
                    "volume": int(float(row.get("成交量", 0) or 0)),
                    "amount": float(row.get("成交额", 0) or 0),
                    "turnover": float(row.get("换手率", 0) or 0),
                    "pct_change": float(row.get("涨跌幅", 0) or 0),
                }
            )
        return rows
