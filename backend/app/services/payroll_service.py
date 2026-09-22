import calendar
from datetime import date, datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from core.audit import log_audit
from core.errors import ConflictError, NotFoundError
from models.employee import Employee
from models.enums import EmployeeStatus, PayrollPeriodStatus, PayrollRecordStatus
from models.payroll import PayrollComponent, PayrollPeriod, PayrollRecord
from models.user import User
from payroll import calculator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_period(db: Session, company_id: str, month: int, year: int) -> PayrollPeriod:
    """Create a DRAFT payroll period for a company/month/year."""
    existing = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.company_id == company_id,
            PayrollPeriod.month == month,
            PayrollPeriod.year == year,
        )
    )
    if existing is not None:
        raise ConflictError(f"Payroll period for {month}/{year} already exists")
    try:
        from services import shift_service

        ensure = getattr(shift_service, "ensure_default_shift", None)
        if callable(ensure):
            ensure(db, company_id)
    except Exception:
        pass
    last_day = calendar.monthrange(year, month)[1]
    period = PayrollPeriod(
        company_id=company_id,
        month=month,
        year=year,
        start_date=date(year, month, 1),
        end_date=date(year, month, last_day),
        status=PayrollPeriodStatus.DRAFT,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def get_periods(db: Session, company_id: str) -> list[PayrollPeriod]:
    """List payroll periods for a company, newest first."""
    return list(
        db.scalars(
            select(PayrollPeriod)
            .where(PayrollPeriod.company_id == company_id)
            .order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc())
        )
    )


def get_period(db: Session, company_id: str, period_id: str) -> PayrollPeriod:
    """Return a single payroll period scoped to a company."""
    period = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.id == period_id,
            PayrollPeriod.company_id == company_id,
        )
    )
    if period is None:
        raise NotFoundError("Payroll period")
    return period


def _upsert_record(
    db: Session,
    period: PayrollPeriod,
    employee_id: str,
    candidate: calculator.PayrollCalcResult,
) -> PayrollRecord:
    """Insert or update a payroll record and its components from a calculation."""
    existing = db.scalar(
        select(PayrollRecord).where(
            PayrollRecord.company_id == period.company_id,
            PayrollRecord.payroll_period_id == period.id,
            PayrollRecord.employee_id == employee_id,
        )
    )
    if existing is None:
        record = PayrollRecord(
            company_id=period.company_id,
            payroll_period_id=period.id,
            employee_id=employee_id,
            working_days=candidate.attendance.working_days,
            present_days=candidate.attendance.present_days,
            leave_days=candidate.attendance.leave_days,
            absent_days=candidate.attendance.absent_days,
            lop_days=candidate.attendance.lop_days,
            overtime_minutes=candidate.attendance.overtime_minutes,
            gross_salary=candidate.gross_salary,
            total_deductions=candidate.total_deductions,
            net_salary=candidate.net_salary,
            status=PayrollRecordStatus.CALCULATED,
        )
        db.add(record)
        db.flush()
    else:
        record = existing
        record.working_days = candidate.attendance.working_days
        record.present_days = candidate.attendance.present_days
        record.leave_days = candidate.attendance.leave_days
        record.absent_days = candidate.attendance.absent_days
        record.lop_days = candidate.attendance.lop_days
        record.overtime_minutes = candidate.attendance.overtime_minutes
        record.gross_salary = candidate.gross_salary
        record.total_deductions = candidate.total_deductions
        record.net_salary = candidate.net_salary
        record.status = PayrollRecordStatus.CALCULATED
    for old in list(record.components):
        db.delete(old)
    db.flush()
    for comp in candidate.components:
        db.add(
            PayrollComponent(
                company_id=period.company_id,
                payroll_record_id=record.id,
                name=comp.name,
                component_type=comp.component_type,
                amount=comp.amount,
                is_statutory=comp.is_statutory,
                reference_type=comp.reference_type,
                reference_id=comp.reference_id,
                sort_order=comp.sort_order,
            )
        )
    return record


