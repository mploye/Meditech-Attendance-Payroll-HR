"""Dashboard aggregation endpoints under /dashboard."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.user import User
from services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    scope = company_scope(user=user)
    return success_response(dashboard_service.summary(db, scope, date.today()))


@router.get("/attendance-trend")
def attendance_trend(
    days: int = Query(14, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    scope = company_scope(user=user)
    return success_response(dashboard_service.attendance_trend(db, scope, days=days))


@router.get("/payroll-trend")
def payroll_trend(
    months: int = Query(6, ge=1, le=24),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    scope = company_scope(user=user)
    return success_response(dashboard_service.payroll_trend(db, scope, months=months))


@router.get("/department-attendance")
def department_attendance(
    start_date: date,
    end_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "dashboard.view")
    scope = company_scope(user=user)
    return success_response(dashboard_service.department_attendance(db, scope, start_date, end_date))