from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pathlib import Path

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.payroll import PayrollPeriod
from models.user import User
from services import payslip_service

router = APIRouter()


@router.post("/generate")
def generate(
    payroll_period_id: str = Query(...),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "payslips.generate")
    cid = resolve_company_id(user)
    period = db.get(PayrollPeriod, payroll_period_id)
    if period is None or str(period.company_id) != cid:
        raise NotFoundError("Payroll period")
    result = payslip_service.generate_for_period(db, cid, payroll_period_id)
    db.commit()
    return success_response(result)


@router.get("/")
def list_payslips(
    payroll_period_id: str | None = None,
    employee_id: str | None = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "payslips.view")
    cid = resolve_company_id(user)
    rows = payslip_service.list_payslips(db, cid, payroll_period_id, employee_id)
    return success_response([orm_to_dict(r) for r in rows])


@router.get("/mine")
def my_payslips(
    month: int | None = None,
    year: int | None = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    if not user.employee_id:
        raise NotFoundError("Employee profile not linked")
    rows = payslip_service.employee_payslips(db, str(user.company_id), str(user.employee_id), month, year)
    return success_response([orm_to_dict(r) for r in rows])


@router.post("/mine/{payslip_id}/download")
def mark_downloaded(payslip_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    if not user.employee_id:
        raise NotFoundError("Employee profile not linked")
    from models.enums import PayslipStatus

    row = payslip_service.get_payslip(db, str(user.company_id), payslip_id)
    if str(row.employee_id) != str(user.employee_id):
        raise NotFoundError("Payslip")
    row.status = PayslipStatus.DOWNLOADED
    db.commit()
    return success_response({"downloaded": True})


@router.get("/{payslip_id}/pdf")
def download_pdf(payslip_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    cid = resolve_company_id(user)
    row = payslip_service.get_payslip(db, cid, payslip_id)
    path = payslip_service.build_payslip_pdf(db, row)
    if not path or not Path(path).exists():
        raise NotFoundError("Payslip PDF")
    return FileResponse(path, media_type="application/pdf", filename=Path(path).name)