from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.audit import log_audit
from core.errors import NotFoundError, ValidationError
from models.employee import Employee
from models.enums import EmployeeStatus, LeaveStatus, LeaveTypeCategory
from models.leave import LeaveBalance, LeaveRequest, LeaveType
from models.user import User
from services.employee_service import get_employee

_LT_FIELDS = {"name", "code", "category", "days_per_year", "carry_forward_days", "requires_approval"}


def _to_date(value) -> date:
    """Coerce a str or date value into a date."""
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value


def _apply_leave_type_fields(lt: LeaveType, data: dict) -> None:
    """Apply allowed leave type fields with enum coercion."""
    for key, value in data.items():
        if key not in _LT_FIELDS:
            continue
        if key == "category" and isinstance(value, str):
            value = LeaveTypeCategory(value)
        setattr(lt, key, value)


def _get_leave_type(db: Session, company_id: str, leave_type_id: str) -> LeaveType:
    """Return a leave type scoped to a company or raise NotFoundError."""
    lt = db.scalar(
        select(LeaveType).where(LeaveType.id == leave_type_id, LeaveType.company_id == company_id)
    )
    if lt is None:
        raise NotFoundError("LeaveType")
    return lt


def _get_balance(
    db: Session, company_id: str, employee_id: str, leave_type_id: str, year: int
) -> LeaveBalance | None:
    """Return the leave balance row for an employee/type/year if present."""
    return db.scalar(
        select(LeaveBalance).where(
            LeaveBalance.company_id == str(company_id),
            LeaveBalance.employee_id == str(employee_id),
            LeaveBalance.leave_type_id == str(leave_type_id),
            LeaveBalance.year == year,
        )
    )


def _get_request(db: Session, company_id: str, request_id: str) -> LeaveRequest:
    """Return a leave request scoped to a company or raise NotFoundError."""
    req = db.scalar(
        select(LeaveRequest).where(LeaveRequest.id == request_id, LeaveRequest.company_id == company_id)
    )
    if req is None:
        raise NotFoundError("LeaveRequest")
    return req


def list_leave_types(db: Session, company_id: str) -> list[LeaveType]:
    """List leave types of a company ordered by name."""
    return list(
        db.scalars(
            select(LeaveType)
            .where(LeaveType.company_id == company_id)
            .order_by(LeaveType.name)
        )
    )


def create_leave_type(db: Session, company_id: str, data: dict) -> LeaveType:
    """Create a leave type for a company."""
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValidationError("name is required")
    lt = LeaveType(company_id=company_id, name=name)
    _apply_leave_type_fields(lt, data)
    db.add(lt)
    db.flush()
    db.commit()
    db.refresh(lt)
    return lt


def update_leave_type(db: Session, company_id: str, leave_type_id: str, data: dict) -> LeaveType:
    """Update allowed fields of a leave type."""
    lt = _get_leave_type(db, company_id, leave_type_id)
    _apply_leave_type_fields(lt, data)
    db.flush()
    db.commit()
    db.refresh(lt)
    return lt


def apply_leave(
    db: Session,
    company_id: str,
    employee_id: str,
    *,
    leave_type_id: str,
    start_date,
    end_date,
    reason: str | None = None,
    is_half_day: bool = False,
) -> LeaveRequest:
    """Apply for leave, validating and updating the running balance."""
    lt = _get_leave_type(db, company_id, leave_type_id)
    get_employee(db, company_id, employee_id)
    start_date = _to_date(start_date)
    end_date = _to_date(end_date)
    if end_date < start_date:
        raise ValidationError("end_date cannot be before start_date")
    days = 0.5 if is_half_day else float((end_date - start_date).days + 1)
    balance = _get_balance(db, company_id, employee_id, leave_type_id, start_date.year)
    if balance is None:
        balance = LeaveBalance(
            company_id=str(company_id),
            employee_id=str(employee_id),
            leave_type_id=str(leave_type_id),
            year=start_date.year,
            entitled_days=float(lt.days_per_year or 0),
            used_days=0.0,
            pending_days=0.0,
            remaining_days=float(lt.days_per_year or 0),
        )
        db.add(balance)
        db.flush()
    if (balance.entitled_days - balance.used_days - balance.pending_days) < days:
        raise ValidationError("Insufficient leave balance")
    balance.pending_days += days
    balance.remaining_days = balance.entitled_days - balance.used_days - balance.pending_days
    request = LeaveRequest(
        company_id=str(company_id),
        employee_id=str(employee_id),
        leave_type_id=str(leave_type_id),
        start_date=start_date,
        end_date=end_date,
        days=days,
        reason=reason,
        status=LeaveStatus.PENDING,
        is_half_day=bool(is_half_day),
    )
    db.add(request)
    db.flush()
    db.commit()
    db.refresh(request)
    return request


