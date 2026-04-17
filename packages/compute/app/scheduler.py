import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.crawlers.state_grid.blob_store import BlobStore
from app.crawlers.state_grid.client import StateGridClient
from app.crawlers.state_grid.orchestrator import StateGridOrchestrator

logger = logging.getLogger("scheduler")
scheduler = BackgroundScheduler()


def _run_state_grid_raw() -> None:
    logger.info("[Scheduler] Starting State Grid raw crawl")
    try:
        with StateGridClient() as client:
            orchestrator = StateGridOrchestrator(client=client, blob_store=BlobStore())
            orchestrator.fetch_notices_incremental()
            orchestrator.fetch_details_for_raws()
            orchestrator.fetch_files_for_raws()
        logger.info("[Scheduler] State Grid raw crawl complete")
    except Exception as e:
        logger.error(f"[Scheduler] State Grid raw crawl failed: {e}", exc_info=True)


def start_scheduler():
    if not settings.state_grid_schedule_enable:
        logger.info("[Scheduler] Disabled by config")
        return
    minute, hour, day, month, day_of_week = settings.state_grid_schedule_cron.split()
    scheduler.add_job(
        _run_state_grid_raw,
        CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week),
        id="state_grid_raw",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[Scheduler] Started")


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
