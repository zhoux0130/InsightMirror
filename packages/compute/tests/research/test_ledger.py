from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import research_admin
from app.config import settings
from app.research.ledger import Ledger, MeteredClient, Price, load_models
from app.research.llm import ModelCallError, Usage
from app.research.runs import compare_models, execute_run, run_metrics
from app.research.schemas import ClaimsOutput, ClaimVerdict, DocumentMap, ReviewOutput, SegmentSpan
from tests.research.helpers import block, draft

BLOCKS = [block("B001", "英伟达这家公司股价会大跌。")]
USAGE = Usage(input_tokens=1000, output_tokens=100, cache_read_tokens=500, cache_write_tokens=200)


class FakeProvider:
    def __init__(self, model="fake", direction="负面(看跌)", fail=False):
        self.model, self.direction, self.fail = model, direction, fail

    def call(self, *, system, user, output):
        if self.fail:
            raise ModelCallError("boom", Usage(output_tokens=3))
        if output is DocumentMap:
            span = SegmentSpan(start_block="B001", end_block="B001", topic="t", has_investment_view=True)
            return DocumentMap(main_theses=[], glossary=[], groups=[], likely_transcription_errors=[], segments=[span]), USAGE
        if output is ClaimsOutput:
            return ClaimsOutput(claims=[draft(direction=self.direction)]), USAGE
        return ReviewOutput(verdicts=[ClaimVerdict(index=0, supported=True, wrong_fields=[], note="")]), USAGE


def run(root, model_id="glm", doc="2026-10-29", **kwargs):
    provider = kwargs.pop("provider", FakeProvider())
    return execute_run(model_id=model_id, api_key="k", doc_id=doc, doc_date=doc, blocks=BLOCKS, root=root, provider=provider, **kwargs)


def test_catalog_has_the_three_models_and_no_secrets():
    models = load_models()
    assert set(models) == {"claude", "glm", "kimi"} and models["claude"].model == "claude-opus-5-5"
    assert all(m.key_env.endswith("_API_KEY") for m in models.values())


def test_cost_counts_each_token_class():
    price = Price("USD", input=4, output=20, cache_read=0.2, cache_write=5)
    assert price.cost(USAGE) == pytest.approx((1000 * 4 + 100 * 20 + 500 * 0.2 + 200 * 5) / 1_000_000)


def test_run_records_calls_cost_and_metrics(tmp_path):
    _, metrics = run(tmp_path)
    ledger = Ledger(tmp_path / "ledger.sqlite")
    usage = ledger.usage_by_model()[0]
    expected = load_models()["glm"].price.cost(USAGE) * 3
    assert (usage["model_id"], usage["calls"], usage["failed_calls"]) == ("glm", 3, 0)
    assert usage["estimated_cost"] == pytest.approx(expected)
    saved = ledger.runs()[0]
    assert saved["status"] == "ok" and saved["metrics"]["claims"] == 1 == metrics["auto"]
    assert saved["estimated_cost"] == pytest.approx(expected)


def test_resumed_run_is_not_billed_again(tmp_path):
    run(tmp_path)
    run(tmp_path)
    assert Ledger(tmp_path / "ledger.sqlite").usage_by_model()[0]["calls"] == 3


def test_failed_call_is_recorded_with_billed_tokens(tmp_path):
    with pytest.raises(ModelCallError):
        run(tmp_path, provider=FakeProvider(fail=True))
    ledger = Ledger(tmp_path / "ledger.sqlite")
    assert ledger.usage_by_model()[0]["failed_calls"] == 1 and ledger.usage_by_model()[0]["output_tokens"] == 3
    assert ledger.runs()[0]["status"] == "error"


def test_non_model_exception_is_recorded_without_leaking_detail(tmp_path):
    class Boom:
        model = "m"

        def call(self, **_):
            raise RuntimeError("secret-in-message")

    ledger = Ledger(tmp_path / "l.sqlite")
    client = MeteredClient(Boom(), load_models()["glm"], ledger, "r")
    with pytest.raises(RuntimeError):
        client.complete(system=[], user="u", output=ReviewOutput)
    with ledger._connect() as db:
        assert db.execute("select error from llm_call").fetchone()[0] == "RuntimeError"


def test_compare_flags_disagreement_and_ignores_trial_runs(tmp_path):
    run(tmp_path, "glm")
    run(tmp_path, "kimi", provider=FakeProvider(direction="正面(看涨)"))
    run(tmp_path, "claude", provider=FakeProvider(), max_segments=1)
    data = compare_models(Ledger(tmp_path / "ledger.sqlite"), "2026-10-29")
    assert data["models"] == ["glm", "kimi"] and data["rows"][0]["status"] == "有分歧"


def test_metrics_report_failed_traps(tmp_path):
    result, _ = run(tmp_path)
    metrics = run_metrics(result)
    assert metrics["traps_total"] == 9 and "spacex_condition" in metrics["traps_failed"]


