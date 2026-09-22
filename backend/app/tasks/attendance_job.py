import logging
from datetime import date, timedelta

from sqlalchemy import select

from core.database import SessionLocal
from models.company import Company
from services import attendance_service, sync_service

logger = logging.getLogger(__name__)


def process_yesterday_for_all_companies() -> None:
    """Sync all companies and compute daily attendance for yesterday's business date."""
    yesterday = date.today() - timedelta(days=1)
    db = SessionLocal()
    try:
        companies = list(db.scalars(select(Company)))
        for company in companies:
            db.rollback()
            try:
                sync_service.SyncService(db).run_manual_sync(company.id)
                counts = attendance_service.process_range(db, company.id, yesterday, yesterday)
                logger.info("Daily attendance for company %s (%s): %s", company.id, company.name, counts)
            except Exception:
                logger.exception("Daily attendance job failed for company %s", company.id)
    finally:
        db.close()