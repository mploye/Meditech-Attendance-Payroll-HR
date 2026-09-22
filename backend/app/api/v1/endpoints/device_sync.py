from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import get_db
from core.deps import get_device_connector_auth
from core.errors import success_response
from services import sync_service

router = APIRouter()

ACCEPTED = {"application/json"}


@router.post("/sync")
def connector_sync(
    company_id: str,
    payload: Optional[dict] = None,
    db=Depends(get_db),
    _auth=Depends(get_device_connector_auth),
):
    """Ingest attendance transactions pushed by the on-prem connector."""
    if payload is None:
        payload = {}
    if payload.get("trigger") == "manual":
        result = sync_service.SyncService(db).run_manual_sync(company_id)
        db.commit()
        return success_response(result)
    received = payload.get("transactions") or []
    from models.employee_device import EmployeeDevice
    from models.enums import EventType, LogSource
    from sqlalchemy import select

    inserted, duplicates, failed = 0, 0, 0
    for tx in received:
        try:
            device_user_id = str(tx.get("employee_code") or tx.get("device_user_id") or "")
            device_id = tx.get("device_id")
            timestamp_str = tx.get("timestamp") or tx.get("datetime")
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else datetime.now(timezone.utc)
            event_type = EventType(tx.get("event_type", "IN").upper()) if str(tx.get("event_type", "IN")).upper() in ("IN", "OUT") else EventType.UNKNOWN
            mapping = db.scalar(
                select(EmployeeDevice).where(
                    EmployeeDevice.company_id == company_id,
                    EmployeeDevice.device_id == device_id,
                    EmployeeDevice.device_user_id == device_user_id,
                )
            )
            employee_id = str(mapping.employee_id) if mapping else None
            from services.attendance_service import insert_raw_log

            result = insert_raw_log(
                db,
                company_id=company_id,
                device_id=device_id,
                employee_id=employee_id,
                device_user_id=device_user_id,
                event_timestamp=timestamp,
                event_type=event_type,
                source=LogSource.DEVICE,
                raw_payload=tx,
            )
            if result.inserted:
                inserted += 1
            else:
                duplicates += 1
        except Exception:
            failed += 1
            continue
    db.commit()
    return success_response(
        {
            "received": len(received),
            "inserted": inserted,
            "duplicates": duplicates,
            "failed": failed,
        }
    )


@router.get("/health")
def connector_health(_auth=Depends(get_device_connector_auth)):
    return success_response({"status": "ok", "service": "connector-ingest"})


@router.post("/process")
def connector_process(
    company_id: str,
    payload: Optional[dict] = None,
    db=Depends(get_db),
    _auth=Depends(get_device_connector_auth),
):
    """Trigger attendance processing for a company's date range."""
    from services import attendance_service

    payload = payload or {}
    end = date.today()
    start = end - timedelta(days=int(payload.get("days", 7)))
    if payload.get("from_date"):
        start = date.fromisoformat(str(payload["from_date"]))
    if payload.get("to_date"):
        end = date.fromisoformat(str(payload["to_date"]))
    result = attendance_service.process_range(db, company_id, start, end)
    db.commit()
    return success_response(result)