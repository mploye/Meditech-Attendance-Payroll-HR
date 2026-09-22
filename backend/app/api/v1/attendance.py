"""Attendance endpoints under /attendance."""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict, page_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import NotFoundError, ValidationError, success_response
from models.attendance import AttendanceDaily, AttendanceLog
from models.enums import AttendanceStatus, EventType, LogSource
from models.user import User
from schemas.attendance_process import AttendanceProcessRequest
from schemas.attendance_sync import AttendanceSyncRequest
from schemas.manual_attendance import ManualAttendanceLogRequest
from services import attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/daily")
def daily_attendance(
    date: Optional[str] = None,
    employee_id: Optional[str] = None,
    department_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    scope = company_scope(user=user)
    stmt = select(AttendanceDaily).where(AttendanceDaily.company_id == scope)
    if date:
        stmt = stmt.where(AttendanceDaily.attendance_date == date.fromisoformat(date))
    if employee_id:
        stmt = stmt.where(AttendanceDaily.employee_id == employee_id)
    if department_id:
        from models.employee import Employee

        stmt = stmt.join(Employee, Employee.id == AttendanceDaily.employee_id).filter(
            Employee.department_id == department_id
        )
    if status:
        stmt = stmt.where(AttendanceDaily.status == AttendanceStatus(status))
    total = len(list(db.scalars(stmt)))
    rows = list(
        db.scalars(
            stmt.order_by(AttendanceDaily.attendance_date.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return success_response({"items": orm_to_dict(rows), "total": total, "page": page, "page_size": page_size})


@router.get("/monthly")
def monthly_attendance(
    month: int,
    year: int,
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    scope = company_scope(user=user)
    stmt = select(AttendanceDaily).where(
        AttendanceDaily.company_id == scope,
        AttendanceDaily.attendance_date >= date(year, month, 1),
    )
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    stmt = stmt.where(AttendanceDaily.attendance_date <= date(year, month, last_day))
    if employee_id:
        stmt = stmt.where(AttendanceDaily.employee_id == employee_id)
    rows = list(db.scalars(stmt.order_by(AttendanceDaily.attendance_date)))
    return success_response(orm_to_dict(rows))


@router.get("/logs")
def attendance_logs(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    device_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    scope = company_scope(user=user)
    stmt = select(AttendanceLog).where(AttendanceLog.company_id == scope)
    if from_date:
        stmt = stmt.where(AttendanceLog.event_timestamp >= datetime.fromisoformat(from_date))
    if to_date:
        stmt = stmt.where(AttendanceLog.event_timestamp <= datetime.fromisoformat(to_date))
    if device_id:
        stmt = stmt.where(AttendanceLog.device_id == device_id)
    if employee_id:
        stmt = stmt.where(AttendanceLog.employee_id == employee_id)
    total = len(list(db.scalars(stmt)))
    rows = list(
        db.scalars(
            stmt.order_by(AttendanceLog.event_timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return success_response({"items": orm_to_dict(rows), "total": total, "page": page, "page_size": page_size})


@router.post("/sync")
def sync_attendance(
    payload: AttendanceSyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.sync")
    scope = company_scope(user=user)
    from services.sync_service import SyncService

    result = SyncService(db).run_manual_sync(scope, payload.device_id)
    return success_response(result)


@router.post("/process")
def process_attendance(
    payload: AttendanceProcessRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.process")
    scope = company_scope(user=user)
    if payload.date:
        day = payload.date[:10]
        result = attendance_service.process_range(db, scope, date.fromisoformat(day), date.fromisoformat(day), payload.employee_id)
        return success_response(result)
    if payload.from_date and payload.to_date:
        result = attendance_service.process_range(
            db, scope, date.fromisoformat(payload.from_date[:10]), date.fromisoformat(payload.to_date[:10]), payload.employee_id
        )
        return success_response(result)
    raise ValidationError("provide either date or from_date+to_date")


@router.post("/manual")
def manual_attendance_log(
    payload: ManualAttendanceLogRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.edit")
    scope = company_scope(user=user)
    timestamp = (
        datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        if payload.timestamp
        else datetime.now(timezone.utc)
    )
    result = attendance_service.insert_raw_log(
        db,
        company_id=scope,
        device_id=payload.device_id,
        employee_id=payload.employee_id,
        device_user_id=payload.employee_id,
        event_timestamp=timestamp,
        event_type=EventType(payload.event_type or "IN"),
        source=LogSource.MANUAL,
        raw_payload={"remarks": payload.remarks},
    )
    db.commit()
    return success_response(orm_to_dict(result.log))


@router.get("/daily/{record_id}")
def daily_record(
    record_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    scope = company_scope(user=user)
    record = db.scalar(
        select(AttendanceDaily).where(AttendanceDaily.id == record_id, AttendanceDaily.company_id == scope)
    )
    if record is None:
        raise NotFoundError("AttendanceDaily")
    return success_response(orm_to_dict(record))


@router.patch("/daily/{record_id}")
def correct_daily_record(
    record_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.edit")
    scope = company_scope(user=user)
    record = db.scalar(
        select(AttendanceDaily).where(AttendanceDaily.id == record_id, AttendanceDaily.company_id == scope)
    )
    if record is None:
        raise NotFoundError("AttendanceDaily")
    allowed = {
        "status", "worked_minutes", "late_minutes", "early_leave_minutes",
        "overtime_minutes", "break_minutes", "first_in", "last_out", "remarks",
    }
    from api.v1.deps import orm_to_dict

    from core.audit import log_audit

    old = orm_to_dict(record)
    for key, value in payload.items():
        if key in allowed:
            setattr(record, key, value)
    db.commit()
    db.refresh(record)
    log_audit(
        db, "attendance.correct", entity_type="attendance_daily", entity_id=str(record.id),
        old_value=old, new_value=orm_to_dict(record), company_id=scope, user_id=str(user.id), commit=False,
    )
    db.commit()
    return success_response(orm_to_dict(record))


@router.get("/summary")
def attendance_summary(
    from_date: date,
    to_date: date,
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "attendance.view")
    scope = company_scope(user=user)
    if employee_id:
        result = attendance_service.get_daily_summary(db, scope, employee_id, from_date, to_date)
        return success_response(result)
    from models.employee import Employee

    stmt = select(Employee).where(Employee.company_id == scope, Employee.status == "ACTIVE")
    rows = [
        attendance_service.get_daily_summary(db, scope, str(emp.id), from_date, to_date)
        for emp in db.scalars(stmt)
    ]
    return success_response(rows)