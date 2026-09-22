from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.enums import OvertimeStatus
from models.overtime import OvertimeRecord
from models.user import User
from services import overtime_service

router = APIRouter()


def _get_record(db, cid: str, record_id: str) -> OvertimeRecord:
    row = db.get(OvertimeRecord, record_id)
    if row is None or str(row.company_id) != cid:
        raise NotFoundError("Overtime record")
    return row


@router.get("/")
def list_overtime(
    status: Optional[str] = None,
    employee_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "overtime.view")
    cid = resolve_company_id(user)
    st = OvertimeStatus(status) if status else None
    rows = overtime_service.list_overtime(db, cid, status=st, employee_id=employee_id, from_date=from_date, to_date=to_date)
    return success_response([orm_to_dict(r) for r in rows])


@router.post("/")
def create_overtime(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "overtime.create")
    cid = resolve_company_id(user)
    row = overtime_service.create_overtime(
        db,
        cid,
        body["employee_id"],
        date=date.fromisoformat(body["date"]),
        minutes=int(body["minutes"]),
        rate=body.get("rate"),
        remarks=body.get("remarks"),
    )
    return success_response(orm_to_dict(row))


@router.post("/{record_id}/approve")
def approve(record_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "overtime.approve")
    cid = resolve_company_id(user)
    _get_record(db, cid, record_id)
    row = overtime_service.approve_overtime(db, cid, record_id, user)
    return success_response(orm_to_dict(row))


@router.post("/{record_id}/reject")
def reject(record_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "overtime.approve")
    cid = resolve_company_id(user)
    _get_record(db, cid, record_id)
    row = overtime_service.reject_overtime(db, cid, record_id, user)
    return success_response(orm_to_dict(row))