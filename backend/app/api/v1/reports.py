"""Report export endpoints under /reports."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.user import User
from services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


def _handle(rows_result, fmt: str = "json"):
    if fmt == "json":
        return success_response(rows_result)
    path = rows_result
    return FileResponse(path, media_type="application/octet-stream")


@router.get("/attendance/daily")
def attendance_daily(
    from_date: date,
    to_date: date,
    format: str = "json",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    result = report_service.attendance_daily_rows(db, scope, from_date, to_date, format=format)
    return success_response(result)


@router.get("/attendance/monthly")
def attendance_monthly(
    month: int,
    year: int,
    format: str = "json",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    return success_response(report_service.attendance_monthly_rows(db, scope, month, year))


@router.get("/attendance/employee")
def attendance_employee(
    employee_id: str,
    from_date: date,
    to_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    from services import attendance_service

    result = attendance_service.get_daily_summary(db, scope, employee_id, from_date, to_date)
    return success_response(result)


@router.get("/attendance/late")
def attendance_late(
    from_date: date,
    to_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    rows = report_service.attendance_daily_rows(db, scope, from_date, to_date, format="json")
    late = [r for r in rows.get("rows", []) if int(r.get("late") or 0) > 0]
    return success_response({"rows": late, "count": len(late)})


@router.get("/attendance/missing-punch")
def attendance_missing_punch(
    from_date: date,
    to_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    rows = report_service.attendance_daily_rows(db, scope, from_date, to_date, format="json")
    missing = [r for r in rows.get("rows", []) if not r.get("first_in") or not r.get("last_out")]
    return success_response({"rows": missing, "count": len(missing)})


@router.get("/payroll/monthly")
def payroll_monthly(
    payroll_period_id: str,
    format: str = "json",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    return success_response(report_service.payroll_monthly_rows(db, scope, payroll_period_id))


@router.get("/payroll/salary-register")
def payroll_salary_register(
    payroll_period_id: str,
    format: str = "json",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    return success_response(report_service.payroll_salary_register_rows(db, scope, payroll_period_id))


@router.get("/payroll/deductions")
def payroll_deductions(
    payroll_period_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    return success_response(report_service.deduction_summary_rows(db, scope, payroll_period_id))


@router.get("/loans")
def loans_report(
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "reports.view")
    scope = company_scope(user=user)
    return success_response(report_service.loans_report_rows(db, scope, employee_id=employee_id))