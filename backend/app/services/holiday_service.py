from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.errors import NotFoundError, ValidationError
from models.enums import HolidayType
from models.leave import Holiday

_FIELDS = {"holiday_date", "name", "holiday_type"}


def _to_date(value) -> date:
    """Coerce a str or date value into a date."""
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value


def _get_holiday(db: Session, company_id: str, holiday_id: str) -> Holiday:
    """Return a holiday scoped to a company or raise NotFoundError."""
    holiday = db.scalar(
        select(Holiday).where(Holiday.id == holiday_id, Holiday.company_id == company_id)
    )
    if holiday is None:
        raise NotFoundError("Holiday")
    return holiday


def list_holidays(
    db: Session,
    company_id: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Holiday]:
    """List holidays of a company with optional date range filters."""
    stmt = select(Holiday).where(Holiday.company_id == company_id)
    if from_date is not None:
        stmt = stmt.where(Holiday.holiday_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Holiday.holiday_date <= to_date)
    return list(db.scalars(stmt.order_by(Holiday.holiday_date)))


def create_holiday(
    db: Session,
    company_id: str,
    *,
    holiday_date,
    name: str,
    holiday_type: HolidayType = HolidayType.COMPANY,
) -> Holiday:
    """Create a holiday for a company."""
    holiday_date = _to_date(holiday_date)
    name = str(name or "").strip()
    if not name:
        raise ValidationError("name is required")
    holiday_type = holiday_type if isinstance(holiday_type, HolidayType) else HolidayType(holiday_type)
    holiday = Holiday(
        company_id=company_id,
        holiday_date=holiday_date,
        name=name,
        holiday_type=holiday_type,
    )
    db.add(holiday)
    db.flush()
    db.commit()
    db.refresh(holiday)
    return holiday


def update_holiday(db: Session, company_id: str, holiday_id: str, data: dict) -> Holiday:
    """Update allowed fields of a holiday."""
    holiday = _get_holiday(db, company_id, holiday_id)
    for key, value in data.items():
        if key not in _FIELDS:
            continue
        if key == "holiday_date":
            value = _to_date(value)
        elif key == "holiday_type" and isinstance(value, str):
            value = HolidayType(value)
        setattr(holiday, key, value)
    db.flush()
    db.commit()
    db.refresh(holiday)
    return holiday


def delete_holiday(db: Session, company_id: str, holiday_id: str) -> None:
    """Delete a holiday of a company."""
    holiday = _get_holiday(db, company_id, holiday_id)
    db.delete(holiday)
    db.commit()


def is_holiday(db: Session, company_id: str, day: date) -> bool:
    """Return whether a given day is a holiday for a company."""
    day = _to_date(day)
    holiday = db.scalar(
        select(Holiday.id).where(
            Holiday.company_id == company_id,
            Holiday.holiday_date == day,
        )
    )
    return holiday is not None


def holidays_between(
    db: Session, company_id: str, from_date: date, to_date: date
) -> list[date]:
    """Return holiday dates within a range for a company."""
    return list(
        db.scalars(
            select(Holiday.holiday_date)
            .where(
                Holiday.company_id == company_id,
                Holiday.holiday_date >= from_date,
                Holiday.holiday_date <= to_date,
            )
            .order_by(Holiday.holiday_date)
        )
    )