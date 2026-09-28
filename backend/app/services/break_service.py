"""Service layer for scheduled and restroom breaks.

Breaks are recorded as BreakLog rows (start -> optional end). Scheduled break
templates live on ShiftBreak rows and configure names, timings, max duration,
and paid/unpaid status. Restroom breaks can be started at any time.
"""

from typing import Optional

from sqlalchemy import func, select, case
from sqlalchemy.orm import Session

from core.errors import NotFoundError, ValidationError
from core.timezone import company_now, local_date
from models.employee import Employee
from models.enums import BreakStatus, BreakType
from models.shift import BreakLog, Shift, ShiftBreak
from services import shift_service


def break_dict(entry: BreakLog) -> dict:
    return {
        "id": str(entry.id),
        "company_id": str(entry.company_id),
        "employee_id": str(entry.employee_id),
        "shift_id": str(entry.shift_id) if entry.shift_id else None,
        "scheduled_break_id": str(entry.scheduled_break_id) if entry.scheduled_break_id else None,
        "name": entry.scheduled_break.name if entry.scheduled_break else None,
        "break_date": entry.break_date.isoformat(),
        "break_type": entry.break_type.value,
        "start_time": entry.start_time.isoformat() if entry.start_time else None,
        "end_time": entry.end_time.isoformat() if entry.end_time else None,
        "duration_minutes": entry.duration_minutes,
        "is_paid": entry.is_paid,
        "status": entry.status.value,
        "remarks": entry.remarks,
    }


def get_active_break(db: Session, company_id: str, employee_id: str) -> Optional[BreakLog]:
    """Return the currently running break for an employee, if any."""
    return db.scalar(
        select(BreakLog)
        .where(
            BreakLog.company_id == company_id,
            BreakLog.employee_id == employee_id,
            BreakLog.status == BreakStatus.ACTIVE,
        )
        .order_by(BreakLog.start_time.desc())
        .limit(1)
    )


def start_break(
    db: Session,
    company_id: str,
    employee_id: str,
    break_type: BreakType,
    scheduled_break_id: Optional[str] = None,
    tz: Optional[str] = None,
) -> BreakLog:
    """Open a break for an employee. Raises ValidationError if one is already active."""
    existing = get_active_break(db, company_id, employee_id)
    if existing is not None:
        raise ValidationError("A break is already active for this employee")

    now = company_now(tz)
    shift = shift_service.get_employee_shift(db, company_id, employee_id, local_date(now, tz))
    scheduled: Optional[ShiftBreak] = None
    is_paid = True

    if break_type == BreakType.SCHEDULED:
        if not scheduled_break_id:
            raise ValidationError("scheduled_break_id is required for SCHEDULED breaks")
        scheduled = db.get(ShiftBreak, scheduled_break_id)
        if scheduled is None or str(scheduled.company_id) != company_id or not scheduled.active:
            raise ValidationError("Invalid scheduled break")
        is_paid = scheduled.is_paid

    entry = BreakLog(
        company_id=company_id,
        employee_id=employee_id,
        shift_id=str(shift.id) if shift else None,
        scheduled_break_id=str(scheduled.id) if scheduled else None,
        break_date=local_date(now, tz),
        break_type=break_type,
        start_time=now,
        duration_minutes=0,
        is_paid=is_paid,
        status=BreakStatus.ACTIVE,
    )
    db.add(entry)
    db.flush()
    return entry


