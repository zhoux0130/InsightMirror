"""Admin API routes for pipeline management."""

import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, HTTPException
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


class InitRequest(BaseModel):
    market: str = "CN"                    # "CN" or "US"
    symbols: list[str] | None = None      # Optional; None = all stocks for CN
    start_date: str | None = None         # YYYY-MM-DD; default varies by market
    end_date: str | None = None           # YYYY-MM-DD; defaults to today
    skip_hnsw: bool = False


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


@router.post("/pipeline/init")
def trigger_init(req: InitRequest, background_tasks: BackgroundTasks):
    """Trigger full stock data initialization for CN or US market."""
    market = req.market.upper()
    if market not in ("CN", "US"):
        raise HTTPException(status_code=400, detail="market must be 'CN' or 'US'")

    if market == "US" and not req.symbols:
        raise HTTPException(
            status_code=400,
            detail="symbols is required for US market initialization",
        )

    # Resolve defaults
    start_date = req.start_date or ("2016-01-01" if market == "CN" else "2020-01-01")
    end_date = req.end_date
    symbols = req.symbols
    skip_hnsw = req.skip_hnsw
    run_date = date.today()

    def _log(step_name: str, status: str, records: int | None = None, error: str | None = None):
        """Log init progress to pipeline_run_log for status tracking."""
        from sqlalchemy import text as sa_text
        now = datetime.now()
        with get_db() as db:
            if status == "running":
                db.execute(sa_text("""
                    INSERT INTO pipeline_run_log (run_date, market, step_name, status, started_at)
                    VALUES (:run_date, :market, :step_name, :status, :started_at)
                    ON CONFLICT (run_date, market, step_name) DO UPDATE SET
                        status = EXCLUDED.status,
                        started_at = EXCLUDED.started_at,
                        finished_at = NULL,
                        records_processed = NULL,
                        error_message = NULL
                """), {
                    "run_date": run_date, "market": market,
                    "step_name": step_name, "status": status, "started_at": now,
                })
            else:
                db.execute(sa_text("""
                    UPDATE pipeline_run_log SET
                        status = :status, finished_at = :finished_at,
                        records_processed = :records, error_message = :error
                    WHERE run_date = :run_date AND market = :market AND step_name = :step_name
                """), {
                    "run_date": run_date, "market": market,
                    "step_name": step_name, "status": status,
                    "finished_at": now, "records": records, "error": error,
                })
            db.commit()

    def _run():
        _log("init", "running")
        try:
            if market == "US":
                from scripts.init_us_stocks import init_us_stocks
                result = init_us_stocks(
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    skip_hnsw=skip_hnsw,
                )
            else:
                from scripts.full_init import full_init
                result = full_init(
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    skip_hnsw=skip_hnsw,
                )
            _log("init", "success")
            logger.info("[Init] %s complete: %s", market, result)
        except Exception as e:
            _log("init", "failed", error=str(e))
            logger.error("[Init] %s failed: %s", market, e, exc_info=True)

    background_tasks.add_task(_run)

    return {
        "status": "accepted",
        "market": market,
        "symbols": symbols,
        "start_date": start_date,
        "end_date": end_date,
        "skip_hnsw": skip_hnsw,
        "message": f"{market} stock initialization started in background",
    }


@router.get("/pipeline/status")
def pipeline_status(run_date: str | None = None):
    rd = date.fromisoformat(run_date) if run_date else None
    with get_db() as db:
        orchestrator = PipelineOrchestrator(db)
        steps = orchestrator.get_status(rd)
    return {"steps": steps}
