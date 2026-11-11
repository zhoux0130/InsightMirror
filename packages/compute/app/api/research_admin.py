"""Local console for transcript-extraction usage, estimated cost, quality and human feedback on claims."""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.research.ledger import VERDICTS, load_models
from app.research.runs import claims_for_document, compare_models, ledger_at, research_root

PASSWORD_ENV = "RESEARCH_ADMIN_PASSWORD"
LOCAL_ENV = "RESEARCH_ADMIN_LOCAL"
USERNAME = "research"
_basic = HTTPBasic(auto_error=False)


def require_access(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    """Shows course text and accepts writes, so it is off unless a password is set or it runs localhost-only."""
    password = os.environ.get(PASSWORD_ENV, "")
    if not password:
        if os.environ.get(LOCAL_ENV) == "1":
            return
        raise HTTPException(404)
    if credentials is None or not (
        secrets.compare_digest(credentials.username.encode(), USERNAME.encode())
        and secrets.compare_digest(credentials.password.encode(), password.encode())
    ):
        raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="research", charset="UTF-8"'})


router = APIRouter(prefix="/compute/v1/research", tags=["research-admin"], dependencies=[Depends(require_access)])
PAGE = Path(__file__).with_name("research_admin.html")


def _ledger():
    return ledger_at(research_root(settings.raw_data_dir))


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page() -> str:
    return PAGE.read_text(encoding="utf-8")


@router.get("/usage")
def usage() -> dict[str, Any]:
    notes = {m.id: {"model": m.model, "price_note": m.price_note} for m in load_models().values()}
    return {"models": _ledger().usage_by_model(), "catalog": notes}


@router.get("/runs")
def runs(limit: int = 100) -> dict[str, Any]:
    rows = _ledger().runs(limit)
    for row in rows:
        row.pop("metrics_json", None)
        row.pop("result_path", None)
    return {"runs": rows}


@router.get("/documents")
def documents() -> dict[str, list[str]]:
    return {"documents": _ledger().documents()}


@router.get("/compare")
def compare(doc_id: str) -> dict[str, Any]:
    return compare_models(_ledger(), doc_id)


@router.get("/claims")
def claims(doc_id: str) -> dict[str, Any]:
    """Includes verbatim course text; this console must stay on localhost."""
    return claims_for_document(_ledger(), doc_id)


WRONG_FIELDS = ("entity", "meaning", "direction", "target", "window", "attribution", "condition", "other")


class FeedbackIn(BaseModel):
    doc_id: str
    model_id: str
    claim_id: str
    verdict: str = ""
    wrong_fields: list[str] = Field(default_factory=list)
    note: str = Field("", max_length=2000)


@router.post("/feedback")
def save_feedback(body: FeedbackIn, request: Request) -> dict[str, bool]:
    """JSON only: with no CORS configured, a browser will not send this from another site."""
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(415, "application/json required")
    if body.verdict and body.verdict not in VERDICTS:
        raise HTTPException(400, "unknown verdict")
    if any(f not in WRONG_FIELDS for f in body.wrong_fields):
        raise HTTPException(400, "unknown wrong field")
    claim = next(
        (c for c in claims_for_document(_ledger(), body.doc_id)["claims"]
         if c["model_id"] == body.model_id and c["claim_id"] == body.claim_id),
        None,
    )
    if claim is None:
        raise HTTPException(404, "claim not found in the latest run")
    _ledger().save_feedback(
        doc_id=body.doc_id, model_id=body.model_id, claim_id=body.claim_id, quote=claim["quote"],
        verdict=body.verdict, wrong_fields=body.wrong_fields if body.verdict in ("partial", "wrong") else [],
        note=body.note.strip(),
    )
    return {"ok": True}