def end_break(db: Session, company_id: str, employee_id: str, break_id: Optional[str] = None, tz: Optional[str] = None) -> BreakLog:
    """Close an active break (by id, or the newest active one) and compute duration."""
    if break_id:
        entry = db.get(BreakLog, break_id)
        if entry is None or str(entry.company_id) != company_id:
            raise NotFoundError("Break")
    else:
        entry = get_active_break(db, company_id, employee_id)
    if entry is None:
        raise ValidationError("No active break to end")

    if entry.status != BreakStatus.ACTIVE:
        return entry

    ended = company_now(tz)
    entry.end_time = ended
    entry.duration_minutes = max(0, int((ended - entry.start_time).total_seconds() // 60))
    entry.status = BreakStatus.COMPLETED
    db.flush()
    return entry


def cancel_break(db: Session, company_id: str, entry: BreakLog) -> BreakLog:
    """Cancel an active break so it is not counted towards break time."""
    if entry.status == BreakStatus.ACTIVE:
        entry.end_time = company_now()
        entry.status = BreakStatus.CANCELLED
        db.flush()
    return entry


def current_duration(entry: BreakLog, tz: Optional[str] = None) -> int:
    """Minutes elapsed for an active break (buffered 0 before the minute mark)."""
    if entry.start_time is None:
        return 0
    return max(0, int((company_now(tz) - entry.start_time).total_seconds() // 60))


def day_break_minutes(
    db: Session,
    company_id: str,
    employee_id: str,
    day,
    shift: Optional[Shift] = None,
    tz: Optional[str] = None,
) -> int:
    """Total break minutes counted for an employee on a day.

    Prefers recorded break logs (completed + currently active partial). Falls
    back to the shift's configured break budget when no breaks were recorded,
    so payroll still inherits a sensible default before the module goes live.
    """
    entries = list(
        db.scalars(
            select(BreakLog).where(
                BreakLog.company_id == company_id,
                BreakLog.employee_id == employee_id,
                BreakLog.break_date == day,
            )
        )
    )
    if entries:
        total = 0
        for e in entries:
            if e.status == BreakStatus.COMPLETED:
                total += int(e.duration_minutes or 0)
            elif e.status == BreakStatus.ACTIVE:
                total += current_duration(e, tz)
        return total

    if shift is None:
        shift = shift_service.get_employee_shift(db, company_id, employee_id, day)
    if shift is not None:
        return shift.total_scheduled_break_minutes
    return 0


def list_day(
    db: Session,
    company_id: str,
    day,
    employee_id: Optional[str] = None,
) -> list[dict]:
    """All breaks recorded on a day, decorated with employee details."""
    stmt = select(BreakLog).where(BreakLog.company_id == company_id, BreakLog.break_date == day)
    if employee_id:
        stmt = stmt.where(BreakLog.employee_id == employee_id)
    rows: list[dict] = []
    for entry in list(db.scalars(stmt.order_by(BreakLog.start_time))):
        item = break_dict(entry)
        emp = db.get(Employee, entry.employee_id)
        item["employee_code"] = emp.employee_code if emp else None
        item["employee_name"] = f"{emp.first_name} {emp.last_name or ''}".strip() if emp else None
        rows.append(item)
    return rows


def who_on_break(db: Session, company_id: str, tz: Optional[str] = None) -> list[dict]:
    """Employees who currently have an ACTIVE break, with elapsed duration."""
    entries = list(
        db.scalars(
            select(BreakLog)
            .where(BreakLog.company_id == company_id, BreakLog.status == BreakStatus.ACTIVE)
            .order_by(BreakLog.start_time)
        )
    )
    rows: list[dict] = []
    for entry in entries:
        emp = db.get(Employee, entry.employee_id)
        rows.append(
            {
                **break_dict(entry),
                "employee_code": emp.employee_code if emp else None,
                "employee_name": f"{emp.first_name} {emp.last_name or ''}".strip() if emp else None,
                "elapsed_minutes": current_duration(entry, tz),
            }
        )
    return rows


def stats(
    db: Session,
    company_id: str,
    from_date,
    to_date,
    employee_id: Optional[str] = None,
) -> list[dict]:
    """Break totals per employee across a date range."""
    stmt = (
        select(
            BreakLog.employee_id,
            func.count(BreakLog.id).label("break_count"),
            func.sum(func.coalesce(BreakLog.duration_minutes, 0)).label("total_minutes"),
            func.sum(
                case((BreakLog.is_paid.is_(True), func.coalesce(BreakLog.duration_minutes, 0)), else_=0)
            ).label("paid_minutes"),
        )
        .where(
            BreakLog.company_id == company_id,
            BreakLog.break_date >= from_date,
            BreakLog.break_date <= to_date,
            BreakLog.status != BreakStatus.CANCELLED,
        )
        .group_by(BreakLog.employee_id)
    )
    if employee_id:
        stmt = stmt.where(BreakLog.employee_id == employee_id)
    rows: list[dict] = []
    for employee_id_val, count, total_minutes, paid_minutes in db.execute(stmt):
        emp = db.get(Employee, employee_id_val)
        rows.append(
            {
                "employee_id": str(employee_id_val),
                "employee_code": emp.employee_code if emp else None,
                "employee_name": f"{emp.first_name} {emp.last_name or ''}".strip() if emp else None,
                "break_count": int(count),
                "total_minutes": int(total_minutes or 0),
                "paid_minutes": int(paid_minutes or 0),
            }
        )
    return rows