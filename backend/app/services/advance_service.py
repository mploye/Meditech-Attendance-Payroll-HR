from datetime import date, datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from core.audit import log_audit
from core.errors import NotFoundError
from models.enums import AdvanceStatus
from models.loan import SalaryAdvance
from models.payroll import PayrollPeriod
from models.user import User


def _month_key(month: int, year: int) -> str:
    return f"{year}-{month:02d}"


def request_advance(
    db: Session,
    company_id: str,
    employee_id: str,
    *,
    requested_amount: float,
    deduction_installments: int = 1,
    deduction_start_month: str | None = None,
    remarks: str | None = None,
) -> SalaryAdvance:
    """Create a salary advance request for an employee."""
    if deduction_start_month is None:
        today = date.today()
        deduction_start_month = _month_key(today.month, today.year)
    advance = SalaryAdvance(
        company_id=company_id,
        employee_id=employee_id,
        requested_amount=float(requested_amount or 0),
        approved_amount=0.0,
        requested_at=datetime.now(timezone.utc),
        deduction_installments=int(deduction_installments or 1),
        deduction_start_month=deduction_start_month,
        status=AdvanceStatus.REQUESTED,
        remarks=remarks,
    )
    db.add(advance)
    db.commit()
    db.refresh(advance)
    return advance


def _get_advance(db: Session, company_id: str, advance_id: str) -> SalaryAdvance:
    advance = db.scalar(
        select(SalaryAdvance).where(
            SalaryAdvance.id == advance_id,
            SalaryAdvance.company_id == company_id,
        )
    )
    if advance is None:
        raise NotFoundError("SalaryAdvance")
    return advance


def list_advances(
    db: Session,
    company_id: str,
    employee_id: str | None = None,
    status: AdvanceStatus | str | None = None,
) -> list[SalaryAdvance]:
    """List salary advances for a company with optional filters."""
    if isinstance(status, str):
        status = AdvanceStatus(status)
    stmt = select(SalaryAdvance).where(SalaryAdvance.company_id == company_id)
    if employee_id:
        stmt = stmt.where(SalaryAdvance.employee_id == employee_id)
    if status is not None:
        stmt = stmt.where(SalaryAdvance.status == status)
    return list(db.scalars(stmt.order_by(SalaryAdvance.created_at.desc())))


def approve_advance(
    db: Session,
    company_id: str,
    advance_id: str,
    reviewer: User,
    approved_amount: float | None = None,
) -> SalaryAdvance:
    """Approve a salary advance request, recording the reviewer and approved amount."""
    advance = _get_advance(db, company_id, advance_id)
    if advance.status in (AdvanceStatus.CLOSED, AdvanceStatus.REJECTED, AdvanceStatus.PAID):
        return advance
    advance.approved_amount = float(approved_amount if approved_amount is not None else advance.requested_amount)
    advance.status = AdvanceStatus.APPROVED
    advance.approved_by = reviewer.id
    advance.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(advance)
    log_audit(
        db,
        "advance.approval",
        "salary_advance",
        entity_id=str(advance.id),
        company_id=company_id,
        user_id=str(reviewer.id),
    )
    return advance


def reject_advance(
    db: Session, company_id: str, advance_id: str, reviewer: User
) -> SalaryAdvance:
    """Reject a pending salary advance request."""
    advance = _get_advance(db, company_id, advance_id)
    advance.status = AdvanceStatus.REJECTED
    advance.approved_by = reviewer.id
    advance.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(advance)
    log_audit(
        db,
        "advance.rejection",
        "salary_advance",
        entity_id=str(advance.id),
        company_id=company_id,
        user_id=str(reviewer.id),
    )
    return advance


def approved_advance_deduction(
    db: Session, company_id: str, employee_id: str, period: PayrollPeriod
) -> float:
    """Sum the monthly deduction for approved advances starting in a payroll period."""
    key = _month_key(period.month, period.year)
    advances = list(
        db.scalars(
            select(SalaryAdvance).where(
                and_(
                    SalaryAdvance.company_id == company_id,
                    SalaryAdvance.employee_id == employee_id,
                    SalaryAdvance.status == AdvanceStatus.APPROVED,
                    SalaryAdvance.deduction_start_month == key,
                )
            )
        )
    )
    total = sum(
        float(a.approved_amount or 0) / max(1, int(a.deduction_installments or 1))
        for a in advances
    )
    return round(total, 2)


def close_advance(
    db: Session, company_id: str, advance_id: str, reviewer: User
) -> SalaryAdvance:
    """Close a salary advance as fully recovered."""
    advance = _get_advance(db, company_id, advance_id)
    advance.status = AdvanceStatus.CLOSED
    advance.approved_by = reviewer.id
    db.commit()
    db.refresh(advance)
    log_audit(
        db,
        "advance.close",
        "salary_advance",
        entity_id=str(advance.id),
        company_id=company_id,
        user_id=str(reviewer.id),
    )
    return advance