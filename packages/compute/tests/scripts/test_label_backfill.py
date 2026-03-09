from datetime import date

from scripts.backfill_full_labels import compute_future_label


def test_compute_future_label_uses_trading_day_window():
    future_rows = [
        {
            "trade_date": date(2024, 1, 2 + offset),
            "close": price,
        }
        for offset, price in enumerate(
            [
                100.0,
                102.0,
                101.0,
                104.0,
                106.0,
                108.0,
                110.0,
                109.0,
                111.0,
                112.0,
                113.0,
                114.0,
                116.0,
                118.0,
                117.0,
                119.0,
                121.0,
                122.0,
                123.0,
                125.0,
            ]
        )
    ]

    label = compute_future_label(segment_id=1, future_rows=future_rows, future_days=20)

    assert label["segment_id"] == 1
    assert label["label_status"] == "filled"
    assert label["return_rate"] == 0.25
    assert label["max_drawdown"] == 0.0
    assert label["max_profit"] == 0.25
    assert label["win_flag"] is True


def test_compute_future_label_marks_na_when_history_is_insufficient():
    future_rows = [{"trade_date": date(2024, 1, 2), "close": 100.0}] * 19

    label = compute_future_label(segment_id=2, future_rows=future_rows, future_days=20)

    assert label == {
        "segment_id": 2,
        "label_status": "na",
    }
