from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.enums import HolidayType
from models.leave import Holiday
from models.user import User
from services import holiday_service

router = APIRouter()


@router.get("/")
def list_holidays(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    ensure_perm(user, "holidays.view")
    cid = resolve_company_id(user)
    rows = holiday_service.list_holidays(db, cid, from_date, to_date)
    return success_response([orm_to_dict(r) for r in rows])


@router.post("/")
def create_holiday(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "holidays.create")
    cid = resolve_company_id(user)
    hd = holiday_service.create_holiday(
        db,
        cid,
        holiday_date=date.fromisoformat(body["holiday_date"]),
        name=body["name"],
        holiday_type=HolidayType(body.get("holiday_type", "COMPANY")),
    )
    return success_response(orm_to_dict(hd))


@router.patch("/{holiday_id}")
def update_holiday(holiday_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "holidays.edit")
    cid = resolve_company_id(user)
    row = holiday_service.update_holiday(db, cid, holiday_id, body)
    return success_response(orm_to_dict(row))


@router.delete("/{holiday_id}")
def delete_holiday(holiday_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "holidays.delete")
    cid = resolve_company_id(user)
    holiday_service.delete_holiday(db, cid, holiday_id)
    return success_response({"deleted": True})