from datetime import date, datetime, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from core.errors import NotFoundError
from models.employee import Employee
from models.enums import LoanStatus
from models.loan import EmployeeLoan, LoanInstallment
from models.payroll import PayrollPeriod


def _add_months(value: date, months: int) -> date:
    return value + relativedelta(months=months)


def create_loan(
    db: Session,
    company_id: str,
    employee_id: str,
    *,
    loan_amount: float,
    installment_amount: float,
    number_of_installments: int,
    start_date: date | None = None,
    interest_rate: float = 0,
    remarks: str | None = None,
) -> EmployeeLoan:
    """Create an employee loan with a full schedule of pending installments."""
    start = start_date or date.today()
    loan = EmployeeLoan(
        company_id=company_id,
        employee_id=employee_id,
        loan_amount=float(loan_amount or 0),
        start_date=start,
        installment_amount=float(installment_amount or 0),
        number_of_installments=int(number_of_installments or 1),
        paid_installments=0,
        outstanding_amount=float(loan_amount or 0),
        interest_rate=float(interest_rate or 0),
        status=LoanStatus.ACTIVE,
        remarks=remarks,
    )
    db.add(loan)
    db.flush()
    for i in range(1, int(number_of_installments or 1) + 1):
        db.add(
            LoanInstallment(
                company_id=company_id,
                loan_id=loan.id,
                installment_no=i,
                due_date=_add_months(start, i),
                amount=float(installment_amount or 0),
                status="PENDING",
            )
        )
    db.commit()
    db.refresh(loan)
    return loan


def list_loans(
    db: Session,
    company_id: str,
    employee_id: str | None = None,
) -> list[EmployeeLoan]:
    """List loans for a company, optionally filtered by employee."""
    stmt = select(EmployeeLoan).where(EmployeeLoan.company_id == company_id)
    if employee_id:
        stmt = stmt.where(EmployeeLoan.employee_id == employee_id)
    return list(db.scalars(stmt.order_by(EmployeeLoan.created_at.desc())))


def _due_installments(
    db: Session, company_id: str, employee_id: str, end_date: date
) -> list[tuple[EmployeeLoan, LoanInstallment]]:
    """Return (loan, installment) pairs pending and due for an employee by a date."""
    stmt = (
        select(EmployeeLoan, LoanInstallment)
        .join(LoanInstallment, LoanInstallment.loan_id == EmployeeLoan.id)
        .where(
            and_(
                EmployeeLoan.company_id == company_id,
                EmployeeLoan.employee_id == employee_id,
                LoanInstallment.status == "PENDING",
                LoanInstallment.due_date <= end_date,
            )
        )
        .order_by(LoanInstallment.due_date)
    )
    return list(db.execute(stmt).all())


def first_due_loan_id(
    db: Session, company_id: str, employee_id: str, period: PayrollPeriod
) -> str | None:
    """Return the loan id with the earliest pending installment due in a period."""
    pairs = _due_installments(db, company_id, employee_id, period.end_date)
    return str(pairs[0][0].id) if pairs else None


def due_instalment_amount(
    db: Session, company_id: str, employee_id: str, period: PayrollPeriod
) -> float:
    """Sum pending installment amounts due for an employee up to period end."""
    pairs = _due_installments(db, company_id, employee_id, period.end_date)
    return round(sum(float(pair[1].amount or 0) for pair in pairs), 2)


def mark_installment_paid(
    db: Session, loan_id: str, installment_no: int, payroll_period_id: str
) -> None:
    """Mark a loan installment paid and reconcile the loan balance."""
    installment = db.scalar(
        select(LoanInstallment).where(
            LoanInstallment.loan_id == loan_id,
            LoanInstallment.installment_no == installment_no,
        )
    )
    if installment is None:
        raise NotFoundError("LoanInstallment")
    installment.status = "PAID"
    installment.paid_in_payroll_period_id = payroll_period_id
    loan = db.get(EmployeeLoan, loan_id)
    if loan is None:
        raise NotFoundError("EmployeeLoan")
    loan.paid_installments = int(loan.paid_installments or 0) + 1
    loan.outstanding_amount = round(float(loan.outstanding_amount or 0) - float(installment.amount or 0), 2)
    if loan.paid_installments >= int(loan.number_of_installments or 1):
        loan.status = LoanStatus.CLOSED
        loan.outstanding_amount = 0.0
    db.commit()