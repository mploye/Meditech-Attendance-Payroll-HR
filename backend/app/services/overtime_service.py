from datetime import date as _date_type

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.audit import log_audit
from core.errors import NotFoundError, ValidationError
from models.enums import OvertimeStatus
from models.overtime import OvertimeRecord
from models.user import User
from services.employee_service import active_salary, get_employee


def _get_record(db: Session, company_id: str, record_id: str) -> OvertimeRecord:
    """Return an overtime record scoped to a company or raise NotFoundError."""
    record = db.scalar(
        select(OvertimeRecord).where(
            OvertimeRecord.id == record_id,
            OvertimeRecord.company_id == company_id,
        )
    )
    if record is None:
        raise NotFoundError("OvertimeRecord")
    return record


def create_overtime(
    db: Session,
    company_id: str,
    employee_id: str,
    *,
    date,
    minutes: int,
    rate: float | None = None,
    remarks: str | None = None,
) -> OvertimeRecord:
    """Create a pending overtime record for an employee."""
    get_employee(db, company_id, employee_id)
    if isinstance(date, str):
        date = _date_type.fromisoformat(date)
    record = OvertimeRecord(
        company_id=company_id,
        employee_id=employee_id,
        date=date,
        minutes=int(minutes or 0),
        rate=float(rate if rate is not None else 1.0),
        remarks=remarks,
        status=OvertimeStatus.PENDING,
    )
    db.add(record)
    db.flush()
    db.commit()
    db.refresh(record)
    return record


def list_overtime(
    db: Session,
    company_id: str,
    status: OvertimeStatus | str | None = None,
    employee_id: str | None = None,
    from_date: _date_type | None = None,
    to_date: _date_type | None = None,
) -> list[OvertimeRecord]:
    """List overtime records of a company with optional filters."""
    stmt = select(OvertimeRecord).where(OvertimeRecord.company_id == company_id)
    if status is not None:
        status = status if isinstance(status, OvertimeStatus) else OvertimeStatus(status)
        stmt = stmt.where(OvertimeRecord.status == status)
    if employee_id:
        stmt = stmt.where(OvertimeRecord.employee_id == employee_id)
    if from_date is not None:
        stmt = stmt.where(OvertimeRecord.date >= from_date)
    if to_date is not None:
        stmt = stmt.where(OvertimeRecord.date <= to_date)
    return list(db.scalars(stmt.order_by(OvertimeRecord.date.desc())))


def approve_overtime(
    db: Session,
    company_id: str,
    record_id: str,
    reviewer: User,
) -> OvertimeRecord:
    """Approve a pending overtime record, computing its amount from salary."""
    record = _get_record(db, company_id, record_id)
    if record.status != OvertimeStatus.PENDING:
        raise ValidationError("only pending overtime records can be approved")
    salary = active_salary(db, company_id, record.employee_id, record.date)
    daily_rate = (salary.basic_salary or 0) / 30 if salary is not None else 0
    record.amount = round(record.minutes / 60 * daily_rate * (record.rate or 1.0), 2)
    record.status = OvertimeStatus.APPROVED
    record.approved_by = str(reviewer.id)
    db.flush()
    db.commit()
    db.refresh(record)
    log_audit(
        db,
        "overtime.approve",
        entity_type="overtime_record",
        entity_id=str(record.id),
        new_value={"status": record.status.value, "amount": record.amount},
        company_id=str(company_id),
        user_id=str(reviewer.id),
    )
    return record


def reject_overtime(
    db: Session,
    company_id: str,
    record_id: str,
    reviewer: User,
) -> OvertimeRecord:
    """Reject a pending overtime record."""
    record = _get_record(db, company_id, record_id)
    if record.status != OvertimeStatus.PENDING:
        raise ValidationError("only pending overtime records can be rejected")
    record.status = OvertimeStatus.REJECTED
    record.approved_by = str(reviewer.id)
    db.flush()
    db.commit()
    db.refresh(record)
    log_audit(
        db,
        "overtime.reject",
        entity_type="overtime_record",
        entity_id=str(record.id),
        new_value={"status": record.status.value},
        company_id=str(company_id),
        user_id=str(reviewer.id),
    )
    return record


def approved_overtime_minutes_between(
    db: Session,
    company_id: str,
    employee_id: str,
    from_date: _date_type,
    to_date: _date_type,
) -> int:
    """Return the sum of approved overtime minutes overlapping a date range."""
    total = db.scalar(
        select(func.coalesce(func.sum(OvertimeRecord.minutes), 0)).where(
            OvertimeRecord.company_id == str(company_id),
            OvertimeRecord.employee_id == str(employee_id),
            OvertimeRecord.status == OvertimeStatus.APPROVED,
            OvertimeRecord.date >= from_date,
            OvertimeRecord.date <= to_date,
        )
    )
    return int(total or 0)