def calculate_period(db: Session, company_id: str, period_id: str) -> dict:
    """Run payroll calculations for every employee in a DRAFT/REVIEW period."""
    period = get_period(db, company_id, period_id)
    if period.status not in (PayrollPeriodStatus.DRAFT, PayrollPeriodStatus.REVIEW):
        raise ConflictError("Payroll period must be DRAFT or REVIEW to calculate")
    period.status = PayrollPeriodStatus.CALCULATING
    period.processed_at = None
    db.flush()

    employees = list(
        db.scalars(
            select(Employee).where(
                Employee.company_id == company_id,
                Employee.status.in_(
                    [EmployeeStatus.ACTIVE, EmployeeStatus.ON_NOTICE, EmployeeStatus.INACTIVE]
                ),
            )
        )
    )
    failures: list[str] = []
    employees_processed = 0
    gross_total = 0.0
    deductions_total = 0.0
    net_total = 0.0
    try:
        for emp in employees:
            try:
                candidate = calculator.calculate_employee(db, company_id, period, emp)
            except Exception as exc:
                failures.append(f"{emp.employee_code}: {exc}")
                continue
            _upsert_record(db, period, emp.id, candidate)
            employees_processed += 1
            gross_total += candidate.gross_salary
            deductions_total += candidate.total_deductions
            net_total += candidate.net_salary
        period.status = PayrollPeriodStatus.REVIEW
        period.processed_at = _utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise
    log_audit(
        db,
        "payroll.calculation",
        "payroll_period",
        entity_id=str(period.id),
        company_id=company_id,
        new_value={
            "employees_processed": employees_processed,
            "failures": len(failures),
        },
    )
    return {
        "employees_processed": employees_processed,
        "gross": round(gross_total, 2),
        "total_deductions": round(deductions_total, 2),
        "net": round(net_total, 2),
        "failures": failures,
    }


def review_period(db: Session, company_id: str, period_id: str, user: User) -> PayrollPeriod:
    """Move a calculated payroll period into REVIEW."""
    period = get_period(db, company_id, period_id)
    period.status = PayrollPeriodStatus.REVIEW
    period.reviewed_at = _utcnow()
    db.commit()
    db.refresh(period)
    log_audit(
        db,
        "payroll.review",
        "payroll_period",
        entity_id=str(period.id),
        company_id=company_id,
        user_id=str(user.id),
    )
    return period


def approve_period(db: Session, company_id: str, period_id: str, user: User) -> PayrollPeriod:
    """Approve a review-status payroll period and its records."""
    period = get_period(db, company_id, period_id)
    if period.status != PayrollPeriodStatus.REVIEW:
        raise ConflictError("Payroll period must be in REVIEW to approve")
    period.status = PayrollPeriodStatus.APPROVED
    period.approved_at = _utcnow()
    for record in list(period.records):
        record.status = PayrollRecordStatus.APPROVED
    db.commit()
    db.refresh(period)
    log_audit(
        db,
        "payroll.approval",
        "payroll_period",
        entity_id=str(period.id),
        company_id=company_id,
        user_id=str(user.id),
    )
    return period


def lock_period(db: Session, company_id: str, period_id: str, user: User) -> PayrollPeriod:
    """Lock an approved payroll period and its records."""
    period = get_period(db, company_id, period_id)
    if period.status != PayrollPeriodStatus.APPROVED:
        raise ConflictError("Payroll period must be APPROVED to lock")
    period.status = PayrollPeriodStatus.LOCKED
    period.locked_at = _utcnow()
    for record in list(period.records):
        record.status = PayrollRecordStatus.LOCKED
    db.commit()
    db.refresh(period)
    log_audit(
        db,
        "payroll.lock",
        "payroll_period",
        entity_id=str(period.id),
        company_id=company_id,
        user_id=str(user.id),
    )
    return period


def get_period_records(db: Session, period_id: str) -> list[PayrollRecord]:
    """List payroll records of a period with employee details loaded."""
    return list(
        db.scalars(
            select(PayrollRecord)
            .where(PayrollRecord.payroll_period_id == period_id)
            .options(joinedload(PayrollRecord.employee))
            .order_by(PayrollRecord.created_at)
        )
    )


def get_record_details(db: Session, record_id: str) -> dict:
    """Return a payroll record with its calculation component breakdown."""
    record = db.get(PayrollRecord, record_id)
    if record is None:
        raise NotFoundError("Payroll record")
    return {"record": record, "components": list(record.components)}


def monthly_summary(
    db: Session, company_id: str, month: int, year: int
) -> dict:
    """Return a payroll summary for a company in a month."""
    period = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.company_id == company_id,
            PayrollPeriod.month == month,
            PayrollPeriod.year == year,
        )
    )
    if period is None:
        return {"period": None, "employees": 0, "gross": 0.0, "deductions": 0.0, "net": 0.0, "status": None}
    totals = db.execute(
        select(
            func.count(PayrollRecord.id),
            func.coalesce(func.sum(PayrollRecord.gross_salary), 0.0),
            func.coalesce(func.sum(PayrollRecord.total_deductions), 0.0),
            func.coalesce(func.sum(PayrollRecord.net_salary), 0.0),
        ).where(PayrollRecord.payroll_period_id == period.id)
    ).one()
    return {
        "period": period,
        "employees": int(totals[0] or 0),
        "gross": round(float(totals[1] or 0), 2),
        "deductions": round(float(totals[2] or 0), 2),
        "net": round(float(totals[3] or 0), 2),
        "status": period.status.value,
    }