from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from api.deps import ensure_perm, get_current_user, get_db, resolve_company_id
from core.errors import NotFoundError, success_response
from models.user import User
from services import report_service

router = APIRouter()

_FORMATS = {"json", "csv", "xlsx", "pdf"}
_MEDIA = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _file(path, fmt: str):
    if not path or not Path(path).exists():
        raise NotFoundError("Report file")
    return FileResponse(path, media_type=_MEDIA[fmt], filename=Path(path).name)


@router.get("/attendance/daily")
def attendance_daily(
    from_date: date,
    to_date: date,
    format: str = "json",
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "reports.view")
    cid = resolve_company_id(user)
    fmt = format if format in _FORMATS else "json"
    result = report_service.attendance_daily_rows(db, cid, from_date, to_date, fmt)
    if fmt == "json":
        return success_response(result["rows"])
    return _file(result["path"], fmt)


@router.get("/attendance/monthly")
def attendance_monthly(
    month: int,
    year: int,
    format: str = "json",
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "reports.view")
    cid = resolve_company_id(user)
    fmt = format if format in _FORMATS else "json"
    rows = report_service.attendance_monthly_rows(db, cid, month, year)
    if fmt == "json":
        return success_response(rows)
    path = report_service.export_report(db, cid, f"attendance_monthly_{year}_{month:02d}", rows, fmt)
    return _file(path, fmt)


@router.get("/payroll/salary-register")
def salary_register(
    payroll_period_id: str | None = None,
    month: int | None = None,
    year: int | None = None,
    format: str = "json",
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "reports.view")
    cid = resolve_company_id(user)
    fmt = format if format in _FORMATS else "json"
    period_id = report_service._resolve_period_id(db, cid, payroll_period_id, month, year)
    rows = report_service.payroll_salary_register_rows(db, cid, period_id)
    if fmt == "json":
        return success_response(rows)
    path = report_service.export_report(db, cid, f"salary_register_{period_id}", rows, fmt)
    return _file(path, fmt)


@router.get("/payroll/monthly")
def payroll_monthly(
    payroll_period_id: str | None = None,
    month: int | None = None,
    year: int | None = None,
    format: str = "json",
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "reports.view")
    cid = resolve_company_id(user)
    fmt = format if format in _FORMATS else "json"
    period_id = report_service._resolve_period_id(db, cid, payroll_period_id, month, year)
    rows = report_service.payroll_monthly_rows(db, cid, period_id)
    if fmt == "json":
        return success_response(rows)
    path = report_service.export_report(db, cid, f"payroll_monthly_{period_id}", rows, fmt)
    return _file(path, fmt)


@router.get("/payroll/deductions")
def deduction_summary(
    payroll_period_id: str | None = None,
    month: int | None = None,
    year: int | None = None,
    format: str = "json",
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "reports.view")
    cid = resolve_company_id(user)
    fmt = format if format in _FORMATS else "json"
    period_id = report_service._resolve_period_id(db, cid, payroll_period_id, month, year)
    rows = report_service.deduction_summary_rows(db, cid, period_id)
    if fmt == "json":
        return success_response(rows)
    path = report_service.export_report(db, cid, f"deduction_summary_{period_id}", rows, fmt)
    return _file(path, fmt)


@router.get("/loans")
def loans_report(
    format: str = "json",
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "reports.view")
    cid = resolve_company_id(user)
    fmt = format if format in _FORMATS else "json"
    rows = report_service.loans_report_rows(db, cid)
    if fmt == "json":
        return success_response(rows)
    path = report_service.export_report(db, cid, "loans_report", rows, fmt)
    return _file(path, fmt)