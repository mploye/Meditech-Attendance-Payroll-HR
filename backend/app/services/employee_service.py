import secrets
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.audit import log_audit
from core.errors import ConflictError, NotFoundError, ValidationError
from core.security import hash_password
from core.supabase_sync import sync_supabase_user
from models.company import Company
from models.device import Device
from models.employee import Employee
from models.employee_device import EmployeeDevice
from models.enums import EmployeeStatus, EmploymentType, MappingSyncStatus, Role, SalaryFrequency
from models.organization import Department, Designation
from models.salary import EmployeeSalary, SalaryStructure
from models.user import User

_EMPLOYEE_FIELDS = {
    "employee_code",
    "first_name",
    "last_name",
    "email",
    "phone",
    "date_of_birth",
    "gender",
    "joining_date",
    "resignation_date",
    "department_id",
    "designation_id",
    "manager_id",
    "employment_type",
    "work_location",
    "profile_photo_url",
    "status",
    "aadhaar_no",
    "pan",
    "bank_name",
    "account_number",
    "ifsc",
    "account_holder_name",
}
_DATE_FIELDS = {"date_of_birth", "joining_date", "resignation_date"}
_SALARY_KEYS = {
    "salary_structure_id",
    "effective_from",
    "effective_to",
    "basic_salary",
    "gross_salary",
    "payment_frequency",
    "bank_name",
    "account_number",
    "ifsc",
    "account_holder_name",
}


def _employee_summary(emp: Employee) -> dict:
    """Return a minimal serializable snapshot of employee fields for audit."""
    return {
        "employee_code": emp.employee_code,
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "email": emp.email,
        "department_id": str(emp.department_id) if emp.department_id else None,
        "designation_id": str(emp.designation_id) if emp.designation_id else None,
        "status": emp.status.value if isinstance(emp.status, EmployeeStatus) else emp.status,
    }


def _coerce_employee_value(key: str, value):
    """Coerce enum and date values into the types the Employee model expects."""
    if key in _DATE_FIELDS and isinstance(value, str) and value:
        return date.fromisoformat(value)
    if key == "status" and isinstance(value, str):
        return EmployeeStatus(value)
    if key == "employment_type" and isinstance(value, str):
        return EmploymentType(value)
    return value


def _validate_org_refs(db: Session, company_id: str, data: dict) -> None:
    """Validate that department/designation refs belong to the same company."""
    dep_id = data.get("department_id")
    if dep_id:
        dep = db.get(Department, dep_id)
        if dep is None or str(dep.company_id) != str(company_id):
            raise ValidationError("department_id does not belong to this company")
    desig_id = data.get("designation_id")
    if desig_id:
        desig = db.get(Designation, desig_id)
        if desig is None or str(desig.company_id) != str(company_id):
            raise ValidationError("designation_id does not belong to this company")


