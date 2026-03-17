from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router

# Lightweight app for testing — avoids importing app.main (which pulls in apscheduler)
_app = FastAPI()
_app.include_router(router)
client = TestClient(_app)


@patch("app.api.admin.get_db")
def test_trigger_eod_passes_market_to_orchestrator(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    resp = client.post("/compute/v1/pipeline/eod", json={
        "run_date": "2024-06-01",
        "market": "US",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["market"] == "US"
    assert body["run_date"] == "2024-06-01"
    assert body["status"] == "accepted"


@patch("app.api.admin.get_db")
def test_trigger_eod_defaults_to_cn(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    resp = client.post("/compute/v1/pipeline/eod", json={})

    assert resp.status_code == 200
    assert resp.json()["market"] == "CN"


@patch("app.api.admin.get_db")
def test_backfill_passes_market(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    resp = client.post("/compute/v1/pipeline/backfill", json={
        "start_date": "2024-06-01",
        "end_date": "2024-06-05",
        "market": "US",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["market"] == "US"
    assert body["status"] == "accepted"


@patch("app.api.admin.get_db")
def test_pipeline_status_accepts_market_param(mock_get_db):
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = []
    mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    resp = client.get("/compute/v1/pipeline/status", params={
        "run_date": "2024-06-01",
        "market": "US",
    })

    assert resp.status_code == 200
    assert resp.json() == {"steps": []}
    call_args = mock_db.execute.call_args
    assert call_args[0][1]["market"] == "US"


def test_trigger_eod_rejects_invalid_market():
    resp = client.post("/compute/v1/pipeline/eod", json={
        "market": "JP",
    })
    assert resp.status_code == 422
