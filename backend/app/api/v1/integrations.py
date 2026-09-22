"""eSSL integration + device connector endpoints."""

import json
from dataclasses import dataclass

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm
from core.database import get_db
from core.deps import get_current_user, get_device_connector_auth
from core.errors import NotFoundError, success_response
from integrations.essl.config import ESSLConfiguration, encrypt_value
from models.device import ESSLConfig, Device
from models.user import User
from schemas.integration import ESSLConfigUpdateRequest
from services import sync_service

router = APIRouter(prefix="/integrations/essl", tags=["integrations"])


def _get_config(db: Session, company_id: str) -> ESSLConfig | None:
    return db.scalar(select(ESSLConfig).where(ESSLConfig.company_id == company_id))


def _apply_config(record: ESSLConfig, data: dict) -> ESSLConfig:
    for key, value in data.items():
        if value is None:
            continue
        if key == "password":
            record.password_encrypted = encrypt_value(str(value))
        elif key == "api_key":
            record.api_key_encrypted = encrypt_value(str(value))
        elif key == "capabilities":
            record.capabilities = json.dumps(value)
        elif hasattr(record, key):
            setattr(record, key, value)
    return record


@router.get("/config")
def get_essl_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "settings.view")
    scope = company_scope(user=user)
    config = _get_config(db, scope)
    if config is None:
        return success_response(ESSLConfiguration.from_settings().to_dict())
    return success_response(ESSLConfiguration.from_db_record(config).to_dict())


@router.patch("/config")
def update_essl_config(
    payload: ESSLConfigUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "settings.edit")
    scope = company_scope(user=user)
    record = _get_config(db, scope)
    if record is None:
        record = ESSLConfig(company_id=scope)
    data = payload.model_dump(exclude_unset=True)
    record = _apply_config(record, data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return success_response(ESSLConfiguration.from_db_record(record).to_dict())


@router.post("/test")
def test_essl(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.test")
    scope = company_scope(user=user)
    service = sync_service.get_essl_service(db, scope)
    if service is None:
        return success_response(
            {"success": False, "provider": "eSSL", "status": "FAILED", "message": "provider not configured"}
        )
    return success_response(sync_service._run(service.test_connection()))


@router.post("/sync")
def sync_essl(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "devices.sync")
    scope = company_scope(user=user)
    result = sync_service.SyncService(db).run_manual_sync(scope)
    return success_response(result)


connector_router = APIRouter(prefix="/device-sync", tags=["device-sync"])


@dataclass
class _Tx:
    device_user_id: object
    timestamp: object
    event_type: object
    external_event_id: object = None
    raw: object = None


@connector_router.post("/transactions")
def connector_transactions(
    payload: dict,
    db: Session = Depends(get_db),
    _: str = Depends(get_device_connector_auth),
):
    """Ingest raw device transactions authenticated by the connector API key."""
    device_ref = str(payload.get("device_id") or "")
    transactions = payload.get("transactions") or []
    device = db.scalar(
        select(Device).where((Device.id == device_ref) | (Device.serial_number == device_ref))
    )
    if device is None:
        raise NotFoundError("Device")
    from services import attendance_service

    items = [
        _Tx(
            device_user_id=tx.get("device_user_id"),
            timestamp=tx.get("timestamp"),
            event_type=tx.get("event_type"),
            external_event_id=tx.get("external_event_id"),
            raw=tx.get("raw"),
        )
        for tx in transactions
        if isinstance(tx, dict)
    ]
    counts = attendance_service.insert_transactions(db, str(device.company_id), str(device.id), items)
    return success_response(
        {
            "success": True,
            "received": counts.received,
            "inserted": counts.inserted,
            "duplicates": counts.duplicates,
            "failed": counts.failed,
        }
    )


@connector_router.get("/status")
def connector_status(db: Session = Depends(get_db)):
    from core.config import settings

    return success_response(
        {
            "connected": True,
            "mock_mode": settings.ESSL_MOCK_MODE,
            "scheduler_enabled": settings.SCHEDULER_ENABLED,
        }
    )