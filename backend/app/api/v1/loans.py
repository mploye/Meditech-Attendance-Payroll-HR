"""Loan and salary advance endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.user import User
from schemas.loan import AdvanceApproveRequest, AdvanceCreateRequest, LoanCreateRequest
from services import advance_service, loan_service

router = APIRouter(tags=["loans"])


@router.get("/loans")
def list_loans(
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.view")
    scope = company_scope(user=user)
    rows = loan_service.list_loans(db, scope, employee_id=employee_id)
    return success_response(orm_to_dict(rows))


@router.post("/loans")
def create_loan(
    payload: LoanCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.create")
    scope = company_scope(user=user)
    loan = loan_service.create_loan(
        db,
        scope,
        payload.employee_id,
        loan_amount=payload.loan_amount,
        installment_amount=payload.installment_amount,
        number_of_installments=payload.number_of_installments,
        start_date=payload.start_date,
        interest_rate=payload.interest_rate,
        remarks=payload.remarks,
    )
    return success_response(orm_to_dict(loan))


@router.post("/loans/{loan_id}/installments/{installment_no}/pay")
def pay_installment(
    loan_id: str,
    installment_no: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.edit")
    loan_service.mark_installment_paid(db, loan_id, installment_no, payroll_period_id="")
    return success_response({"message": "installment paid"})


@router.get("/advances")
def list_advances(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.view")
    scope = company_scope(user=user)
    rows = advance_service.list_advances(db, scope, employee_id=employee_id, status=status)
    return success_response(orm_to_dict(rows))


@router.post("/advances")
def request_advance(
    payload: AdvanceCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.create")
    scope = company_scope(user=user)
    advance = advance_service.request_advance(
        db,
        scope,
        payload.employee_id,
        requested_amount=payload.requested_amount,
        deduction_installments=payload.deduction_installments,
        deduction_start_month=payload.deduction_start_month,
        remarks=payload.remarks,
    )
    return success_response(orm_to_dict(advance))


@router.post("/advances/{advance_id}/approve")
def approve_advance(
    advance_id: str,
    payload: AdvanceApproveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.edit")
    scope = company_scope(user=user)
    advance = advance_service.approve_advance(db, scope, advance_id, user, approved_amount=payload.approved_amount)
    return success_response(orm_to_dict(advance))


@router.post("/advances/{advance_id}/reject")
def reject_advance(
    advance_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.edit")
    scope = company_scope(user=user)
    advance = advance_service.reject_advance(db, scope, advance_id, user)
    return success_response(orm_to_dict(advance))


@router.post("/advances/{advance_id}/close")
def close_advance(
    advance_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.edit")
    scope = company_scope(user=user)
    advance = advance_service.close_advance(db, scope, advance_id, user)
    return success_response(orm_to_dict(advance))