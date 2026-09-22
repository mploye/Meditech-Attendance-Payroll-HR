from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.employee import Employee
from models.payroll import PayrollPeriod, PayrollRecord
from models.user import User
from services import payroll_service

router = APIRouter()


def _period_dict(db, period: PayrollPeriod) -> dict:
    data = orm_to_dict(period)
    records = payroll_service.get_period_records(db, str(period.id))
    data["employees_processed"] = len(records)
    data["gross"] = round(sum(r.gross_salary for r in records), 2)
    data["deductions"] = round(sum(r.total_deductions for r in records), 2)
    data["net"] = round(sum(r.net_salary for r in records), 2)
    return data


@router.get("/periods")
def list_periods(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "payroll.view")
    cid = resolve_company_id(user)
    periods = payroll_service.get_periods(db, cid)
    return success_response([_period_dict(db, p) for p in periods])


@router.post("/periods")
def create_period(
    body: Optional[dict] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "payroll.create")
    cid = resolve_company_id(user)
    body = body or {}
    month = month or body.get("month")
    year = year or body.get("year")
    if not month or not year:
        from core.errors import ValidationError

        raise ValidationError("month and year are required")
    period = payroll_service.create_period(db, cid, int(month), int(year))
    return success_response(_period_dict(db, period))


@router.get("/periods/{period_id}")
def get_period(period_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "payroll.view")
    cid = resolve_company_id(user)
    period = payroll_service.get_period(db, cid, period_id)
    return success_response(_period_dict(db, period))


@router.post("/periods/{period_id}/calculate")
def calculate(period_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "payroll.calculate")
    cid = resolve_company_id(user)
    payroll_service.get_period(db, cid, period_id)
    result = payroll_service.calculate_period(db, cid, period_id)
    db.commit()
    return success_response(result)


@router.post("/periods/{period_id}/review")
def review(period_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "payroll.review")
    cid = resolve_company_id(user)
    period = payroll_service.review_period(db, cid, period_id, user)
    return success_response(_period_dict(db, period))


@router.post("/periods/{period_id}/approve")
def approve(period_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "payroll.approve")
    cid = resolve_company_id(user)
    period = payroll_service.approve_period(db, cid, period_id, user)
    return success_response(_period_dict(db, period))


@router.post("/periods/{period_id}/lock")
def lock(period_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "payroll.lock")
    cid = resolve_company_id(user)
    period = payroll_service.lock_period(db, cid, period_id, user)
    return success_response(_period_dict(db, period))


@router.get("/periods/{period_id}/records")
def period_records(period_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "payroll.view")
    cid = resolve_company_id(user)
    period = payroll_service.get_period(db, cid, period_id)
    records = payroll_service.get_period_records(db, str(period.id))
    items = []
    for record in records:
        data = orm_to_dict(record)
        emp = db.get(Employee, record.employee_id)
        data["employee_code"] = emp.employee_code if emp else None
        data["employee_name"] = f"{emp.first_name} {emp.last_name or ''}" if emp else None
        items.append(data)
    return success_response(items)


@router.get("/records/{record_id}")
def record_details(record_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "payroll.view")
    cid = resolve_company_id(user)
    record = db.get(PayrollRecord, record_id)
    if record is None or str(record.company_id) != cid:
        raise NotFoundError("Payroll record")
    details = payroll_service.get_record_details(db, record_id)
    emp = db.get(Employee, record.employee_id)
    result = {
        "record": orm_to_dict(record),
        "employee_code": emp.employee_code if emp else None,
        "employee_name": f"{emp.first_name} {emp.last_name or ''}" if emp else None,
        "components": [orm_to_dict(c) for c in details.get("components", [])],
    }
    return success_response(result)


@router.get("/summary")
def summary(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "payroll.view")
    cid = resolve_company_id(user)
    return success_response(payroll_service.monthly_summary(db, cid, month, year))