def list_leave_requests(
    db: Session,
    company_id: str,
    status: LeaveStatus | str | None = None,
    employee_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Return paginated leave requests for a company with optional filters."""
    stmt = select(LeaveRequest).where(LeaveRequest.company_id == company_id)
    if status is not None:
        status = status if isinstance(status, LeaveStatus) else LeaveStatus(status)
        stmt = stmt.where(LeaveRequest.status == status)
    if employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    page = max(1, page)
    page_size = max(1, page_size)
    items = list(
        db.scalars(
            stmt.order_by(LeaveRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    pages = (total + page_size - 1) // page_size
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


def approve_leave(
    db: Session,
    company_id: str,
    request_id: str,
    reviewer: User,
    comment: str | None = None,
) -> LeaveRequest:
    """Approve a pending leave request, moving pending days to used."""
    req = _get_request(db, company_id, request_id)
    if req.status != LeaveStatus.PENDING:
        raise ValidationError("only pending leave requests can be approved")
    balance = _get_balance(db, company_id, req.employee_id, req.leave_type_id, req.start_date.year)
    if balance is None:
        raise ValidationError("leave balance not found for this request period")
    balance.pending_days -= req.days
    balance.used_days += req.days
    balance.remaining_days = balance.entitled_days - balance.used_days - balance.pending_days
    req.status = LeaveStatus.APPROVED
    req.reviewed_by = str(reviewer.id)
    req.reviewed_at = datetime.now(timezone.utc)
    req.review_comment = comment
    db.flush()
    db.commit()
    db.refresh(req)
    log_audit(
        db,
        "leave.approve",
        entity_type="leave_request",
        entity_id=str(req.id),
        new_value={"status": req.status.value, "days": req.days},
        company_id=str(company_id),
        user_id=str(reviewer.id),
    )
    return req


def reject_leave(
    db: Session,
    company_id: str,
    request_id: str,
    reviewer: User,
    comment: str | None = None,
) -> LeaveRequest:
    """Reject a pending leave request, releasing its pending days."""
    req = _get_request(db, company_id, request_id)
    if req.status != LeaveStatus.PENDING:
        raise ValidationError("only pending leave requests can be rejected")
    balance = _get_balance(db, company_id, req.employee_id, req.leave_type_id, req.start_date.year)
    if balance is not None:
        balance.pending_days -= req.days
        balance.remaining_days = balance.entitled_days - balance.used_days - balance.pending_days
    req.status = LeaveStatus.REJECTED
    req.reviewed_by = str(reviewer.id)
    req.reviewed_at = datetime.now(timezone.utc)
    req.review_comment = comment
    db.flush()
    db.commit()
    db.refresh(req)
    log_audit(
        db,
        "leave.reject",
        entity_type="leave_request",
        entity_id=str(req.id),
        new_value={"status": req.status.value, "days": req.days},
        company_id=str(company_id),
        user_id=str(reviewer.id),
    )
    return req


def cancel_leave(db: Session, company_id: str, request_id: str, reviewer: User) -> None:
    """Cancel a pending or approved leave request and adjust balances."""
    req = _get_request(db, company_id, request_id)
    if req.status not in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
        raise ValidationError("only pending or approved leave requests can be cancelled")
    balance = _get_balance(db, company_id, req.employee_id, req.leave_type_id, req.start_date.year)
    if balance is not None:
        if req.status == LeaveStatus.PENDING:
            balance.pending_days -= req.days
        else:
            balance.used_days -= req.days
        balance.remaining_days = balance.entitled_days - balance.used_days - balance.pending_days
    req.status = LeaveStatus.CANCELLED
    req.reviewed_by = str(reviewer.id)
    req.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    db.commit()


def get_balances(
    db: Session,
    company_id: str,
    employee_id: str | None = None,
    year: int | None = None,
) -> list[LeaveBalance]:
    """List leave balances of a company with optional employee and year filters."""
    stmt = select(LeaveBalance).where(LeaveBalance.company_id == company_id)
    if employee_id:
        stmt = stmt.where(LeaveBalance.employee_id == employee_id)
    if year:
        stmt = stmt.where(LeaveBalance.year == year)
    return list(db.scalars(stmt.order_by(LeaveBalance.year, LeaveBalance.created_at)))


def init_balances(db: Session, company_id: str, year: int) -> dict:
    """Create leave balance rows for each active employee and leave type for a year."""
    employee_ids = list(
        db.scalars(
            select(Employee.id).where(
                Employee.company_id == company_id,
                Employee.status == EmployeeStatus.ACTIVE,
            )
        )
    )
    leave_types = list(db.scalars(select(LeaveType).where(LeaveType.company_id == company_id)))
    created = 0
    for emp_id in employee_ids:
        for lt in leave_types:
            existing = _get_balance(db, company_id, str(emp_id), str(lt.id), year)
            if existing is not None:
                continue
            entitled = float(lt.days_per_year or 0)
            db.add(
                LeaveBalance(
                    company_id=str(company_id),
                    employee_id=str(emp_id),
                    leave_type_id=str(lt.id),
                    year=year,
                    entitled_days=entitled,
                    used_days=0.0,
                    pending_days=0.0,
                    remaining_days=entitled,
                )
            )
            created += 1
    db.flush()
    db.commit()
    return {"created": created}


def approved_leave_days_between(
    db: Session,
    company_id: str,
    employee_id: str,
    from_date: date,
    to_date: date,
) -> float:
    """Return the sum of approved leave days overlapping a date range."""
    total = db.scalar(
        select(func.coalesce(func.sum(LeaveRequest.days), 0)).where(
            LeaveRequest.company_id == str(company_id),
            LeaveRequest.employee_id == str(employee_id),
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= to_date,
            LeaveRequest.end_date >= from_date,
        )
    )
    return float(total or 0)