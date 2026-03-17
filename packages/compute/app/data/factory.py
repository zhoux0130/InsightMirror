from app.config import settings
from app.data.akshare import AKShareDataSource
from app.data.base import DataSource


class UnsupportedDataSourceError(ValueError):
    pass


def get_data_source(source_name: str | None = None) -> DataSource:
    name = (source_name or settings.data_source).lower()
    if name == "akshare":
        return AKShareDataSource()
    if name == "tushare":
        from app.data.tushare import TushareDataSource

        return TushareDataSource()
    if name == "yahoo":
        from app.data.yahoo import YahooFinanceDataSource

        return YahooFinanceDataSource()
    raise UnsupportedDataSourceError(f"Unsupported data source: {name}")
