"""Payroll endpoints under /payroll."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.user import User
from schemas.payroll import PayrollPeriodCreate
from services import payroll_service

router = APIRouter(prefix="/payroll", tags=["payroll"])


@router.get("/periods")
def list_periods(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.view")
    scope = company_scope(user=user)
    rows = payroll_service.get_periods(db, scope)
    return success_response(orm_to_dict(rows))


@router.post("/periods")
def create_period(
    payload: PayrollPeriodCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.create")
    scope = company_scope(user=user)
    period = payroll_service.create_period(db, scope, payload.month, payload.year)
    return success_response(orm_to_dict(period))


@router.get("/periods/{period_id}")
def get_period(
    period_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.view")
    scope = company_scope(user=user)
    period = payroll_service.get_period(db, scope, period_id)
    return success_response(orm_to_dict(period))


@router.post("/periods/{period_id}/calculate")
def calculate_period(
    period_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.calculate")
    scope = company_scope(user=user)
    result = payroll_service.calculate_period(db, scope, period_id)
    return success_response(result)


@router.post("/periods/{period_id}/review")
def review_period(
    period_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.review")
    scope = company_scope(user=user)
    period = payroll_service.review_period(db, scope, period_id, user)
    return success_response(orm_to_dict(period))


@router.post("/periods/{period_id}/approve")
def approve_period(
    period_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.approve")
    scope = company_scope(user=user)
    period = payroll_service.approve_period(db, scope, period_id, user)
    return success_response(orm_to_dict(period))


@router.post("/periods/{period_id}/lock")
def lock_period(
    period_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.lock")
    scope = company_scope(user=user)
    period = payroll_service.lock_period(db, scope, period_id, user)
    return success_response(orm_to_dict(period))


@router.get("/periods/{period_id}/records")
def period_records(
    period_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.view")
    scope = company_scope(user=user)
    payroll_service.get_period(db, scope, period_id)
    rows = payroll_service.get_period_records(db, period_id)
    return success_response(orm_to_dict(rows))


@router.get("/records/{record_id}")
def record_detail(
    record_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.view")
    result = payroll_service.get_record_details(db, record_id)
    return success_response(result)


@router.get("/summary")
def payroll_summary(
    month: int,
    year: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payroll.view")
    scope = company_scope(user=user)
    result = payroll_service.monthly_summary(db, scope, month, year)
    result["period"] = orm_to_dict(result.get("period"))
    return success_response(result)