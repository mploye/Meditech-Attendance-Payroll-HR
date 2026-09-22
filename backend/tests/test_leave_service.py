from datetime import date

import pytest

from core.errors import ValidationError
from models.enums import LeaveStatus
from services import leave_service

from tests.conftest import make_company, make_employee, make_shift, make_user


def _balance(db, ctx):
    balances = leave_service.get_balances(
        db, ctx["company_id"], employee_id=ctx["employee_id"], year=2024
    )
    return balances[0]


@pytest.fixture()
def ctx(db):
    company = make_company(db)
    shift = make_shift(db, str(company.id))
    emp = make_employee(db, str(company.id), code="L001")
    reviewer = make_user(db, str(company.id), "reviewer@example.com", role="HR_ADMIN")
    lt = leave_service.create_leave_type(
        db,
        str(company.id),
        {"name": "Casual Leave", "code": "CL", "days_per_year": 10},
    )
    return {
        "company_id": str(company.id),
        "employee_id": str(emp.id),
        "type_id": str(lt.id),
        "reviewer": reviewer,
        "shift": shift,
    }


def test_apply_and_approve_leave_moves_balance(db, ctx):
    req = leave_service.apply_leave(
        db,
        ctx["company_id"],
        ctx["employee_id"],
        leave_type_id=ctx["type_id"],
        start_date=date(2024, 3, 4),
        end_date=date(2024, 3, 6),
        reason="travel",
    )
    assert req.status == LeaveStatus.PENDING
    assert req.days == 3

    balance = _balance(db, ctx)
    assert balance.pending_days == 3
    assert balance.remaining_days == 7

    approved = leave_service.approve_leave(
        db, ctx["company_id"], str(req.id), ctx["reviewer"]
    )
    assert approved.status == LeaveStatus.APPROVED

    balance = _balance(db, ctx)
    assert balance.used_days == 3
    assert balance.remaining_days == 7


def test_reject_leave_restores_balance(db, ctx):
    req = leave_service.apply_leave(
        db,
        ctx["company_id"],
        ctx["employee_id"],
        leave_type_id=ctx["type_id"],
        start_date=date(2024, 3, 4),
        end_date=date(2024, 3, 4),
    )
    leave_service.reject_leave(db, ctx["company_id"], str(req.id), ctx["reviewer"])
    balance = _balance(db, ctx)
    assert balance.pending_days == 0
    assert balance.remaining_days == 10


def test_apply_leave_exceeding_balance_rejected(db, ctx):
    with pytest.raises(ValidationError):
        leave_service.apply_leave(
            db,
            ctx["company_id"],
            ctx["employee_id"],
            leave_type_id=ctx["type_id"],
            start_date=date(2024, 3, 4),
            end_date=date(2024, 3, 20),
        )


def test_init_balances_seeds_entitlement(db, ctx):
    result = leave_service.init_balances(db, ctx["company_id"], 2024)
    assert result.get("created", 0) >= 1
    balances = leave_service.get_balances(db, ctx["company_id"], employee_id=ctx["employee_id"], year=2024)
    assert any(b.entitled_days == 10 for b in balances)