def list_employees(
    db: Session,
    company_id: str,
    *,
    search: str | None = None,
    department_id: str | None = None,
    designation_id: str | None = None,
    status: EmployeeStatus | str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Return paginated employees for a company with optional filters."""
    stmt = select(Employee).where(Employee.company_id == company_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Employee.employee_code.ilike(like),
                Employee.first_name.ilike(like),
                Employee.last_name.ilike(like),
                Employee.email.ilike(like),
            )
        )
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if designation_id:
        stmt = stmt.where(Employee.designation_id == designation_id)
    if status is not None:
        status = status if isinstance(status, EmployeeStatus) else EmployeeStatus(status)
        stmt = stmt.where(Employee.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    page = max(1, page)
    page_size = max(1, page_size)
    items = list(
        db.scalars(
            stmt.order_by(Employee.created_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    pages = (total + page_size - 1) // page_size
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


def get_employee(db: Session, company_id: str, employee_id: str) -> Employee:
    """Return an employee scoped to a company or raise NotFoundError."""
    emp = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.company_id == company_id)
    )
    if emp is None:
        raise NotFoundError("Employee")
    return emp


def create_employee(
    db: Session,
    company_id: str,
    data: dict,
    user_id: str | None = None,
    audit: bool | None = None,
) -> Employee:
    """Create and commit an employee with uniqueness and org reference validation."""
    code = str(data.get("employee_code") or "").strip()
    if not code:
        raise ValidationError("employee_code is required")
    dup = db.scalar(
        select(Employee).where(Employee.company_id == company_id, Employee.employee_code == code)
    )
    if dup is not None:
        raise ConflictError(f"employee_code '{code}' already exists in this company")
    _validate_org_refs(db, company_id, data)
    emp = Employee(company_id=company_id, employee_code=code)
    for key, value in data.items():
        if key == "employee_code":
            continue
        if key in _EMPLOYEE_FIELDS:
            setattr(emp, key, _coerce_employee_value(key, value))
    if "status" not in data:
        emp.status = EmployeeStatus.ACTIVE
    db.add(emp)
    db.flush()
    db.commit()
    db.refresh(emp)
    if audit is not False:
        log_audit(
            db,
            "employee.create",
            entity_type="employee",
            entity_id=str(emp.id),
            new_value=_employee_summary(emp),
            company_id=str(company_id),
            user_id=user_id,
        )
    return emp


def update_employee(
    db: Session,
    company_id: str,
    employee_id: str,
    data: dict,
    user_id: str | None = None,
) -> Employee:
    """Update allowed fields of an employee and audit the change."""
    emp = get_employee(db, company_id, employee_id)
    old = _employee_summary(emp)
    if "employee_code" in data:
        code = str(data["employee_code"] or "").strip()
        dup = db.scalar(
            select(Employee).where(
                Employee.company_id == company_id,
                Employee.employee_code == code,
                Employee.id != employee_id,
            )
        )
        if dup is not None:
            raise ConflictError(f"employee_code '{code}' already exists in this company")
        data = dict(data)
        data["employee_code"] = code
    _validate_org_refs(db, company_id, data)
    for key, value in data.items():
        if key in _EMPLOYEE_FIELDS:
            setattr(emp, key, _coerce_employee_value(key, value))
    db.flush()
    db.commit()
    db.refresh(emp)
    log_audit(
        db,
        "employee.update",
        entity_type="employee",
        entity_id=str(emp.id),
        old_value=old,
        new_value=_employee_summary(emp),
        company_id=str(company_id),
        user_id=user_id,
    )
    return emp


def _compute_basic_from_structure(
    db: Session, company_id: str, structure_id: str, gross: float
) -> float:
    """Compute basic salary by simulating a structure, falling back to gross."""
    structure = db.scalar(
        select(SalaryStructure).where(
            SalaryStructure.id == structure_id,
            SalaryStructure.company_id == company_id,
        )
    )
    if structure is None:
        raise ValidationError("salary_structure_id does not belong to this company")
    try:
        from payroll.calculator import compute_structure_basic
    except ImportError:
        return gross
    try:
        return compute_structure_basic(structure, gross)
    except Exception:
        return gross


def set_employee_salary(
    db: Session, company_id: str, employee_id: str, data: dict
) -> EmployeeSalary:
    """Insert a new salary history row, expiring prior active records."""
    get_employee(db, company_id, employee_id)
    if not data.get("effective_from"):
        raise ValidationError("effective_from is required")
    effective_from = data["effective_from"]
    if isinstance(effective_from, str):
        effective_from = date.fromisoformat(effective_from)
    prior = list(
        db.scalars(
            select(EmployeeSalary).where(
                EmployeeSalary.company_id == str(company_id),
                EmployeeSalary.employee_id == str(employee_id),
                EmployeeSalary.effective_to.is_(None),
            )
        )
    )
    for record in prior:
        record.effective_to = effective_from - timedelta(days=1)
    values = {k: v for k, v in data.items() if k in _SALARY_KEYS and k != "effective_from"}
    if "effective_to" in values:
        values["effective_to"] = (
            date.fromisoformat(values["effective_to"]) if values["effective_to"] else None
        )
    if "payment_frequency" in values and isinstance(values["payment_frequency"], str):
        values["payment_frequency"] = SalaryFrequency(values["payment_frequency"])
    basic = values.get("basic_salary")
    structure_id = values.get("salary_structure_id")
    gross = values.get("gross_salary")
    if basic is None and structure_id and gross:
        values["basic_salary"] = _compute_basic_from_structure(
            db, str(company_id), str(structure_id), float(gross)
        )
    salary = EmployeeSalary(
        company_id=str(company_id),
        employee_id=str(employee_id),
        effective_from=effective_from,
        **values,
    )
    db.add(salary)
    db.flush()
    db.commit()
    db.refresh(salary)
    log_audit(
        db,
        "employee.salary_change",
        entity_type="employee_salary",
        entity_id=str(salary.id),
        new_value={
            "effective_from": effective_from.isoformat(),
            "basic_salary": salary.basic_salary,
            "gross_salary": salary.gross_salary,
        },
        company_id=str(company_id),
    )
    return salary


def employee_salary_history(
    db: Session, company_id: str, employee_id: str
) -> list[EmployeeSalary]:
    """Return the full salary history of an employee, newest first."""
    get_employee(db, company_id, employee_id)
    return list(
        db.scalars(
            select(EmployeeSalary)
            .where(
                EmployeeSalary.company_id == str(company_id),
                EmployeeSalary.employee_id == str(employee_id),
            )
            .order_by(EmployeeSalary.effective_from.desc())
        )
    )


def active_salary(
    db: Session, company_id: str, employee_id: str, month_date: date | None = None
) -> EmployeeSalary | None:
    """Return the salary record active for an employee on a given date."""
    month_date = month_date or date.today()
    return db.scalar(
        select(EmployeeSalary)
        .where(
            EmployeeSalary.company_id == str(company_id),
            EmployeeSalary.employee_id == str(employee_id),
            EmployeeSalary.effective_from <= month_date,
            or_(
                EmployeeSalary.effective_to.is_(None),
                EmployeeSalary.effective_to >= month_date,
            ),
        )
        .order_by(EmployeeSalary.effective_from.desc())
        .limit(1)
    )


def add_device_mapping(
    db: Session,
    company_id: str,
    employee_id: str,
    *,
    device_id: str,
    device_user_id: str,
) -> EmployeeDevice:
    """Create a device mapping for an employee, rejecting duplicates."""
    get_employee(db, company_id, employee_id)
    device = db.get(Device, device_id)
    if device is None or str(device.company_id) != str(company_id):
        raise ValidationError("device does not belong to this company")
    existing = db.scalar(
        select(EmployeeDevice).where(
            EmployeeDevice.company_id == str(company_id),
            EmployeeDevice.device_id == str(device_id),
            EmployeeDevice.device_user_id == str(device_user_id),
        )
    )
    if existing is not None:
        raise ConflictError("a device mapping for this device user already exists")
    mapping = EmployeeDevice(
        company_id=str(company_id),
        employee_id=str(employee_id),
        device_id=str(device_id),
        device_user_id=str(device_user_id),
        sync_status=MappingSyncStatus.PENDING,
    )
    db.add(mapping)
    db.flush()
    db.commit()
    db.refresh(mapping)
    return mapping


def employee_devices(db: Session, company_id: str, employee_id: str) -> list[EmployeeDevice]:
    """Return all device mappings of an employee."""
    get_employee(db, company_id, employee_id)
    return list(
        db.scalars(
            select(EmployeeDevice)
            .where(
                EmployeeDevice.company_id == str(company_id),
                EmployeeDevice.employee_id == str(employee_id),
            )
            .order_by(EmployeeDevice.created_at)
        )
    )


def associate_user(
    db: Session,
    company_id: str,
    employee_id: str,
    email: str,
    full_name: str | None = None,
    password: str | None = None,
) -> User:
    """Link an existing user by email or create a new EMPLOYEE user for the employee."""
    emp = get_employee(db, company_id, employee_id)
    email = (email or "").strip().lower()
    if not email:
        raise ValidationError("email is required")
    created = False
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        created = True
        plain_password = password if password else secrets.token_urlsafe(16)
        hashed = hash_password(plain_password)
        display_name = (
            " ".join(part for part in (emp.first_name, emp.last_name or "") if part)
            or emp.employee_code
        )
        user = User(
            company_id=str(company_id),
            email=email,
            password_hash=hashed,
            full_name=full_name or display_name,
            role=Role.EMPLOYEE,
        )
        db.add(user)
    else:
        user.company_id = str(company_id)
    user.employee_id = str(employee_id)
    db.flush()
    db.commit()
    db.refresh(user)
    if created and user.email:
        sync_supabase_user(email, plain_password, user.full_name)
    return user


def sync_employee_to_essl(db: Session, company_id: str, employee_id: str) -> dict:
    """Push an employee to every mapped ESSL device for the company."""
    try:
        from services.sync_service import get_essl_service
    except ImportError:
        return {"synced": False, "reason": "provider-unavailable"}
    emp = get_employee(db, company_id, employee_id)
    mappings = list(
        db.scalars(
            select(EmployeeDevice).where(
                EmployeeDevice.company_id == str(company_id),
                EmployeeDevice.employee_id == str(employee_id),
            )
        )
    )
    if not mappings:
        return {"mappings": 0, "synced": True}
    service = get_essl_service(db, str(company_id))
    if service is None:
        return {"mappings": len(mappings), "synced": False, "reason": "not-configured"}
    company = db.get(Company, str(company_id))
    import asyncio

    synced = 0
    for mapping in mappings:
        device = db.get(Device, mapping.device_id)
        if device is None:
            continue
        asyncio.run(service.sync_employee(company, emp, device, mapping))
        synced += 1
    return {"mappings": synced, "synced": True}


def employee_dashboard_stats(db: Session, company_id: str) -> dict:
    """Return employee counts by overall and key statuses."""
    total = db.scalar(select(func.count(Employee.id)).where(Employee.company_id == company_id)) or 0
    counts: dict[str, EmployeeStatus] = {
        "active": EmployeeStatus.ACTIVE,
        "on_notice": EmployeeStatus.ON_NOTICE,
        "resigned": EmployeeStatus.RESIGNED,
        "terminated": EmployeeStatus.TERMINATED,
    }
    stats = {"total": total}
    for key, status in counts.items():
        stats[key] = (
            db.scalar(
                select(func.count(Employee.id)).where(
                    Employee.company_id == company_id,
                    Employee.status == status,
                )
            )
            or 0
        )
    return stats