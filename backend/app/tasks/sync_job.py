import logging

from core.database import SessionLocal
from services.sync_service import SyncService

logger = logging.getLogger(__name__)


def sync_all_companies() -> None:
    """Run the scheduled ESSL sync for all companies with sync enabled."""
    db = SessionLocal()
    try:
        results = SyncService(db).run_scheduled_sync()
        logger.info("Scheduled sync completed: %s", results)
    except Exception:
        logger.exception("Scheduled sync failed")
    finally:
        db.close()