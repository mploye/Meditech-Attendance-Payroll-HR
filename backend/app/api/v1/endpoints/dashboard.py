from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import ensure_perm, get_current_user, get_db, resolve_company_id
from core.errors import success_response
from models.user import User
from services import dashboard_service

router = APIRouter()


def _today() -> date:
    return date.today()


@router.get("/summary")
def summary(
    day: Optional[date] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    cid = resolve_company_id(user)
    return success_response(dashboard_service.summary(db, cid, day or _today()))


@router.get("/attendance-trend")
def attendance_trend(
    days: int = Query(14, ge=1, le=90),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    cid = resolve_company_id(user)
    return success_response(dashboard_service.attendance_trend(db, cid, days))


@router.get("/payroll-trend")
def payroll_trend(
    months: int = Query(6, ge=1, le=24),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    cid = resolve_company_id(user)
    return success_response(dashboard_service.payroll_trend(db, cid, months))


@router.get("/department-attendance")
def department_attendance(
    start_date: date,
    end_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    cid = resolve_company_id(user)
    end = end_date or start_date
    return success_response(dashboard_service.department_attendance(db, cid, start_date, end))


@router.get("/employee-growth")
def employee_growth(
    months: int = Query(6, ge=1, le=24),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    cid = resolve_company_id(user)
    return success_response(dashboard_service.employee_growth(db, cid, months))