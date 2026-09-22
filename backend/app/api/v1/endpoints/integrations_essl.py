from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.config import settings
from core.errors import success_response
from models.device import ESSLConfig
from models.user import User
from services import sync_service

router = APIRouter()


def _load_config(db, cid: str) -> dict:
    row = db.query(ESSLConfig).filter(ESSLConfig.company_id == cid).first()
    if row is None:
        return {"enabled": False}
    return {
        "base_url": row.base_url or "",
        "username": row.username or "",
        "company_short_name": row.company_short_name or "",
        "timeout_sec": row.timeout_sec,
        "sync_interval_sec": row.sync_interval_sec,
        "capabilities": row.capabilities,
        "enabled": row.enabled,
    }


@router.get("/config")
def get_config(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "settings.view")
    cid = resolve_company_id(user)
    return success_response(_load_config(db, cid))


@router.patch("/config")
def patch_config(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "settings.edit")
    cid = resolve_company_id(user)
    row = db.query(ESSLConfig).filter(ESSLConfig.company_id == cid).first()
    if row is None:
        row = ESSLConfig(company_id=cid, enabled=bool(body.get("enabled", False)))
        db.add(row)
    else:
        row.enabled = bool(body.get("enabled", row.enabled))
    if body.get("base_url") is not None:
        row.base_url = body["base_url"]
    if body.get("username") is not None:
        row.username = body["username"]
    if body.get("company_short_name") is not None:
        row.company_short_name = body["company_short_name"]
    if body.get("timeout_sec") is not None:
        row.timeout_sec = int(body["timeout_sec"])
    if body.get("sync_interval_sec") is not None:
        row.sync_interval_sec = int(body["sync_interval_sec"])
    if body.get("password"):
        from integrations.essl.config import encrypt_value

        row.password_encrypted = encrypt_value(str(body["password"]))
    if body.get("api_key"):
        from integrations.essl.config import encrypt_value

        row.api_key_encrypted = encrypt_value(str(body["api_key"]))
    db.commit()
    return success_response(_load_config(db, cid))


@router.post("/test")
async def test_connection(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.test")
    cid = resolve_company_id(user)
    from integrations.essl.config import ESSLConfiguration
    from integrations.essl.service import ESSLService

    row = db.query(ESSLConfig).filter(ESSLConfig.company_id == cid).first()
    cfg = ESSLConfiguration.from_db_record(row)
    service = ESSLService(db=db, config=cfg)
    result = await service.test_connection()
    return success_response(result)


@router.post("/sync")
def sync_essl(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "devices.sync")
    cid = resolve_company_id(user)
    result = sync_service.SyncService(db).run_manual_sync(cid)
    db.commit()
    return success_response(result)