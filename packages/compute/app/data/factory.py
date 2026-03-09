from app.config import settings
from app.data.akshare import AKShareDataSource
from app.data.base import DataSource


class UnsupportedDataSourceError(ValueError):
    pass


def get_data_source() -> DataSource:
    source_name = settings.data_source.lower()
    if source_name == "akshare":
        return AKShareDataSource()
    if source_name == "tushare":
        from app.data.tushare import TushareDataSource

        return TushareDataSource()
    raise UnsupportedDataSourceError(f"Unsupported data source: {settings.data_source}")
