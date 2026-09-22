from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.errors import ConflictError, NotFoundError, ValidationError
from models.employee import Employee
from models.organization import Department

_FIELDS = {"name", "code", "manager_id", "description"}


def list_all(db: Session, company_id: str) -> list[Department]:
    """List departments of a company ordered by name."""
    return list(
        db.scalars(
            select(Department)
            .where(Department.company_id == company_id)
            .order_by(Department.name)
        )
    )


def create(db: Session, company_id: str, data: dict) -> Department:
    """Create a department with a unique name within the company."""
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValidationError("name is required")
    existing = db.scalar(
        select(Department).where(Department.company_id == company_id, Department.name == name)
    )
    if existing is not None:
        raise ConflictError(f"department '{name}' already exists")
    dept = Department(company_id=company_id, **{k: v for k, v in data.items() if k in _FIELDS})
    db.add(dept)
    db.flush()
    db.commit()
    db.refresh(dept)
    return dept


def get(db: Session, company_id: str, obj_id: str) -> Department:
    """Return a department scoped to a company or raise NotFoundError."""
    dept = db.scalar(
        select(Department).where(Department.id == obj_id, Department.company_id == company_id)
    )
    if dept is None:
        raise NotFoundError("Department")
    return dept


def update(db: Session, company_id: str, obj_id: str, data: dict) -> Department:
    """Update allowed fields of a department."""
    dept = get(db, company_id, obj_id)
    name = str(data.get("name") or "").strip() if "name" in data else None
    if name:
        dup = db.scalar(
            select(Department).where(
                Department.company_id == company_id,
                Department.name == name,
                Department.id != obj_id,
            )
        )
        if dup is not None:
            raise ConflictError(f"department '{name}' already exists")
    for key, value in data.items():
        if key in _FIELDS:
            setattr(dept, key, value)
    db.flush()
    db.commit()
    db.refresh(dept)
    return dept


def delete(db: Session, company_id: str, obj_id: str) -> None:
    """Delete a department only when no employees reference it."""
    dept = get(db, company_id, obj_id)
    refs = (
        db.scalar(
            select(func.count(Employee.id)).where(
                Employee.company_id == company_id,
                Employee.department_id == obj_id,
            )
        )
        or 0
    )
    if refs > 0:
        raise ConflictError("department is assigned to employees and cannot be deleted")
    db.delete(dept)
    db.commit()