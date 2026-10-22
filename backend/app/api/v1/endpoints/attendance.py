from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import selectinload

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.audit import log_audit
from core.errors import NotFoundError, ValidationError, success_response
from core.timezone import company_now, get_zone, local_date
from models.attendance import AttendanceDaily, AttendanceLog
from models.employee import Employee
from models.enums import AttendanceStatus, EventType, LogSource
from models.shift import BreakLog
from models.user import User
from services import attendance_service, break_service, sync_service

router = APIRouter()


@router.get("/daily")
def daily_attendance(
    date_: Optional[date] = Query(None, alias="date"),
    employee_id: Optional[str] = None,
    department_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    cid = resolve_company_id(user)
    target = date_ or local_date(company_now(), _company_tz(db, cid))
    from sqlalchemy import func, select

    stmt = select(AttendanceDaily).where(
        AttendanceDaily.company_id == cid,
        AttendanceDaily.attendance_date == target,
    )
    if employee_id:
        stmt = stmt.where(AttendanceDaily.employee_id == employee_id)
    if status:
        stmt = stmt.where(AttendanceDaily.status == AttendanceStatus(status))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.join(Employee, Employee.id == AttendanceDaily.employee_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    pages = (total + page_size - 1) // page_size

    employee_ids = [row.employee_id for row in rows]
    employees: dict[str, Employee] = {}
    logs_by_employee: dict[str, list[AttendanceLog]] = {}
    breaks_by_employee: dict[str, list[dict]] = {}
    if employee_ids:
        employees = {
            emp.id: emp
            for emp in db.scalars(select(Employee).where(Employee.id.in_(employee_ids)))
        }
        zone = get_zone(_company_tz(db, cid))
        day_start = datetime.combine(target, datetime.min.time(), tzinfo=zone).astimezone(timezone.utc)
        day_end = day_start + timedelta(days=1)
        for log in db.scalars(
            select(AttendanceLog)
            .where(
                AttendanceLog.company_id == cid,
                AttendanceLog.employee_id.in_(employee_ids),
                AttendanceLog.event_timestamp >= day_start,
                AttendanceLog.event_timestamp <= day_end,
            )
            .order_by(AttendanceLog.event_timestamp)
        ):
            logs_by_employee.setdefault(log.employee_id, []).append(log)
        for entry in db.scalars(
            select(BreakLog)
            .where(
                BreakLog.company_id == cid,
                BreakLog.employee_id.in_(employee_ids),
                BreakLog.break_date == target,
            )
            .options(selectinload(BreakLog.scheduled_break))
            .order_by(BreakLog.start_time)
        ):
            breaks_by_employee.setdefault(entry.employee_id, []).append(break_service.break_dict(entry))

    items = []
    for row in rows:
        d = orm_to_dict(row)
        emp = employees.get(row.employee_id)
        d["employee_code"] = emp.employee_code if emp else None
        d["employee_name"] = f"{emp.first_name} {emp.last_name or ''}" if emp else None
        d["department_id"] = str(emp.department_id) if emp and emp.department_id else None
        logs = logs_by_employee.get(row.employee_id, [])
        d["punches"] = [
            {
                "time": log.event_timestamp.isoformat(),
                "event_type": eff.value,
                "source": log.source.value if hasattr(log.source, "value") else str(log.source),
            }
            for log, eff in attendance_service.effective_punch_sequence(logs)
        ]
        logged = breaks_by_employee.get(row.employee_id)
        d["breaks"] = logged if logged else attendance_service.break_segments(logs)
        items.append(d)
    return success_response(
        {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}
    )


@router.get("/range-summary")
def range_summary(
    from_date: date,
    to_date: date,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Per-employee aggregates across a range — powers Daily/Weekly/Monthly tabs."""
    ensure_perm(user, "attendance.view")
    cid = resolve_company_id(user)
    return success_response(attendance_service.get_range_summary(db, cid, from_date, to_date))


@router.get("/monthly")
def monthly_attendance(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    cid = resolve_company_id(user)
    from calendar import monthrange

    last_day = monthrange(year, month)[1]
    rows = attendance_service.get_range_summary(db, cid, date(year, month, 1), date(year, month, last_day))
    if employee_id:
        rows = [r for r in rows if r["employee_id"] == employee_id]
    return success_response(rows)


@router.get("/logs")
def list_logs(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    device_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    cid = resolve_company_id(user)
    from sqlalchemy import func, select

    stmt = select(AttendanceLog).where(AttendanceLog.company_id == cid)
    if device_id:
        stmt = stmt.where(AttendanceLog.device_id == device_id)
    if employee_id:
        stmt = stmt.where(AttendanceLog.employee_id == employee_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(AttendanceLog.event_timestamp.desc()).offset((page - 1) * page_size).limit(page_size)))
    pages = (total + page_size - 1) // page_size
    return success_response(
        {
            "items": [orm_to_dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }
    )


@router.post("/sync")
def sync_attendance(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "attendance.sync")
    cid = resolve_company_id(user)
    result = sync_service.SyncService(db).run_manual_sync(cid)
    db.commit()
    return success_response(result)


@router.post("/process")
def process_attendance(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    date_: Optional[date] = Query(None, alias="date"),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "attendance.process")
    cid = resolve_company_id(user)
    start = from_date or date_ or local_date(company_now(), _company_tz(db, cid))
    end = to_date or start
    result = attendance_service.process_range(db, cid, start, end)
    return success_response(result)


@router.post("/manual")
def manual_punch(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "attendance.edit")
    cid = resolve_company_id(user)
    employee_id = body.get("employee_id")
    event_type = EventType(body.get("event_type", "IN"))
    ts = body.get("timestamp")
    if ts:
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        ts = company_now(_company_tz(db, cid))
    emp = db.get(Employee, employee_id)
    if emp is None or str(emp.company_id) != cid:
        raise NotFoundError("Employee")
    employee_service_device_user_id = body.get("device_user_id") or emp.employee_code
    result = attendance_service.insert_raw_log(
        db,
        company_id=cid,
        device_id=None,
        employee_id=str(emp.id),
        device_user_id=str(employee_service_device_user_id),
        event_timestamp=ts,
        event_type=event_type,
        source=LogSource.MANUAL,
        raw_payload={"remarks": body.get("remarks"), "entered_by": str(user.id)},
    )
    db.commit()
    day = local_date(ts, _company_tz(db, cid))
    attendance_service.process_day(db, cid, str(emp.id), day)
    db.commit()
    return success_response({"log": orm_to_dict(result.log), "inserted": result.inserted})


@router.get("/daily/{record_id}")
def get_daily(record_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "attendance.view")
    cid = resolve_company_id(user)
    row = db.get(AttendanceDaily, record_id)
    if row is None or str(row.company_id) != cid:
        raise NotFoundError("Attendance record")
    return success_response(orm_to_dict(row))


@router.patch("/daily/{record_id}")
def correct_daily(record_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "attendance.edit")
    cid = resolve_company_id(user)
    row = db.get(AttendanceDaily, record_id)
    if row is None or str(row.company_id) != cid:
        raise NotFoundError("Attendance record")
    old = orm_to_dict(row)
    for key in ("first_in", "last_out"):
        if key in body and body[key]:
            body[key] = datetime.fromisoformat(body[key].replace("Z", "+00:00"))
    for key in ("first_in", "last_out", "worked_minutes", "late_minutes", "early_leave_minutes", "overtime_minutes", "remarks"):
        if key in body:
            setattr(row, key, body[key])
    if "status" in body:
        row.status = AttendanceStatus(body["status"])
    db.commit()
    log_audit(
        db,
        "attendance.edit",
        entity_type="attendance_daily",
        entity_id=str(row.id),
        old_value=old,
        new_value=orm_to_dict(row),
        company_id=cid,
        user_id=str(user.id),
    )
    return success_response(orm_to_dict(row))


@router.get("/summary")
def attendance_summary(
    from_date: date,
    to_date: date,
    employee_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    cid = resolve_company_id(user)
    return success_response(attendance_service.get_daily_summary(db, cid, employee_id, from_date, to_date))


def _company_tz(db, cid: str) -> str:
    from models.company import Company

    company = db.get(Company, cid)
    return company.timezone if company else "Asia/Kolkata"