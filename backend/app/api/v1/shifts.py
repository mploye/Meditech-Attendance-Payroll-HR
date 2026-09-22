"""Shift endpoints under /shifts (CRUD + assignments)."""

from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import NotFoundError, ValidationError, success_response
from models.shift import Shift, ShiftAssignment
from models.user import User
from schemas.shift import ShiftAssignRequest, ShiftCreateRequest, ShiftDefaultRequest, ShiftUpdateRequest
from services import shift_service

router = APIRouter(prefix="/shifts", tags=["shifts"])


def _get_shift(db: Session, company_id: str, shift_id: str) -> Shift:
    shift = db.scalar(
        select(Shift).where(Shift.id == shift_id, Shift.company_id == company_id)
    )
    if shift is None:
        raise NotFoundError("Shift")
    return shift


@router.get("")
def list_shifts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "shifts.view")
    scope = company_scope(user=user)
    rows = list(db.scalars(select(Shift).where(Shift.company_id == scope).order_by(Shift.name)))
    return success_response(orm_to_dict(rows))


@router.post("")
def create_shift(
    payload: ShiftCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "shifts.create")
    scope = company_scope(user=user)
    data = payload.model_dump()
    start = _parse_time(data.pop("start_time", None))
    end = _parse_time(data.pop("end_time", None))
    shift = Shift(company_id=scope, start_time=start, end_time=end, **data)
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return success_response(orm_to_dict(shift))


@router.get("/{shift_id}")
def get_shift(
    shift_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "shifts.view")
    scope = company_scope(user=user)
    return success_response(orm_to_dict(_get_shift(db, scope, shift_id)))


@router.patch("/{shift_id}")
def update_shift(
    shift_id: str,
    payload: ShiftUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "shifts.edit")
    scope = company_scope(user=user)
    shift = _get_shift(db, scope, shift_id)
    data = payload.model_dump(exclude_unset=True)
    if "start_time" in data:
        shift.start_time = _parse_time(data.pop("start_time"))
    if "end_time" in data:
        shift.end_time = _parse_time(data.pop("end_time"))
    for key, value in data.items():
        if hasattr(shift, key):
            setattr(shift, key, value)
    db.commit()
    db.refresh(shift)
    return success_response(orm_to_dict(shift))


@router.delete("/{shift_id}")
def delete_shift(
    shift_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "shifts.delete")
    scope = company_scope(user=user)
    shift = _get_shift(db, scope, shift_id)
    db.delete(shift)
    db.commit()
    return success_response({"message": "deleted"})


@router.post("/{shift_id}/assign")
def assign_shift(
    shift_id: str,
    payload: ShiftAssignRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "shifts.edit")
    scope = company_scope(user=user)
    _get_shift(db, scope, shift_id)
    effective_from = _parse_date(payload.effective_from) if payload.effective_from else None
    effective_to = _parse_date(payload.effective_to) if payload.effective_to else None
    for employee_id in payload.employee_ids:
        db.add(
            ShiftAssignment(
                company_id=scope,
                employee_id=employee_id,
                shift_id=shift_id,
                effective_from=effective_from,
                effective_to=effective_to,
            )
        )
    db.commit()
    return success_response({"message": f"assigned to {len(payload.employee_ids)} employees"})


@router.post("/default")
def set_default_shift(
    payload: ShiftDefaultRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "shifts.edit")
    scope = company_scope(user=user)
    shift = _get_shift(db, scope, payload.shift_id)
    for existing in db.scalars(select(Shift).where(Shift.company_id == scope, Shift.is_default.is_(True))):
        existing.is_default = False
    shift.is_default = True
    db.commit()
    db.refresh(shift)
    return success_response(orm_to_dict(shift))


@router.get("/employees/{employee_id}/active")
def employee_active_shift(
    employee_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "shifts.view")
    scope = company_scope(user=user)
    shift = shift_service.get_employee_shift(db, scope, employee_id, date.today())
    return success_response(orm_to_dict(shift))


def _parse_time(value) -> any:
    if value in (None, ""):
        return None
    from datetime import time

    parts = str(value).split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    second = int(parts[2]) if len(parts) > 2 else 0
    return time(hour, minute, second)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])