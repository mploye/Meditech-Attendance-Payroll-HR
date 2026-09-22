from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.errors import ConflictError, NotFoundError, ValidationError
from models.employee import Employee
from models.organization import Designation

_FIELDS = {"name", "code", "level", "description"}


def list_all(db: Session, company_id: str) -> list[Designation]:
    """List designations of a company ordered by name."""
    return list(
        db.scalars(
            select(Designation)
            .where(Designation.company_id == company_id)
            .order_by(Designation.name)
        )
    )


def create(db: Session, company_id: str, data: dict) -> Designation:
    """Create a designation with a unique name within the company."""
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValidationError("name is required")
    existing = db.scalar(
        select(Designation).where(Designation.company_id == company_id, Designation.name == name)
    )
    if existing is not None:
        raise ConflictError(f"designation '{name}' already exists")
    desig = Designation(company_id=company_id, **{k: v for k, v in data.items() if k in _FIELDS})
    db.add(desig)
    db.flush()
    db.commit()
    db.refresh(desig)
    return desig


def get(db: Session, company_id: str, obj_id: str) -> Designation:
    """Return a designation scoped to a company or raise NotFoundError."""
    desig = db.scalar(
        select(Designation).where(Designation.id == obj_id, Designation.company_id == company_id)
    )
    if desig is None:
        raise NotFoundError("Designation")
    return desig


def update(db: Session, company_id: str, obj_id: str, data: dict) -> Designation:
    """Update allowed fields of a designation."""
    desig = get(db, company_id, obj_id)
    name = str(data.get("name") or "").strip() if "name" in data else None
    if name:
        dup = db.scalar(
            select(Designation).where(
                Designation.company_id == company_id,
                Designation.name == name,
                Designation.id != obj_id,
            )
        )
        if dup is not None:
            raise ConflictError(f"designation '{name}' already exists")
    for key, value in data.items():
        if key in _FIELDS:
            setattr(desig, key, value)
    db.flush()
    db.commit()
    db.refresh(desig)
    return desig


def delete(db: Session, company_id: str, obj_id: str) -> None:
    """Delete a designation only when no employees reference it."""
    desig = get(db, company_id, obj_id)
    refs = (
        db.scalar(
            select(func.count(Employee.id)).where(
                Employee.company_id == company_id,
                Employee.designation_id == obj_id,
            )
        )
        or 0
    )
    if refs > 0:
        raise ConflictError("designation is assigned to employees and cannot be deleted")
    db.delete(desig)
    db.commit()