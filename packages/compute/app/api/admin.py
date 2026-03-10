"""Admin API routes for pipeline management."""

import logging
from datetime import date, timedelta
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.core.pipeline.orchestrator import PipelineOrchestrator
from app.db.connection import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compute/v1", tags=["admin"])


class PipelineRequest(BaseModel):
    run_date: str | None = None  # YYYY-MM-DD format


class BackfillRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD


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


@router.post("/pipeline/backfill")
def backfill(body: BackfillRequest, background_tasks: BackgroundTasks):
    """Run the EOD pipeline for each trading day in [start_date, end_date]."""
    start = date.fromisoformat(body.start_date)
    end = date.fromisoformat(body.end_date)

    def _run():
        results = {}
        current = start
        while current <= end:
            # Skip weekends (Saturday=5, Sunday=6)
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            logger.info(f"[Backfill] Running EOD for {current}")
            try:
                with get_db() as db:
                    orch = PipelineOrchestrator(db)
                    result = orch.run_eod(current)
                results[current.isoformat()] = result
                logger.info(f"[Backfill] {current} done: {result}")
            except Exception as e:
                results[current.isoformat()] = {"error": str(e)}
                logger.error(f"[Backfill] {current} failed: {e}", exc_info=True)
            current += timedelta(days=1)
        logger.info(f"[Backfill] Complete: {len(results)} days processed")

    background_tasks.add_task(_run)

    return {
        "status": "accepted",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "message": "Backfill started in background",
    }


@router.get("/pipeline/status")
def pipeline_status(run_date: str | None = None):
    rd = date.fromisoformat(run_date) if run_date else None
    with get_db() as db:
        orchestrator = PipelineOrchestrator(db)
        steps = orchestrator.get_status(rd)
    return {"steps": steps}