def test_admin_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "raw_data_dir", str(tmp_path))
    monkeypatch.setenv("RESEARCH_ADMIN_LOCAL", "1")
    run(tmp_path / "research")
    app = FastAPI()
    app.include_router(research_admin.router)
    client = TestClient(app)
    assert "模型用量后台" in client.get("/compute/v1/research/admin").text
    assert client.get("/compute/v1/research/usage").json()["models"][0]["calls"] == 3
    row = client.get("/compute/v1/research/runs").json()["runs"][0]
    assert row["metrics"]["claims"] == 1 and "result_path" not in row
    assert client.get("/compute/v1/research/documents").json() == {"documents": ["2026-10-29"]}
    assert client.get("/compute/v1/research/compare", params={"doc_id": "2026-10-29"}).json()["models"] == ["glm"]
    claim = client.get("/compute/v1/research/claims", params={"doc_id": "2026-10-29"}).json()["claims"][0]
    assert claim["model_id"] == "glm" and claim["quote"] and claim["page"] and claim["route"] in ("auto", "review")


def test_feedback_is_saved_cleared_and_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "raw_data_dir", str(tmp_path))
    monkeypatch.setenv("RESEARCH_ADMIN_LOCAL", "1")
    run(tmp_path / "research")
    app = FastAPI()
    app.include_router(research_admin.router)
    client = TestClient(app)
    base = "/compute/v1/research"
    claim = client.get(base + "/claims", params={"doc_id": "2026-10-29"}).json()["claims"][0]
    key = {"doc_id": "2026-10-29", "model_id": claim["model_id"], "claim_id": claim["claim_id"]}

    ok = client.post(base + "/feedback", json={**key, "verdict": "wrong", "wrong_fields": ["direction"], "note": "其实是波动"})
    assert ok.status_code == 200
    saved = client.get(base + "/claims", params={"doc_id": "2026-10-29"}).json()["claims"][0]["feedback"]
    assert saved["verdict"] == "wrong" and saved["wrong_fields"] == ["direction"] and saved["note"] == "其实是波动"

    client.post(base + "/feedback", json={**key, "verdict": "correct", "wrong_fields": ["direction"]})
    assert client.get(base + "/claims", params={"doc_id": "2026-10-29"}).json()["claims"][0]["feedback"]["wrong_fields"] == []

    client.post(base + "/feedback", json={**key, "verdict": ""})
    assert client.get(base + "/claims", params={"doc_id": "2026-10-29"}).json()["claims"][0]["feedback"] is None

    assert client.post(base + "/feedback", json={**key, "verdict": "maybe"}).status_code == 400
    assert client.post(base + "/feedback", json={**key, "verdict": "wrong", "wrong_fields": ["x"]}).status_code == 400
    assert client.post(base + "/feedback", json={**key, "claim_id": "nope", "verdict": "wrong"}).status_code == 404
    import json
    body = json.dumps({**key, "verdict": "wrong"})
    form = client.post(base + "/feedback", content=body, headers={"content-type": "text/plain"})
    assert form.status_code in (415, 422)
    assert client.get(base + "/claims", params={"doc_id": "2026-10-29"}).json()["claims"][0]["feedback"] is None


def test_feedback_does_not_carry_over_to_a_different_claim_with_the_same_id(tmp_path):
    run(tmp_path)
    ledger = Ledger(tmp_path / "ledger.sqlite")
    claim = compare_and_claims(ledger)
    ledger.save_feedback(doc_id="2026-10-29", model_id=claim["model_id"], claim_id=claim["claim_id"],
                         quote="旧的另一句", verdict="correct", wrong_fields=[], note="")
    assert compare_and_claims(ledger)["feedback"] is None


def compare_and_claims(ledger):
    from app.research.runs import claims_for_document
    return claims_for_document(ledger, "2026-10-29")["claims"][0]


def _console(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "raw_data_dir", str(tmp_path))
    monkeypatch.delenv("RESEARCH_ADMIN_LOCAL", raising=False)
    monkeypatch.delenv("RESEARCH_ADMIN_PASSWORD", raising=False)
    run(tmp_path / "research")
    app = FastAPI()
    app.include_router(research_admin.router)
    return TestClient(app)


def test_console_is_off_without_a_password(tmp_path, monkeypatch):
    client = _console(tmp_path, monkeypatch)
    assert client.get("/compute/v1/research/admin").status_code == 404
    assert client.get("/compute/v1/research/claims", params={"doc_id": "2026-10-29"}).status_code == 404


def test_console_requires_the_password_when_set(tmp_path, monkeypatch):
    client = _console(tmp_path, monkeypatch)
    monkeypatch.setenv("RESEARCH_ADMIN_PASSWORD", "s3cret")
    page = "/compute/v1/research/admin"
    assert client.get(page).status_code == 401
    assert client.get(page, auth=("research", "wrong")).status_code == 401
    assert client.get(page, auth=("someone", "s3cret")).status_code == 401
    assert client.get(page, auth=("research", "s3cret")).status_code == 200


def test_ledger_moved_to_another_machine_still_finds_results(tmp_path):
    run(tmp_path / "research")
    ledger = Ledger(tmp_path / "research" / "ledger.sqlite")
    with ledger._connect() as db:
        stored = db.execute("select result_path from run").fetchone()[0]
        assert not stored.startswith("/")
    for legacy in ("/Users/elsewhere/data/raw/research/" + stored, "data/raw/research/" + stored):
        with ledger._connect() as db:
            db.execute("update run set result_path=?", (legacy,))
        path = next(iter(ledger.latest_results("2026-10-29").values()))
        assert Path(path).exists(), legacy
