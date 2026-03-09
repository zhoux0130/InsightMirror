from abc import ABC, abstractmethod
from datetime import date


class DataSource(ABC):
    @abstractmethod
    def fetch_daily(
        self, symbol: str, start_date: date | str, end_date: date | str
    ) -> list[dict]:
        """Fetch daily OHLCV data.

        Returns list of dicts with keys:
        symbol, trade_date, open, high, low, close, volume, amount, turnover, pct_change
        """
        ...

    @abstractmethod
    def get_stock_list(self) -> list[dict]:
        """Get list of available stocks."""
        ...

    def get_stock_metadata(self, symbol: str) -> dict:
        """Get metadata for a single stock.

        Implementations may return an empty dict when the source does not expose
        richer metadata without an additional query.
        """
        return {}
