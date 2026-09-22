"""Leave endpoints under /leaves."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict, page_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import ValidationError, success_response
from models.user import User
from schemas.leave import LeaveApplyRequest, LeaveDecisionRequest, LeaveTypeCreateRequest, LeaveTypeUpdateRequest
from services import leave_service

router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.get("/types")
def list_leave_types(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.view")
    scope = company_scope(user=user)
    return success_response(orm_to_dict(leave_service.list_leave_types(db, scope)))


@router.post("/types")
def create_leave_type(
    payload: LeaveTypeCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.create")
    scope = company_scope(user=user)
    lt = leave_service.create_leave_type(db, scope, payload.model_dump())
    return success_response(orm_to_dict(lt))


@router.patch("/types/{leave_type_id}")
def update_leave_type(
    leave_type_id: str,
    payload: LeaveTypeUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.edit")
    scope = company_scope(user=user)
    lt = leave_service.update_leave_type(db, scope, leave_type_id, payload.model_dump(exclude_unset=True))
    return success_response(orm_to_dict(lt))


@router.get("/requests")
def list_leave_requests(
    status: Optional[str] = None,
    employee_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.view")
    scope = company_scope(user=user)
    if user.role.value == "EMPLOYEE":
        employee_id = str(user.employee_id) if user.employee_id else employee_id
    result = leave_service.list_leave_requests(
        db, scope, status=status, employee_id=employee_id, page=page, page_size=page_size
    )
    return success_response(page_dict(result))


@router.get("/balances")
def get_balances(
    year: Optional[int] = None,
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.view")
    scope = company_scope(user=user)
    if user.role.value == "EMPLOYEE":
        employee_id = str(user.employee_id) if user.employee_id else employee_id
    rows = leave_service.get_balances(db, scope, employee_id=employee_id, year=year)
    return success_response(orm_to_dict(rows))


@router.post("/balances/init")
def init_balances(
    year: int = Query(..., description="leave year to initialize"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.edit")
    scope = company_scope(user=user)
    result = leave_service.init_balances(db, scope, year)
    return success_response(result)


@router.post("/apply")
def apply_leave(
    payload: LeaveApplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.create")
    scope = company_scope(user=user)
    emp_id = payload.employee_id or (str(user.employee_id) if user.employee_id else None)
    if not emp_id:
        raise ValidationError("employee_id is required")
    request = leave_service.apply_leave(
        db,
        scope,
        emp_id,
        leave_type_id=payload.leave_type_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        is_half_day=payload.is_half_day,
    )
    return success_response(orm_to_dict(request))


@router.post("/{request_id}/approve")
def approve_leave(
    request_id: str,
    payload: LeaveDecisionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.approve")
    scope = company_scope(user=user)
    request = leave_service.approve_leave(db, scope, request_id, user, comment=payload.comment)
    return success_response(orm_to_dict(request))


@router.post("/{request_id}/reject")
def reject_leave(
    request_id: str,
    payload: LeaveDecisionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "leaves.approve")
    scope = company_scope(user=user)
    request = leave_service.reject_leave(db, scope, request_id, user, comment=payload.comment)
    return success_response(orm_to_dict(request))