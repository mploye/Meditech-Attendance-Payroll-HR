import logging
from datetime import date, timedelta

from sqlalchemy import select

from core.database import SessionLocal
from core.timezone import company_now
from models.company import Company
from services import attendance_service, sync_service

logger = logging.getLogger(__name__)


def process_today_for_all_companies() -> None:
    """Recompute today's attendance for every company.

    Runs every minute so daily rows (present/absent/late/overtime/breaks) stay
    correct even when nobody has the attendance page open. Punch arrival also
    triggers an immediate recompute; this job is the safety net.
    """
    db = SessionLocal()
    try:
        companies = list(db.scalars(select(Company)))
        for company in companies:
            db.rollback()
            try:
                today = company_now(company.timezone).date()
                counts = attendance_service.process_range(db, company.id, today, today)
                logger.debug("Live attendance for company %s (%s): %s", company.id, today, counts)
            except Exception:
                logger.exception("Live attendance job failed for company %s", company.id)
    finally:
        db.close()


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