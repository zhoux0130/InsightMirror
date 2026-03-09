from datetime import date

import pandas as pd

from scripts.init_security_master import build_security_master_rows
from scripts.load_daily_bars import normalize_daily_bars_frame
from scripts.build_full_segments import build_segments_for_history


def test_normalize_daily_bars_frame_sorts_filters_and_deduplicates():
    raw = pd.DataFrame(
        [
            {
                "日期": "2024-01-03",
                "开盘": 150.0,
                "收盘": 153.0,
                "最高": 155.0,
                "最低": 149.5,
                "成交量": 1000000,
                "成交额": 150000000.0,
                "换手率": 1.5,
                "涨跌幅": 2.0,
            },
            {
                "日期": "2024-01-02",
                "开盘": 148.0,
                "收盘": 150.0,
                "最高": 151.0,
                "最低": 147.2,
                "成交量": 900000,
                "成交额": 140000000.0,
                "换手率": 1.2,
                "涨跌幅": 1.35,
            },
            {
                "日期": "2024-01-02",
                "开盘": 148.0,
                "收盘": 150.0,
                "最高": 151.0,
                "最低": 147.2,
                "成交量": 900000,
                "成交额": 140000000.0,
                "换手率": 1.2,
                "涨跌幅": 1.35,
            },
            {
                "日期": "2018-06-08",
                "开盘": 1.0,
                "收盘": 1.0,
                "最高": 1.0,
                "最低": 1.0,
                "成交量": 1,
                "成交额": 1.0,
                "换手率": 0.0,
                "涨跌幅": 0.0,
            },
        ]
    )

    normalized = normalize_daily_bars_frame(
        symbol="300750.SZ",
        raw=raw,
        list_date=date(2018, 6, 11),
    )

    assert normalized.to_dict("records") == [
        {
            "symbol": "300750.SZ",
            "trade_date": date(2024, 1, 2),
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
            "trade_date": date(2024, 1, 3),
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


def test_build_segments_for_history_creates_feature_and_pending_label():
    start = date(2024, 1, 2)
    history = []
    for offset in range(60):
        history.append(
            {
                "symbol": "300750.SZ",
                "trade_date": start.fromordinal(start.toordinal() + offset),
                "open": 100.0 + offset,
                "high": 101.0 + offset,
                "low": 99.0 + offset,
                "close": 100.0 + offset,
                "volume": 1000000 + offset,
                "amount": 100000000.0 + offset,
                "turnover": 1.0,
                "pct_change": 0.5,
            }
        )

    segments, features, labels = build_segments_for_history(
        symbol="300750.SZ",
        rows=history,
        feature_version="v1",
        window_size=60,
        segment_id_start=100,
    )

    assert segments == [
        {
            "id": 100,
            "symbol": "300750.SZ",
            "start_date": history[0]["trade_date"],
            "end_date": history[-1]["trade_date"],
            "window_size": 60,
            "feature_version": "v1",
        }
    ]
    assert len(features) == 1
    assert features[0]["segment_id"] == 100
    assert len(features[0]["feature"]) == 182
    assert labels == [
        {
            "segment_id": 100,
            "future_days": 20,
            "label_status": "pending",
        }
    ]


def test_build_security_master_rows_falls_back_when_metadata_fetch_fails(monkeypatch):
    class FailingSource:
        def get_stock_list(self):
            return [
                {
                    "symbol": "300750.SZ",
                    "name": "宁德时代",
                    "exchange": "SZSE",
                    "list_status": "listed",
                    "source": "akshare",
                }
            ]

        def get_stock_metadata(self, _symbol):
            raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(
        "scripts.init_security_master.get_data_source",
        lambda: FailingSource(),
    )

    rows = build_security_master_rows(symbols=["300750.SZ"])

    assert rows == [
        {
            "symbol": "300750.SZ",
            "name": "宁德时代",
            "exchange": "SZSE",
            "list_status": "listed",
            "source": "akshare",
            "list_date": None,
            "delist_date": None,
        }
    ]
