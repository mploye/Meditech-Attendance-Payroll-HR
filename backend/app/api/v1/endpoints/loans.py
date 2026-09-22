from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.loan import EmployeeLoan
from models.user import User
from services import loan_service

router = APIRouter()


def _loan_dict(db, loan: EmployeeLoan) -> dict:
    data = orm_to_dict(loan)
    emp = db.get(EmployeeLoan, loan.id)
    from models.employee import Employee

    employee = db.get(Employee, loan.employee_id)
    if employee:
        data["employee_code"] = employee.employee_code
        data["employee_name"] = f"{employee.first_name} {employee.last_name or ''}"
    return data


@router.get("/")
def list_loans(
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "loans.view")
    cid = resolve_company_id(user)
    rows = loan_service.list_loans(db, cid, employee_id)
    return success_response([_loan_dict(db, loan) for loan in rows])


@router.post("/")
def create_loan(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "loans.create")
    cid = resolve_company_id(user)
    loan = loan_service.create_loan(
        db,
        cid,
        body["employee_id"],
        loan_amount=float(body["loan_amount"]),
        installment_amount=float(body["installment_amount"]),
        number_of_installments=int(body["number_of_installments"]),
        start_date=date.fromisoformat(body["start_date"]) if body.get("start_date") else None,
        interest_rate=float(body.get("interest_rate", 0)),
        remarks=body.get("remarks"),
    )
    return success_response(_loan_dict(db, loan))


@router.post("/{loan_id}/pay")
def pay_installment(
    loan_id: str,
    body: Optional[dict] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "loans.edit")
    cid = resolve_company_id(user)
    from models.loan import EmployeeLoan, LoanInstallment
    from sqlalchemy import select

    loan = db.get(EmployeeLoan, loan_id)
    if loan is None or str(loan.company_id) != cid:
        raise NotFoundError("Loan")
    body = body or {}
    installment_no = body.get("installment_no")
    if installment_no is None:
        next_pending = db.scalar(
            select(LoanInstallment.installment_no)
            .where(LoanInstallment.loan_id == loan_id, LoanInstallment.status == "PENDING")
            .order_by(LoanInstallment.installment_no)
            .limit(1)
        )
        if next_pending is None:
            raise NotFoundError("Pending installment")
        installment_no = int(next_pending)
    loan_service.mark_installment_paid(
        db, loan_id, installment_no=int(installment_no), payroll_period_id=body.get("payroll_period_id")
    )
    db.refresh(loan)
    return success_response(_loan_dict(db, loan))