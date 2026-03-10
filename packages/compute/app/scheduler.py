"""Daily EOD pipeline scheduler using APScheduler."""

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.core.pipeline.orchestrator import PipelineOrchestrator
from app.db.connection import get_db

logger = logging.getLogger("scheduler")
scheduler = BackgroundScheduler()


def _run_daily_eod():
    """Execute the daily EOD pipeline for the previous trading day."""
    trade_date = date.today() - timedelta(days=1)
    logger.info(f"[Scheduler] Starting EOD pipeline for {trade_date}")
    try:
        with get_db() as db:
            orch = PipelineOrchestrator(db)
            result = orch.run_eod(trade_date)
        logger.info(f"[Scheduler] EOD complete: {result}")
    except Exception as e:
        logger.error(f"[Scheduler] EOD failed: {e}", exc_info=True)


def start_scheduler():
    if not settings.scheduler_enabled:
        logger.info("[Scheduler] Disabled by config")
        return
    scheduler.add_job(
        _run_daily_eod,
        CronTrigger(hour=settings.scheduler_hour, minute=settings.scheduler_minute),
        id="daily_eod",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"[Scheduler] Started, daily EOD at "
        f"{settings.scheduler_hour:02d}:{settings.scheduler_minute:02d} UTC"
    )


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
