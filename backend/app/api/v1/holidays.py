"""Holiday endpoints under /holidays (CRUD)."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import NotFoundError, success_response
from models.user import User
from schemas.holiday import HolidayCreateRequest, HolidayUpdateRequest
from services import holiday_service

router = APIRouter(prefix="/holidays", tags=["holidays"])


@router.get("")
def list_holidays(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "holidays.view")
    scope = company_scope(user=user)
    rows = holiday_service.list_holidays(db, scope, from_date=from_date, to_date=to_date)
    return success_response(orm_to_dict(rows))


@router.post("")
def create_holiday(
    payload: HolidayCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "holidays.create")
    scope = company_scope(user=user)
    item = holiday_service.create_holiday(
        db, scope, holiday_date=payload.holiday_date, name=payload.name, holiday_type=payload.holiday_type
    )
    return success_response(orm_to_dict(item))


@router.get("/{holiday_id}")
def get_holiday(
    holiday_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "holidays.view")
    scope = company_scope(user=user)
    from models.leave import Holiday

    item = db.get(Holiday, holiday_id)
    if item is None or str(item.company_id) != scope:
        raise NotFoundError("Holiday")
    return success_response(orm_to_dict(item))


@router.patch("/{holiday_id}")
def update_holiday(
    holiday_id: str,
    payload: HolidayUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "holidays.edit")
    scope = company_scope(user=user)
    item = holiday_service.update_holiday(db, scope, holiday_id, payload.model_dump(exclude_unset=True))
    return success_response(orm_to_dict(item))


@router.delete("/{holiday_id}")
def delete_holiday(
    holiday_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "holidays.delete")
    scope = company_scope(user=user)
    holiday_service.delete_holiday(db, scope, holiday_id)
    return success_response({"message": "deleted"})