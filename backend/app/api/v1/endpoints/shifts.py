from datetime import date, time
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.employee import Employee
from models.shift import Shift, ShiftAssignment
from models.user import User
from services import shift_service

router = APIRouter()


def _shift_dict(shift: Shift) -> dict:
    data = orm_to_dict(shift)
    data["start_time"] = shift.start_time.isoformat() if shift.start_time else None
    data["end_time"] = shift.end_time.isoformat() if shift.end_time else None
    return data


def _get_shift(db, cid: str, shift_id: str) -> Shift:
    shift = db.get(Shift, shift_id)
    if shift is None or str(shift.company_id) != cid:
        raise NotFoundError("Shift")
    return shift


def _parse_time(value):
    if not value:
        return None
    if isinstance(value, time):
        return value
    parts = str(value).split(":")
    return time(int(parts[0]), int(parts[1]))


@router.get("/")
def list_shifts(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.view")
    cid = resolve_company_id(user)
    from sqlalchemy import select

    shifts = list(db.scalars(select(Shift).where(Shift.company_id == cid)))
    return success_response([_shift_dict(s) for s in shifts])


@router.post("/")
def create_shift(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.create")
    cid = resolve_company_id(user)
    shift = Shift(
        company_id=cid,
        name=body["name"],
        code=body.get("code"),
        start_time=_parse_time(body.get("start_time")),
        end_time=_parse_time(body.get("end_time")),
        grace_period_minutes=int(body.get("grace_period_minutes", 0)),
        minimum_work_minutes=int(body.get("minimum_work_minutes", 0)),
        break_minutes=int(body.get("break_minutes", 0)),
        overtime_enabled=bool(body.get("overtime_enabled", True)),
        overtime_after_minutes=int(body.get("overtime_after_minutes", 60)),
        night_shift=bool(body.get("night_shift", False)),
        weekly_off_days=body.get("weekly_off_days"),
        is_default=bool(body.get("is_default", False)),
        active=True,
    )
    if shift.is_default:
        existing_default = shift_service.get_default_shift(db, cid)
        if existing_default and existing_default.id != shift.id:
            existing_default.is_default = False
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return success_response(_shift_dict(shift))


@router.get("/{shift_id}")
def get_shift(shift_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.view")
    cid = resolve_company_id(user)
    return success_response(_shift_dict(_get_shift(db, cid, shift_id)))


@router.patch("/{shift_id}")
def update_shift(shift_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.edit")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    if "name" in body:
        shift.name = body["name"]
    if "code" in body:
        shift.code = body["code"]
    if "start_time" in body:
        shift.start_time = _parse_time(body["start_time"])
    if "end_time" in body:
        shift.end_time = _parse_time(body["end_time"])
    for key in ("grace_period_minutes", "minimum_work_minutes", "break_minutes", "overtime_after_minutes"):
        if key in body:
            setattr(shift, key, int(body[key]))
    for key in ("overtime_enabled", "night_shift", "active", "is_default"):
        if key in body:
            setattr(shift, key, bool(body[key]))
    if "weekly_off_days" in body:
        shift.weekly_off_days = body["weekly_off_days"]
    db.commit()
    db.refresh(shift)
    return success_response(_shift_dict(shift))


@router.delete("/{shift_id}")
def delete_shift(shift_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.delete")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    shift.active = False
    db.commit()
    return success_response({"deleted": True})


@router.post("/{shift_id}/assign")
def assign_shift(shift_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.edit")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    employee_ids = body.get("employee_ids") or []
    effective_from = body.get("effective_from")
    if isinstance(effective_from, str):
        effective_from = date.fromisoformat(effective_from)
    created = []
    for emp_id in employee_ids:
        emp = db.get(Employee, emp_id)
        if emp is None or str(emp.company_id) != cid:
            continue
        assignment = ShiftAssignment(
            company_id=cid, employee_id=str(emp_id), shift_id=str(shift.id), effective_from=effective_from
        )
        db.add(assignment)
        created.append(str(emp_id))
    db.commit()
    return success_response({"assigned": created})


@router.post("/default")
def set_default(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.edit")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, body["shift_id"])
    from sqlalchemy import select

    for other in list(db.scalars(select(Shift).where(Shift.company_id == cid, Shift.is_default.is_(True)))):
        other.is_default = False
    shift.is_default = True
    db.commit()
    return success_response(_shift_dict(shift))