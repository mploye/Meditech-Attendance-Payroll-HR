"""Payslip endpoints under /payslips."""

from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import NotFoundError, success_response
from models.user import User
from schemas.payslip_generate import PayslipGenerateRequest
from services import payslip_service

router = APIRouter(prefix="/payslips", tags=["payslips"])


@router.post("/generate")
def generate_payslips(
    payload: PayslipGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payslips.generate")
    scope = company_scope(user=user)
    result = payslip_service.generate_for_period(db, scope, payload.payroll_period_id)
    return success_response(result)


@router.get("")
def list_payslips(
    payroll_period_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payslips.view")
    scope = company_scope(user=user)
    rows = payslip_service.list_payslips(db, scope, payroll_period_id=payroll_period_id, employee_id=employee_id)
    return success_response(orm_to_dict(rows))


@router.get("/mine")
def my_payslips(
    month: Optional[int] = None,
    year: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payslips.view.own")
    scope = company_scope(user=user)
    employee_id = str(user.employee_id) if user.employee_id else None
    if employee_id is None:
        return success_response([])
    rows = payslip_service.employee_payslips(db, scope, employee_id, month=month, year=year)
    return success_response(orm_to_dict(rows))


@router.get("/{payslip_id}")
def get_payslip(
    payslip_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payslips.view")
    scope = company_scope(user=user)
    slip = payslip_service.get_payslip(db, scope, payslip_id)
    if user.role.value == "EMPLOYEE" and user.employee_id != slip.employee_id:
        raise NotFoundError("Payslip")
    return success_response(orm_to_dict(slip))


@router.post("/mine/{payslip_id}/download")
def mark_payslip_downloaded(
    payslip_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payslips.download.own")
    scope = company_scope(user=user)
    slip = payslip_service.get_payslip(db, scope, payslip_id)
    if user.role.value == "EMPLOYEE" and user.employee_id != slip.employee_id:
        raise NotFoundError("Payslip")
    updated = payslip_service.mark_downloaded(db, slip)
    return success_response(orm_to_dict(updated))


@router.get("/{payslip_id}/pdf")
def payslip_pdf(
    payslip_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "payslips.view")
    scope = company_scope(user=user)
    slip = payslip_service.get_payslip(db, scope, payslip_id)
    if user.role.value == "EMPLOYEE" and user.employee_id != slip.employee_id:
        raise NotFoundError("Payslip")
    path = payslip_service.build_payslip_pdf(db, slip)
    return FileResponse(path, media_type="application/pdf", filename=f"payslip-{slip.id}.pdf")