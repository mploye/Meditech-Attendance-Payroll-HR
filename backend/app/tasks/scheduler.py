import logging

from apscheduler.schedulers.background import BackgroundScheduler

from core.config import settings
from tasks import attendance_job, sync_job

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler | None:
    """Return the currently running scheduler instance, if any."""
    return _scheduler


def start_scheduler() -> BackgroundScheduler | None:
    """Start the background scheduler with ESSL sync and daily attendance jobs if enabled."""
    global _scheduler
    if not settings.SCHEDULER_ENABLED:
        logger.info("SCHEDULER_ENABLED is false; background scheduler not started")
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone=settings.DEFAULT_TIMEZONE, daemon=True)
    _scheduler.add_job(
        sync_job.sync_all_companies,
        trigger="interval",
        seconds=settings.ESSL_SYNC_INTERVAL_SECONDS,
        id="essl_auto_sync",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        attendance_job.process_yesterday_for_all_companies,
        trigger="cron",
        hour=0,
        minute=30,
        id="daily_attendance_processing",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Background scheduler started")
    return _scheduler