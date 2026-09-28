from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.audit import log_audit
from core.errors import NotFoundError, PermissionDeniedError, ValidationError, success_response
from core.rbac import has_permission
from core.timezone import company_now, local_date
from models.company import Company
from models.employee import Employee
from models.enums import BreakType, Role
from models.shift import ShiftBreak
from models.user import User
from services import break_service, shift_service

router = APIRouter()


def _company_tz(db, cid: str) -> str:
    company = db.get(Company, cid)
    return company.timezone if company else "Asia/Kolkata"


def _target_employee(db, user: User, cid: str, requested: Optional[str]) -> str:
    """Resolve the employee a break action applies to (employees act on themselves)."""
    if user.role == Role.EMPLOYEE:
        ensure_perm(user, "breaks.view.own")
        if not user.employee_id:
            raise ValidationError("Your account is not linked to an employee record")
        return str(user.employee_id)
    ensure_perm(user, "breaks.view")
    if not requested:
        raise ValidationError("employee_id is required")
    emp = db.get(Employee, requested)
    if emp is None or str(emp.company_id) != cid:
        raise NotFoundError("Employee")
    return str(emp.id)


def _owner_break(db, user: User, cid: str, break_id: str) -> object:
    """Load a break, enforcing scope (employees may only touch their own)."""
    entry = db.get(break_service.BreakLog, break_id)
    if entry is None or str(entry.company_id) != cid:
        raise NotFoundError("Break")
    if user.role == Role.EMPLOYEE:
        if not user.employee_id or str(user.employee_id) != str(entry.employee_id):
            raise PermissionDeniedError("You can only manage your own breaks")
        ensure_perm(user, "breaks.edit.own")
    else:
        ensure_perm(user, "breaks.edit")
    return entry


@router.get("/available")
def available_breaks(
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Scheduled break slots available for an employee's active shift."""
    cid = resolve_company_id(user)
    target = _target_employee(db, user, cid, employee_id)
    tz = _company_tz(db, cid)
    day = local_date(company_now(tz), tz)
    shift = shift_service.get_employee_shift(db, cid, target, day)
    if shift is None:
        return success_response([])
    from sqlalchemy import select

    rows = list(
        db.scalars(
            select(ShiftBreak)
            .where(
                ShiftBreak.shift_id == shift.id,
                ShiftBreak.active.is_(True),
                ShiftBreak.break_type == BreakType.SCHEDULED,
            )
            .order_by(ShiftBreak.sort_order)
        )
    )
    items = []
    for sb in rows:
        data = orm_to_dict(sb)
        data["start_time"] = sb.start_time.isoformat() if sb.start_time else None
        items.append(data)
    return success_response(items)


@router.get("/active")
def active_break(
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    cid = resolve_company_id(user)
    target = _target_employee(db, user, cid, employee_id)
    entry = break_service.get_active_break(db, cid, target)
    if entry is None:
        return success_response(None)
    data = break_service.break_dict(entry)
    data["elapsed_minutes"] = break_service.current_duration(entry, _company_tz(db, cid))
    return success_response(data)


@router.get("/today")
def on_break_now(user: User = Depends(get_current_user), db=Depends(get_db)):
    """Employees currently on a break (admin dashboard feed)."""
    ensure_perm(user, "breaks.view")
    cid = resolve_company_id(user)
    return success_response(break_service.who_on_break(db, cid, _company_tz(db, cid)))


@router.get("/daily")
def daily_breaks(
    date_: Optional[date] = Query(None, alias="date"),
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "breaks.view")
    cid = resolve_company_id(user)
    target = date_ or local_date(company_now(_company_tz(db, cid)), _company_tz(db, cid))
    return success_response(break_service.list_day(db, cid, target, employee_id))


@router.get("/stats")
def break_stats(
    from_date: date,
    to_date: date,
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "breaks.view")
    cid = resolve_company_id(user)
    return success_response(break_service.stats(db, cid, from_date, to_date, employee_id))


@router.post("/start")
def start_break(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    cid = resolve_company_id(user)
    break_type = BreakType(body.get("break_type", "RESTROOM"))
    if user.role == Role.EMPLOYEE:
        ensure_perm(user, "breaks.create.own")
        if not user.employee_id:
            raise ValidationError("Your account is not linked to an employee record")
        employee_id = str(user.employee_id)
    else:
        ensure_perm(user, "breaks.create")
        requested = body.get("employee_id")
        if not requested:
            raise ValidationError("employee_id is required")
        emp = db.get(Employee, requested)
        if emp is None or str(emp.company_id) != cid:
            raise NotFoundError("Employee")
        employee_id = str(emp.id)

    tz = _company_tz(db, cid)
    entry = break_service.start_break(
        db, cid, employee_id, break_type, body.get("scheduled_break_id"), tz
    )
    db.commit()
    log_audit(
        db,
        "break.start",
        entity_type="break_log",
        entity_id=str(entry.id),
        new_value=break_service.break_dict(entry),
        company_id=cid,
        user_id=str(user.id),
    )
    return success_response(break_service.break_dict(entry))


@router.post("/{break_id}/end")
def end_break(break_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    cid = resolve_company_id(user)
    entry = _owner_break(db, user, cid, break_id)
    ended = break_service.end_break(db, cid, str(entry.employee_id), str(entry.id), _company_tz(db, cid))
    db.commit()
    log_audit(
        db,
        "break.end",
        entity_type="break_log",
        entity_id=str(ended.id),
        new_value=break_service.break_dict(ended),
        company_id=cid,
        user_id=str(user.id),
    )
    return success_response(break_service.break_dict(ended))


@router.post("/{break_id}/cancel")
def cancel_break(break_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    cid = resolve_company_id(user)
    entry = _owner_break(db, user, cid, break_id)
    cancelled = break_service.cancel_break(db, cid, entry)
    db.commit()
    log_audit(
        db,
        "break.cancel",
        entity_type="break_log",
        entity_id=str(cancelled.id),
        new_value=break_service.break_dict(cancelled),
        company_id=cid,
        user_id=str(user.id),
    )
    return success_response(break_service.break_dict(cancelled))