from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.leave import LeaveBalance, LeaveRequest, LeaveType
from models.user import User
from services import leave_service

router = APIRouter()


@router.get("/types")
def list_types(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "leaves.view")
    cid = resolve_company_id(user)
    return success_response([orm_to_dict(t) for t in leave_service.list_leave_types(db, cid)])


@router.post("/types")
def create_type(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "leaves.edit")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(leave_service.create_leave_type(db, cid, body)))


@router.patch("/types/{leave_type_id}")
def update_type(leave_type_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "leaves.edit")
    cid = resolve_company_id(user)
    return success_response(orm_to_dict(leave_service.update_leave_type(db, cid, leave_type_id, body)))


@router.post("/apply")
def apply_leave(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "leaves.create")
    cid = resolve_company_id(user)
    if user.role == "EMPLOYEE" and not body.get("employee_id"):
        if not user.employee_id:
            raise NotFoundError("Employee profile not linked")
        body["employee_id"] = str(user.employee_id)
    start = date.fromisoformat(body["start_date"])
    end = date.fromisoformat(body["end_date"])
    request = leave_service.apply_leave(
        db,
        cid,
        body["employee_id"],
        leave_type_id=body["leave_type_id"],
        start_date=start,
        end_date=end,
        reason=body.get("reason"),
        is_half_day=bool(body.get("is_half_day", False)),
    )
    return success_response(orm_to_dict(request))


@router.get("/requests")
def list_requests(
    status: Optional[str] = None,
    employee_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "leaves.view")
    cid = resolve_company_id(user)
    from models.enums import LeaveStatus

    st = LeaveStatus(status) if status else None
    result = leave_service.list_leave_requests(db, cid, status=st, employee_id=employee_id, page=page, page_size=page_size)
    if isinstance(result, dict) and "items" in result:
        result["items"] = [orm_to_dict(i) for i in result["items"]]
        return success_response(result)
    return success_response([orm_to_dict(i) for i in result])


@router.post("/{request_id}/approve")
def approve(request_id: str, body: dict | None = None, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "leaves.approve")
    cid = resolve_company_id(user)
    comment = (body or {}).get("comment")
    row = leave_service.approve_leave(db, cid, request_id, user, comment)
    return success_response(orm_to_dict(row))


@router.post("/{request_id}/reject")
def reject(request_id: str, body: dict | None = None, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "leaves.approve")
    cid = resolve_company_id(user)
    comment = (body or {}).get("comment")
    row = leave_service.reject_leave(db, cid, request_id, user, comment)
    return success_response(orm_to_dict(row))


@router.post("/{request_id}/cancel")
def cancel(request_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "leaves.create")
    cid = resolve_company_id(user)
    leave_service.cancel_leave(db, cid, request_id, user)
    return success_response({"cancelled": True})


@router.get("/balances")
def balances(
    year: Optional[int] = None,
    employee_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "leaves.view")
    cid = resolve_company_id(user)
    rows = leave_service.get_balances(db, cid, employee_id=employee_id, year=year)
    return success_response([orm_to_dict(r) for r in rows])


@router.post("/balances/init")
def init_balances(
    year: int = Query(..., ge=2000, le=2100),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "leaves.edit")
    cid = resolve_company_id(user)
    return success_response(leave_service.init_balances(db, cid, year))