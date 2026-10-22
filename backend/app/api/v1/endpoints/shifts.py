from datetime import date, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, ValidationError, success_response
from models.employee import Employee
from models.enums import BreakType
from models.shift import Shift, ShiftAssignment, ShiftBreak
from models.user import User
from services import shift_service

router = APIRouter()


def _shift_dict(shift: Shift) -> dict:
    data = orm_to_dict(shift)
    data["start_time"] = shift.start_time.isoformat() if shift.start_time else None
    data["end_time"] = shift.end_time.isoformat() if shift.end_time else None
    data["breaks"] = [
        _shift_break_dict(b)
        for b in sorted(shift.breaks, key=lambda x: (x.sort_order, x.start_time.isoformat() if x.start_time else "9999"))
    ]
    return data


def _shift_break_dict(sb: ShiftBreak) -> dict:
    data = orm_to_dict(sb)
    data["start_time"] = sb.start_time.isoformat() if sb.start_time else None
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


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValidationError(f"Invalid date: {value}") from exc


@router.get("/")
def list_shifts(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.view")
    cid = resolve_company_id(user)

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
        minimum_shift_hours=float(body.get("minimum_shift_hours", 8.0)),
        maximum_shift_hours=float(body.get("maximum_shift_hours", 9.0)),
        scheduled_break_count=int(body.get("scheduled_break_count", 3)),
        scheduled_break_duration=int(body.get("scheduled_break_duration", 15)),
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
    for key in ("grace_period_minutes", "minimum_work_minutes", "break_minutes", "overtime_after_minutes",
                "scheduled_break_count", "scheduled_break_duration"):
        if key in body:
            setattr(shift, key, int(body[key]))
    for key in ("minimum_shift_hours", "maximum_shift_hours"):
        if key in body:
            setattr(shift, key, float(body[key]))
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
    raw_ids = body.get("employee_ids") or []
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ValidationError("employee_ids must be a non-empty list")
    effective_from = _parse_date(body.get("effective_from"))
    effective_to = _parse_date(body.get("effective_to"))
    if effective_from and effective_to and effective_to < effective_from:
        raise ValidationError("effective_to cannot be before effective_from")
    created = []
    for emp_id in dict.fromkeys(str(emp) for emp in raw_ids):
        emp = db.get(Employee, emp_id)
        if emp is None or str(emp.company_id) != cid:
            continue
        for other in db.scalars(
            select(ShiftAssignment).where(
                ShiftAssignment.company_id == cid,
                ShiftAssignment.employee_id == emp_id,
                ShiftAssignment.shift_id != str(shift.id),
                ShiftAssignment.effective_to.is_(None),
            )
        ):
            other.effective_to = (
                effective_from - timedelta(days=1) if effective_from else date.today() - timedelta(days=1)
            )
        existing = db.scalar(
            select(ShiftAssignment).where(
                ShiftAssignment.company_id == cid,
                ShiftAssignment.employee_id == emp_id,
                ShiftAssignment.shift_id == str(shift.id),
                ShiftAssignment.effective_to.is_(None),
            )
        )
        if existing is not None:
            existing.effective_from = effective_from
            existing.effective_to = effective_to
        else:
            db.add(
                ShiftAssignment(
                    company_id=cid,
                    employee_id=emp_id,
                    shift_id=str(shift.id),
                    effective_from=effective_from,
                    effective_to=effective_to,
                )
            )
        created.append(emp_id)
    db.commit()
    return success_response({"assigned": created})


@router.get("/{shift_id}/assignments")
def list_shift_assignments(shift_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.view")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    rows = db.execute(
        select(ShiftAssignment, Employee)
        .join(Employee, Employee.id == ShiftAssignment.employee_id)
        .where(ShiftAssignment.company_id == cid, ShiftAssignment.shift_id == str(shift.id))
        .order_by(Employee.first_name, Employee.last_name)
    ).all()
    data = []
    for assignment, emp in rows:
        item = orm_to_dict(assignment)
        item["employee_code"] = emp.employee_code
        item["employee_name"] = f"{emp.first_name or ''} {emp.last_name or ''}".strip()
        item["department_id"] = str(emp.department_id) if emp.department_id else None
        data.append(item)
    return success_response(data)


@router.delete("/{shift_id}/assignments/{assignment_id}")
def unassign_shift(
    shift_id: str, assignment_id: str, user: User = Depends(get_current_user), db=Depends(get_db)
):
    ensure_perm(user, "shifts.edit")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    assignment = db.get(ShiftAssignment, assignment_id)
    if (
        assignment is None
        or str(assignment.company_id) != cid
        or str(assignment.shift_id) != str(shift.id)
    ):
        raise NotFoundError("Shift assignment")
    db.delete(assignment)
    db.commit()
    return success_response({"deleted": True})


@router.post("/default")
def set_default(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.edit")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, body["shift_id"])

    for other in list(db.scalars(select(Shift).where(Shift.company_id == cid, Shift.is_default.is_(True)))):
        other.is_default = False
    shift.is_default = True
    db.commit()
    return success_response(_shift_dict(shift))


def _get_shift_break(db, cid: str, shift: Shift, break_id: str) -> ShiftBreak:
    sb = db.get(ShiftBreak, break_id)
    if sb is None or str(sb.company_id) != cid or str(sb.shift_id) != str(shift.id):
        raise NotFoundError("Shift break")
    return sb


@router.get("/{shift_id}/breaks")
def list_shift_breaks(shift_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.view")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    from sqlalchemy import select

    rows = list(db.scalars(select(ShiftBreak).where(ShiftBreak.shift_id == shift.id)))
    return success_response([_shift_break_dict(b) for b in rows])


@router.post("/{shift_id}/breaks")
def create_shift_break(shift_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.edit")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    name = (body.get("name") or "").strip()
    if not name:
        raise ValidationError("name is required")
    max_duration = int(body.get("max_duration_minutes", 15))
    if max_duration <= 0:
        raise ValidationError("max_duration_minutes must be positive")
    break_type = BreakType(body.get("break_type") or "SCHEDULED")
    sb = ShiftBreak(
        company_id=cid,
        shift_id=str(shift.id),
        name=name,
        break_type=break_type,
        start_time=_parse_time(body.get("start_time")),
        max_duration_minutes=max_duration,
        is_paid=bool(body.get("is_paid", True)),
        sort_order=int(body.get("sort_order", 0)),
        active=True,
    )
    db.add(sb)
    db.commit()
    db.refresh(sb)
    return success_response(_shift_break_dict(sb))


@router.patch("/{shift_id}/breaks/{break_id}")
def update_shift_break(shift_id: str, break_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.edit")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    sb = _get_shift_break(db, cid, shift, break_id)
    if "name" in body and body["name"]:
        sb.name = str(body["name"]).strip()
    if "break_type" in body:
        sb.break_type = BreakType(body["break_type"])
    if "start_time" in body:
        sb.start_time = _parse_time(body["start_time"])
    if "max_duration_minutes" in body:
        value = int(body["max_duration_minutes"])
        if value <= 0:
            raise ValidationError("max_duration_minutes must be positive")
        sb.max_duration_minutes = value
    if "is_paid" in body:
        sb.is_paid = bool(body["is_paid"])
    if "sort_order" in body:
        sb.sort_order = int(body["sort_order"])
    if "active" in body:
        sb.active = bool(body["active"])
    db.commit()
    db.refresh(sb)
    return success_response(_shift_break_dict(sb))


@router.delete("/{shift_id}/breaks/{break_id}")
def delete_shift_break(shift_id: str, break_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "shifts.delete")
    cid = resolve_company_id(user)
    shift = _get_shift(db, cid, shift_id)
    sb = _get_shift_break(db, cid, shift, break_id)
    sb.active = False
    db.commit()
    return success_response({"deleted": True})