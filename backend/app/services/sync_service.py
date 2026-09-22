import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from models.company import Company
from models.device import Device, ESSLConfig
from models.enums import DeviceProvider, DeviceStatus, SyncLogStatus
from services import attendance_service

logger = logging.getLogger(__name__)


def _run(coro):
    """Run a coroutine from synchronous code."""
    return asyncio.run(coro)


def _to_aware(dt):
    """Ensure a datetime is tz-aware (SQLite returns naive values on re-read)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _construct_essl_service(db: Session, config: ESSLConfig):
    """Build an ESSLService from a persisted ESSLConfig row."""
    from integrations.essl.config import ESSLConfiguration
    from integrations.essl.service import ESSLService

    essl_cfg = ESSLConfiguration.from_db_record(config)
    return ESSLService(db=db, config=essl_cfg)


def get_essl_service(db: Session, company_id: str):
    """Return a configured ESSLService for a company, or None if the provider is unavailable."""
    config = db.scalar(select(ESSLConfig).where(ESSLConfig.company_id == company_id))
    if config is None or not config.enabled:
        return None
    try:
        return _construct_essl_service(db, config)
    except (ImportError, AttributeError) as exc:
        logger.warning("ESSL integration provider unavailable for company %s: %s", company_id, exc)
        return None
    except Exception as exc:
        logger.warning("Could not build ESSL service for company %s: %s", company_id, exc)
        return None


class SyncService:
    """Orchestrates attendance device synchronization for companies."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def run_manual_sync(self, company_id: str, device_id: str | None = None) -> dict:
        """Pull transactions from ESSL device(s) for a company and persist raw logs."""
        stmt = select(Device).where(
            and_(
                Device.company_id == company_id,
                Device.provider == DeviceProvider.ESSL,
                Device.status != DeviceStatus.DISABLED,
            )
        )
        if device_id:
            stmt = stmt.where(Device.id == device_id)
        devices = list(self.db.scalars(stmt))
        totals = attendance_service.SyncCounts()
        devices_synced = 0
        for device in devices:
            sync_log = attendance_service.log_sync_start(self.db, company_id, device.id)
            try:
                service = get_essl_service(self.db, company_id)
                if service is None:
                    attendance_service.log_sync_end(
                        self.db,
                        sync_log,
                        received=0,
                        inserted=0,
                        duplicates=0,
                        failed=0,
                        status=SyncLogStatus.FAILED,
                        error_message="ESSL provider not configured",
                    )
                    continue
                now = datetime.now(timezone.utc)
                window_start = _to_aware(device.last_sync_at) or (now - timedelta(days=1))
                company = self.db.get(Company, company_id)
                transactions = _run(service.pull_transactions(company, device, window_start, now))
                counts = attendance_service.insert_transactions(
                    self.db, company_id, device.id, transactions
                )
                totals.add(counts)
                devices_synced += 1
                device.last_sync_at = now
                device.last_seen_at = now
                device.status = DeviceStatus.ONLINE
                if counts.failed > 0 and counts.inserted == 0:
                    log_status = SyncLogStatus.FAILED
                elif counts.failed > 0:
                    log_status = SyncLogStatus.PARTIAL
                else:
                    log_status = SyncLogStatus.SUCCESS
                attendance_service.log_sync_end(
                    self.db,
                    sync_log,
                    received=counts.received,
                    inserted=counts.inserted,
                    duplicates=counts.duplicates,
                    failed=counts.failed,
                    status=log_status,
                )
            except Exception as exc:
                logger.exception("Sync failed for device %s", device.id)
                device.status = DeviceStatus.ERROR
                attendance_service.log_sync_end(
                    self.db,
                    sync_log,
                    received=0,
                    inserted=0,
                    duplicates=0,
                    failed=1,
                    status=SyncLogStatus.FAILED,
                    error_message=str(exc),
                )
            finally:
                self.db.commit()
        return {
            "devices_synced": devices_synced,
            "received": totals.received,
            "inserted": totals.inserted,
            "duplicates": totals.duplicates,
            "failed": totals.failed,
        }

    def run_scheduled_sync(self) -> dict:
        """Run manual sync for every company that has ESSL sync enabled."""
        companies = list(
            self.db.scalars(
                select(Company)
                .join(ESSLConfig, ESSLConfig.company_id == Company.id)
                .where(ESSLConfig.enabled.is_(True))
            )
        )
        results: dict[str, dict] = {}
        for company in companies:
            try:
                results[company.id] = self.run_manual_sync(company.id)
            except Exception:
                logger.exception("Scheduled sync failed for company %s", company.id)
                results[company.id] = {
                    "devices_synced": 0,
                    "received": 0,
                    "inserted": 0,
                    "duplicates": 0,
                    "failed": 0,
                }
        return results

    @staticmethod
    def mark_device_status(
        db: Session,
        device_id: str,
        status: DeviceStatus,
        last_seen: datetime | None = None,
    ) -> Device | None:
        """Update a device's status and optionally its last seen timestamp."""
        device = db.get(Device, device_id)
        if device is None:
            return None
        device.status = status
        if last_seen is not None:
            device.last_seen_at = last_seen
        db.commit()
        return device