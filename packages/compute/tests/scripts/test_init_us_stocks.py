from unittest.mock import patch, MagicMock

from scripts.init_us_stocks import (
    parse_us_symbols,
    init_us_security_master,
    fetch_us_daily_bars,
    init_us_stocks,
)


def test_parse_us_symbols():
    assert parse_us_symbols("AAPL,MSFT,TSLA") == ["AAPL", "MSFT", "TSLA"]
    assert parse_us_symbols(" aapl , msft ") == ["AAPL", "MSFT"]
    assert parse_us_symbols("GOOG") == ["GOOG"]
    assert parse_us_symbols(",,") == []


@patch("scripts.init_us_stocks.get_db")
@patch("scripts.init_us_stocks.YahooFinanceDataSource")
def test_init_us_security_master_upserts_metadata(mock_ds_cls, mock_get_db):
    mock_ds = MagicMock()
    mock_ds.get_stock_metadata.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "list_status": "listed",
    }
    mock_ds_cls.return_value = mock_ds

    mock_db = MagicMock()
    mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    result = init_us_security_master(["AAPL"])

    assert result == {"AAPL": "ok"}
    mock_ds.get_stock_metadata.assert_called_once_with("AAPL")
    mock_db.execute.assert_called_once()
    # Verify market='US' is passed
    call_args = mock_db.execute.call_args[0][1]
    assert call_args["market"] == "US"
    assert call_args["source"] == "yahoo"


@patch("scripts.init_us_stocks.get_db")
@patch("scripts.init_us_stocks.YahooFinanceDataSource")
def test_init_us_security_master_handles_not_found(mock_ds_cls, mock_get_db):
    mock_ds = MagicMock()
    mock_ds.get_stock_metadata.return_value = {}
    mock_ds_cls.return_value = mock_ds

    mock_get_db.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    result = init_us_security_master(["INVALID"])
    assert result == {"INVALID": "not_found"}


@patch("scripts.init_us_stocks.time.sleep")
@patch("scripts.init_us_stocks.get_db")
@patch("scripts.init_us_stocks.YahooFinanceDataSource")
def test_fetch_us_daily_bars_stores_bars(mock_ds_cls, mock_get_db, mock_sleep):
    mock_ds = MagicMock()
    mock_ds.fetch_daily.return_value = [
        {
            "symbol": "AAPL",
            "trade_date": "2024-01-02",
            "open": 185.0,
            "high": 187.0,
            "low": 184.0,
            "close": 186.0,
            "volume": 50000000,
            "amount": 0,
            "turnover": 0,
            "pct_change": 0.0,
        },
    ]
    mock_ds_cls.return_value = mock_ds

    mock_db = MagicMock()
    mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    result = fetch_us_daily_bars(["AAPL"], "2024-01-01", "2024-01-05")

    assert result == {"AAPL": 1}
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][1]
    assert call_args["market"] == "US"
    assert call_args["symbol"] == "AAPL"


@patch("scripts.init_us_stocks.build_hnsw_index")
@patch("scripts.init_us_stocks.backfill_full_labels")
@patch("scripts.init_us_stocks.build_full_segments")
@patch("scripts.init_us_stocks.fetch_us_daily_bars")
@patch("scripts.init_us_stocks.init_us_security_master")
def test_init_us_stocks_runs_all_steps(
    mock_sm, mock_bars, mock_segments, mock_labels, mock_hnsw
):
    mock_sm.return_value = {"AAPL": "ok"}
    mock_bars.return_value = {"AAPL": 250}
    mock_segments.return_value = {"rows": 190}
    mock_labels.return_value = {"filled": 180}

    result = init_us_stocks(
        symbols=["AAPL"],
        start_date="2024-01-01",
        skip_hnsw=False,
    )

    mock_sm.assert_called_once_with(["AAPL"])
    mock_bars.assert_called_once_with(["AAPL"], "2024-01-01", None)
    mock_segments.assert_called_once_with(symbols=["AAPL"])
    mock_labels.assert_called_once_with(symbols=["AAPL"])
    mock_hnsw.assert_called_once()

    assert result["security_master"] == {"AAPL": "ok"}
    assert result["daily_bars"] == {"AAPL": 250}


@patch("scripts.init_us_stocks.build_hnsw_index")
@patch("scripts.init_us_stocks.backfill_full_labels")
@patch("scripts.init_us_stocks.build_full_segments")
@patch("scripts.init_us_stocks.fetch_us_daily_bars")
@patch("scripts.init_us_stocks.init_us_security_master")
def test_init_us_stocks_skip_hnsw(
    mock_sm, mock_bars, mock_segments, mock_labels, mock_hnsw
):
    mock_sm.return_value = {}
    mock_bars.return_value = {}
    mock_segments.return_value = {"rows": 0}
    mock_labels.return_value = {}

    init_us_stocks(symbols=["TSLA"], start_date="2024-01-01", skip_hnsw=True)

    mock_hnsw.assert_not_called()
