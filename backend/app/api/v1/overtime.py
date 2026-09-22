"""Overtime endpoints under /overtime."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.user import User
from schemas.overtime import OvertimeCreateRequest, OvertimeReviewRequest
from services import overtime_service

router = APIRouter(prefix="/overtime", tags=["overtime"])


@router.get("")
def list_overtime(
    status: Optional[str] = None,
    employee_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "overtime.view")
    scope = company_scope(user=user)
    rows = overtime_service.list_overtime(
        db, scope, status=status, employee_id=employee_id, from_date=from_date, to_date=to_date
    )
    return success_response(orm_to_dict(rows))


@router.post("")
def create_overtime(
    payload: OvertimeCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "overtime.create")
    scope = company_scope(user=user)
    record = overtime_service.create_overtime(
        db,
        scope,
        payload.employee_id,
        date=payload.date,
        minutes=payload.minutes,
        rate=payload.rate,
        remarks=payload.remarks,
    )
    return success_response(orm_to_dict(record))


@router.post("/{record_id}/approve")
def approve_overtime(
    record_id: str,
    payload: OvertimeReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "overtime.approve")
    scope = company_scope(user=user)
    record = overtime_service.approve_overtime(db, scope, record_id, user)
    return success_response(orm_to_dict(record))


@router.post("/{record_id}/reject")
def reject_overtime(
    record_id: str,
    payload: OvertimeReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "overtime.approve")
    scope = company_scope(user=user)
    record = overtime_service.reject_overtime(db, scope, record_id, user)
    return success_response(orm_to_dict(record))