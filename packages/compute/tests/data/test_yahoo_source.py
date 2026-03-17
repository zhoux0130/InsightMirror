from unittest.mock import patch

from app.data.yahoo import YahooFinanceDataSource
from app.data.factory import get_data_source


CHART_RESPONSE_AAPL = {
    "chart": {
        "result": [
            {
                "meta": {
                    "symbol": "AAPL",
                    "shortName": "Apple Inc.",
                    "exchangeName": "NMS",
                },
                "timestamp": [1704240600, 1704327000],
                "indicators": {
                    "quote": [
                        {
                            "open": [185.0, 186.5],
                            "high": [187.0, 188.0],
                            "low": [184.0, 185.5],
                            "close": [186.0, 187.5],
                            "volume": [50000000, 45000000],
                        }
                    ]
                },
            }
        ]
    }
}


def test_get_stock_metadata_parses_yahoo_response():
    with patch("app.data.yahoo._fetch_json", return_value=CHART_RESPONSE_AAPL):
        source = YahooFinanceDataSource()
        meta = source.get_stock_metadata("AAPL")

    assert meta["symbol"] == "AAPL"
    assert meta["name"] == "Apple Inc."
    assert meta["exchange"] == "NASDAQ"
    assert meta["market"] == "US"
    assert meta["source"] == "yahoo"
    assert meta["list_status"] == "listed"


def test_get_stock_metadata_returns_empty_on_no_result():
    empty_response = {"chart": {"result": []}}
    with patch("app.data.yahoo._fetch_json", return_value=empty_response):
        source = YahooFinanceDataSource()
        meta = source.get_stock_metadata("INVALID")

    assert meta == {}


def test_fetch_daily_parses_ohlcv_and_computes_pct_change():
    with patch("app.data.yahoo._fetch_json", return_value=CHART_RESPONSE_AAPL):
        source = YahooFinanceDataSource()
        bars = source.fetch_daily("AAPL", "2024-01-01", "2024-01-05")

    assert len(bars) == 2

    bar0 = bars[0]
    assert bar0["symbol"] == "AAPL"
    assert bar0["open"] == 185.0
    assert bar0["high"] == 187.0
    assert bar0["low"] == 184.0
    assert bar0["close"] == 186.0
    assert bar0["volume"] == 50000000
    assert bar0["market"] == "US"
    # First bar has no previous close -> pct_change = 0
    assert bar0["pct_change"] == 0.0

    bar1 = bars[1]
    assert bar1["close"] == 187.5
    # pct_change = (187.5 - 186.0) / 186.0 * 100
    expected_pct = round((187.5 - 186.0) / 186.0 * 100, 4)
    assert bar1["pct_change"] == expected_pct


def test_fetch_daily_skips_rows_with_none_values():
    response_with_nulls = {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "MSFT"},
                    "timestamp": [1704240600, 1704327000, 1704413400],
                    "indicators": {
                        "quote": [
                            {
                                "open": [370.0, None, 375.0],
                                "high": [372.0, None, 377.0],
                                "low": [369.0, None, 374.0],
                                "close": [371.0, None, 376.0],
                                "volume": [30000000, 0, 28000000],
                            }
                        ]
                    },
                }
            ]
        }
    }

    with patch("app.data.yahoo._fetch_json", return_value=response_with_nulls):
        source = YahooFinanceDataSource()
        bars = source.fetch_daily("MSFT", "2024-01-01", "2024-01-05")

    # Middle row has None values and should be skipped
    assert len(bars) == 2
    assert bars[0]["close"] == 371.0
    assert bars[1]["close"] == 376.0


def test_factory_returns_yahoo_source():
    source = get_data_source("yahoo")
    assert isinstance(source, YahooFinanceDataSource)


def test_fetch_json_retries_on_429():
    """Verify _fetch_json retries when receiving HTTP 429."""
    from unittest.mock import MagicMock
    from app.data.yahoo import _fetch_json

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429

    mock_resp_ok = MagicMock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.raise_for_status = MagicMock()
    mock_resp_ok.json.return_value = {"chart": {"result": []}}

    with patch("app.data.yahoo.requests.get", side_effect=[mock_resp_429, mock_resp_ok]):
        with patch("app.data.yahoo.time.sleep"):
            result = _fetch_json("https://example.com")

    assert result == {"chart": {"result": []}}
