from types import SimpleNamespace

import pandas as pd

from app.data.akshare import AKShareDataSource, canonicalize_a_share_symbol


def test_canonicalize_a_share_symbol_maps_sz_and_sh_codes():
    assert canonicalize_a_share_symbol("300750") == "300750.SZ"
    assert canonicalize_a_share_symbol("600519") == "600519.SH"
    assert canonicalize_a_share_symbol("000001.SZ") == "000001.SZ"


def test_akshare_source_maps_stock_list_and_history():
    fake_akshare = SimpleNamespace(
        stock_info_a_code_name=lambda: pd.DataFrame(
            [
                {"code": "300750", "name": "宁德时代"},
                {"code": "600519", "name": "贵州茅台"},
            ]
        ),
        stock_zh_a_hist=lambda **_: pd.DataFrame(
            [
                {
                    "日期": "2024-01-03",
                    "开盘": 150.0,
                    "收盘": 153.0,
                    "最高": 155.0,
                    "最低": 149.5,
                    "成交量": 1000000,
                    "成交额": 150000000.0,
                    "振幅": 3.67,
                    "涨跌幅": 2.0,
                    "涨跌额": 3.0,
                    "换手率": 1.5,
                },
                {
                    "日期": "2024-01-02",
                    "开盘": 148.0,
                    "收盘": 150.0,
                    "最高": 151.0,
                    "最低": 147.2,
                    "成交量": 900000,
                    "成交额": 140000000.0,
                    "振幅": 2.57,
                    "涨跌幅": 1.35,
                    "涨跌额": 2.0,
                    "换手率": 1.2,
                },
            ]
        ),
    )

    source = AKShareDataSource(client=fake_akshare)

    stock_list = source.get_stock_list()
    assert stock_list == [
        {
            "symbol": "300750.SZ",
            "name": "宁德时代",
            "exchange": "SZSE",
            "list_status": "listed",
            "source": "akshare",
        },
        {
            "symbol": "600519.SH",
            "name": "贵州茅台",
            "exchange": "SSE",
            "list_status": "listed",
            "source": "akshare",
        },
    ]

    history = source.fetch_daily("300750.SZ", "2024-01-01", "2024-01-31")
    assert history == [
        {
            "symbol": "300750.SZ",
            "trade_date": "2024-01-02",
            "open": 148.0,
            "high": 151.0,
            "low": 147.2,
            "close": 150.0,
            "volume": 900000,
            "amount": 140000000.0,
            "turnover": 1.2,
            "pct_change": 1.35,
        },
        {
            "symbol": "300750.SZ",
            "trade_date": "2024-01-03",
            "open": 150.0,
            "high": 155.0,
            "low": 149.5,
            "close": 153.0,
            "volume": 1000000,
            "amount": 150000000.0,
            "turnover": 1.5,
            "pct_change": 2.0,
        },
    ]


def test_akshare_source_falls_back_to_sina_daily_when_hist_endpoint_fails():
    def raise_hist_failure(**_kwargs):
        raise RuntimeError("eastmoney unavailable")

    fake_akshare = SimpleNamespace(
        stock_info_a_code_name=lambda: pd.DataFrame(
            [{"code": "000001", "name": "平安银行"}]
        ),
        stock_zh_a_hist=raise_hist_failure,
        stock_zh_a_daily=lambda **_kwargs: pd.DataFrame(
            [
                {
                    "date": "2016-01-04",
                    "open": 12.0,
                    "high": 12.03,
                    "low": 11.23,
                    "close": 11.33,
                    "volume": 56349788.0,
                    "amount": 660376128.0,
                    "turnover": 0.47,
                },
                {
                    "date": "2016-01-05",
                    "open": 11.27,
                    "high": 11.57,
                    "low": 11.15,
                    "close": 11.40,
                    "volume": 66326996.0,
                    "amount": 755531328.0,
                    "turnover": 0.56,
                },
            ]
        ),
    )

    source = AKShareDataSource(client=fake_akshare)

    history = source.fetch_daily("000001.SZ", "2016-01-01", "2016-01-31")

    assert history == [
        {
            "symbol": "000001.SZ",
            "trade_date": "2016-01-04",
            "open": 12.0,
            "high": 12.03,
            "low": 11.23,
            "close": 11.33,
            "volume": 56349788,
            "amount": 660376128.0,
            "turnover": 0.47,
            "pct_change": 0.0,
        },
        {
            "symbol": "000001.SZ",
            "trade_date": "2016-01-05",
            "open": 11.27,
            "high": 11.57,
            "low": 11.15,
            "close": 11.4,
            "volume": 66326996,
            "amount": 755531328.0,
            "turnover": 0.56,
            "pct_change": 0.6178,
        },
    ]
