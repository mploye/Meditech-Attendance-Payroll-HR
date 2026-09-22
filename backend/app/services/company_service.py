from datetime import time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.audit import log_audit
from core.errors import ConflictError, NotFoundError, ValidationError
from models.company import Company
from models.employee import Employee
from models.enums import LOPPolicy
from models.shift import Shift

_COMPANY_FIELDS = {
    "name",
    "short_name",
    "legal_name",
    "email",
    "phone",
    "address",
    "city",
    "state",
    "country",
    "pincode",
    "gstin",
    "pan",
}
_SETTINGS_FIELDS = {"lop_policy", "statutory_state", "timezone", "overtime_enabled"}


def _summary(company: Company) -> dict:
    """Return a minimal serializable snapshot of company fields for audit."""
    return {
        "name": company.name,
        "short_name": company.short_name,
        "email": company.email,
        "phone": company.phone,
        "timezone": company.timezone,
        "lop_policy": (
            company.lop_policy.value if isinstance(company.lop_policy, LOPPolicy) else company.lop_policy
        ),
    }


def get_company(db: Session, company_id: str) -> Company:
    """Return a company by id or raise NotFoundError."""
    company = db.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    return company


def create_company(
    db: Session,
    *,
    name: str,
    short_name: str,
    legal_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str = "India",
    pincode: str | None = None,
    timezone: str = "Asia/Kolkata",
    gstin: str | None = None,
    pan: str | None = None,
    statutory_state: str | None = None,
    lop_policy: LOPPolicy = LOPPolicy.WORKING_DAYS,
    overtime_enabled: bool = True,
) -> Company:
    """Create a new company and commit it."""
    if not name or not short_name:
        raise ValidationError("name and short_name are required")
    existing = db.scalar(select(Company).where(Company.short_name == short_name))
    if existing is not None:
        raise ConflictError(f"company with short_name '{short_name}' already exists")
    company = Company(
        name=name,
        short_name=short_name,
        legal_name=legal_name,
        email=email,
        phone=phone,
        address=address,
        city=city,
        state=state,
        country=country,
        pincode=pincode,
        timezone=timezone,
        gstin=gstin,
        pan=pan,
        statutory_state=statutory_state,
        lop_policy=lop_policy if isinstance(lop_policy, LOPPolicy) else LOPPolicy(lop_policy),
        overtime_enabled=overtime_enabled,
    )
    db.add(company)
    db.flush()
    db.commit()
    db.refresh(company)
    return company


def update_company(db: Session, company_id: str, data: dict) -> Company:
    """Update allowed profile fields of a company and audit the change."""
    company = get_company(db, company_id)
    old = _summary(company)
    for key, value in data.items():
        if key not in _COMPANY_FIELDS:
            continue
        setattr(company, key, value)
    db.flush()
    db.commit()
    db.refresh(company)
    log_audit(
        db,
        "company.update",
        entity_type="company",
        entity_id=str(company.id),
        old_value=old,
        new_value=_summary(company),
        company_id=str(company.id),
    )
    return company


def update_company_settings(db: Session, company_id: str, data: dict) -> Company:
    """Update allowed setting fields of a company and audit the change."""
    company = get_company(db, company_id)
    old = _summary(company)
    for key, value in data.items():
        if key not in _SETTINGS_FIELDS:
            continue
        if key == "lop_policy" and isinstance(value, str):
            value = LOPPolicy(value)
        setattr(company, key, value)
    db.flush()
    db.commit()
    db.refresh(company)
    log_audit(
        db,
        "company.settings.update",
        entity_type="company",
        entity_id=str(company.id),
        old_value=old,
        new_value=_summary(company),
        company_id=str(company.id),
    )
    return company


def list_companies(db: Session, search: str | None = None) -> list[Company]:
    """List companies with optional search over name, short_name and legal_name."""
    stmt = select(Company)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Company.name.ilike(like),
                Company.short_name.ilike(like),
                Company.legal_name.ilike(like),
            )
        )
    return list(db.scalars(stmt.order_by(Company.created_at)))


def ensure_default_shift(db: Session, company_id: str) -> Shift:
    """Return the existing default shift for a company or create the General default."""
    company = get_company(db, company_id)
    existing = db.scalar(
        select(Shift).where(
            Shift.company_id == str(company.id),
            Shift.is_default.is_(True),
            Shift.active.is_(True),
        )
    )
    if existing is not None:
        return existing
    shift = Shift(
        company_id=str(company.id),
        name="General",
        code="GENERAL",
        start_time=time(9, 0),
        end_time=time(18, 0),
        grace_period_minutes=0,
        minimum_work_minutes=420,
        break_minutes=60,
        overtime_enabled=True,
        overtime_after_minutes=60,
        is_default=True,
        active=True,
    )
    db.add(shift)
    db.flush()
    db.commit()
    db.refresh(shift)
    return shift


def count_employees(db: Session, company_id: str) -> int:
    """Return the number of employees belonging to a company."""
    return db.scalar(select(func.count(Employee.id)).where(Employee.company_id == company_id)) or 0