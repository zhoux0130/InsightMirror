"""Admin API routes for pipeline management."""

from datetime import date
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.core.pipeline.orchestrator import PipelineOrchestrator
from app.db.connection import get_db

router = APIRouter(prefix="/compute/v1", tags=["admin"])


class PipelineRequest(BaseModel):
    run_date: str | None = None  # YYYY-MM-DD format


@router.post("/pipeline/eod")
def trigger_eod(req: PipelineRequest, background_tasks: BackgroundTasks):
    run_date = date.fromisoformat(req.run_date) if req.run_date else date.today()

    def _run():
        with get_db() as db:
            orchestrator = PipelineOrchestrator(db)
            orchestrator.run_eod(run_date)

    background_tasks.add_task(_run)

    return {
        "status": "accepted",
        "run_date": run_date.isoformat(),
        "message": "EOD pipeline started in background",
    }


@router.get("/pipeline/status")
def pipeline_status(run_date: str | None = None):
    rd = date.fromisoformat(run_date) if run_date else None
    with get_db() as db:
        orchestrator = PipelineOrchestrator(db)
        steps = orchestrator.get_status(rd)
    return {"steps": steps}
