from datetime import date

import pytest

from core.errors import ConflictError
from models.enums import PayrollPeriodStatus, PayrollRecordStatus
from services import loan_service, payroll_service

from tests.conftest import make_company, make_employee, make_salary_structure, make_shift, make_user


@pytest.fixture()
def ctx(db):
    company = make_company(db)
    shift = make_shift(db, str(company.id))
    structure = make_salary_structure(db, str(company.id), basic=40000.0)
    emp = make_employee(db, str(company.id), code="P001", salary_structure_id=str(structure.id))
    reviewer = make_user(db, str(company.id), "payroll@example.com", role="PAYROLL_ADMIN")
    return {
        "company_id": str(company.id),
        "employee_id": str(emp.id),
        "reviewer": reviewer,
        "shift": shift,
    }


def test_period_lifecycle(db, ctx):
    period = payroll_service.create_period(db, ctx["company_id"], 1, 2024)
    assert period.status == PayrollPeriodStatus.DRAFT

    with pytest.raises(ConflictError):
        payroll_service.create_period(db, ctx["company_id"], 1, 2024)

    result = payroll_service.calculate_period(db, ctx["company_id"], str(period.id))
    assert result["employees_processed"] == 1
    assert result["net"] > 0
    assert payroll_service.get_period(db, ctx["company_id"], str(period.id)).status == PayrollPeriodStatus.REVIEW

    review = payroll_service.review_period(db, ctx["company_id"], str(period.id), ctx["reviewer"])
    assert review.status == PayrollPeriodStatus.REVIEW

    approved = payroll_service.approve_period(db, ctx["company_id"], str(period.id), ctx["reviewer"])
    assert approved.status == PayrollPeriodStatus.APPROVED

    locked = payroll_service.lock_period(db, ctx["company_id"], str(period.id), ctx["reviewer"])
    assert locked.status == PayrollPeriodStatus.LOCKED

    records = payroll_service.get_period_records(db, str(period.id))
    assert len(records) == 1
    assert records[0].status == PayrollRecordStatus.LOCKED
    assert records[0].net_salary > 0


def test_cannot_approve_uncalculated_period(db, ctx):
    period = payroll_service.create_period(db, ctx["company_id"], 2, 2024)
    with pytest.raises(ConflictError):
        payroll_service.approve_period(db, ctx["company_id"], str(period.id), ctx["reviewer"])


def test_monthly_summary(db, ctx):
    period = payroll_service.create_period(db, ctx["company_id"], 3, 2024)
    payroll_service.calculate_period(db, ctx["company_id"], str(period.id))
    summary = payroll_service.monthly_summary(db, ctx["company_id"], 3, 2024)
    assert summary["employees"] == 1
    assert summary["status"] == "REVIEW"
    assert summary["net"] > 0


def test_loan_installment_lifecycle(db, ctx):
    from sqlalchemy import select

    from models.enums import LoanStatus
    from models.loan import LoanInstallment

    loan = loan_service.create_loan(
        db,
        ctx["company_id"],
        ctx["employee_id"],
        loan_amount=12000.0,
        installment_amount=1000.0,
        number_of_installments=12,
        start_date=date(2024, 1, 1),
        interest_rate=0.0,
        remarks="test",
    )
    assert loan.outstanding_amount == 12000.0

    installments = list(
        db.scalars(select(LoanInstallment).where(LoanInstallment.loan_id == loan.id))
    )
    assert len(installments) == 12
    assert all(i.status == "PENDING" for i in installments)

    loan_service.mark_installment_paid(db, str(loan.id), 1, None)
    db.refresh(loan)
    assert loan.outstanding_amount == 11000.0
    assert loan.paid_installments == 1
    assert loan.status == LoanStatus.ACTIVE

    for i in range(2, 13):
        loan_service.mark_installment_paid(db, str(loan.id), i, None)
    db.refresh(loan)
    assert loan.outstanding_amount == 0.0
    assert loan.status == LoanStatus.CLOSED

    remaining_pending = list(
        db.scalars(
            select(LoanInstallment).where(
                LoanInstallment.loan_id == loan.id, LoanInstallment.status == "PENDING"
            )
        )
    )
    assert remaining_pending == []
