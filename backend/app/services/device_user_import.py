import csv
import io
import secrets
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.audit import log_audit
from core.security import hash_password
from models.employee import Employee
from models.employee_device import EmployeeDevice
from models.enums import EmployeeStatus, EmploymentType, MappingSyncStatus, Role
from models.user import User

_USER_ID_ALIASES = {
    "userid",
    "user id",
    "enrollid",
    "enroll id",
    "enrolid",
    "enroll no",
    "enrollno",
    "no",
    "sr no",
    "srno",
    "sno",
    "id",
    "device user id",
    "deviceuserid",
    "employee no",
    "emp no",
    "empno",
    "unicode emp id",
    "bio user id",
}
_BADGE_ALIASES = {
    "badge",
    "badgenumber",
    "badge number",
    "card",
    "cardno",
    "card number",
    "card no",
    "idnumber",
    "id number",
    "id no",
    "idno",
    "badgeno",
    "ruleno",
    "rule no",
    "badge id",
}
_NAME_ALIASES = {
    "name",
    "realname",
    "real name",
    "username",
    "user name",
    "displayname",
    "display name",
    "employeename",
    "employee name",
    "fullname",
    "full name",
}
_DEPT_ALIASES = {
    "dept",
    "deptname",
    "dept name",
    "department",
    "department name",
    "dept id",
    "deptid",
    "department no",
    "dept no",
    "dept code",
}
_DESIG_ALIASES = {
    "designation",
    "desig",
    "title",
    "jobtitle",
    "job title",
    "position",
    "role",
    "designation name",
    "designationname",
}
_EMAIL_ALIASES = {
    "email",
    "emailaddress",
    "email address",
    "mail",
    "employee email",
    "emailid",
    "email id",
}
_PHONE_ALIASES = {
    "phone",
    "mobile",
    "mobileno",
    "mobile no",
    "tel",
    "telephone",
    "phone no",
    "phone number",
    "contact no",
    "phoneno",
    "contact",
}
_GENDER_ALIASES = {"gender", "sex"}
_JOINING_ALIASES = {
    "joindate",
    "join date",
    "joined",
    "joinedon",
    "joined on",
    "hire date",
    "joining date",
    "hire_date",
    "hiredate",
    "date of join",
}
_EMPLOYMENT_ALIASES = {
    "employeetype",
    "employee type",
    "employment type",
    "employmenttype",
    "employtype",
    "employment status",
}

_COLUMN_ALIASES = {
    "device_user_id": _USER_ID_ALIASES,
    "badge": _BADGE_ALIASES,
    "name": _NAME_ALIASES,
    "department": _DEPT_ALIASES,
    "designation": _DESIG_ALIASES,
    "email": _EMAIL_ALIASES,
    "phone": _PHONE_ALIASES,
    "gender": _GENDER_ALIASES,
    "joining_date": _JOINING_ALIASES,
    "employment_type": _EMPLOYMENT_ALIASES,
}

_EMPLOYMENT_MAP = {
    "full": EmploymentType.FULL_TIME,
    "full time": EmploymentType.FULL_TIME,
    "fulltime": EmploymentType.FULL_TIME,
    "fte": EmploymentType.FULL_TIME,
    "permanent": EmploymentType.FULL_TIME,
    "part": EmploymentType.PART_TIME,
    "part time": EmploymentType.PART_TIME,
    "parttime": EmploymentType.PART_TIME,
    "contract": EmploymentType.CONTRACT,
    "contractual": EmploymentType.CONTRACT,
    "intern": EmploymentType.INTERN,
    "internship": EmploymentType.INTERN,
    "trainee": EmploymentType.INTERN,
}


def _norm_header(value: str) -> str:
    """Normalize a CSV header to a stable canonical-ish key."""
    value = value.strip().lower()
    value = value.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", value)


def _resolve_columns(headers: list[str]) -> dict[str, str]:
    """Map canonical import fields to the actual header name present in the CSV."""
    lookup = {_norm_header(h): h for h in headers}
    resolved: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                resolved[canonical] = lookup[alias]
                break
    return resolved


def _first_row_field(row: dict, *keys: str) -> str:
    """Return the first non-empty value among the given header keys."""
    for key in keys:
        value = row.get(key)
        if value is not None:
            value = str(value).strip()
            if value:
                return value
    return ""


def _clean_row(row: dict, resolved: dict[str, str]) -> dict[str, str]:
    """Extract normalized field values from a raw CSV row."""
    out: dict[str, str] = {}
    for canonical, alias in resolved.items():
        out[canonical] = _first_row_field(row, alias)
    return out


def _split_name(name: str) -> tuple[str, str]:
    """Split a full name into (first_name, last_name)."""
    name = name.strip()
    if not name:
        return "", ""
    if "," in name:
        last, first = (part.strip() for part in name.split(",", 1))
        return first or last, last if first else ""
    parts = [p for p in name.split() if p]
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def _parse_date(value: str):
    from datetime import date, datetime

    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_employment(value: str):
    if not value:
        return None
    key = _norm_header(value)
    return _EMPLOYMENT_MAP.get(key)


def parse_csv(content: bytes) -> tuple[list[dict], list[str]]:
    """Decode CSV bytes into (raw_rows, errors). Tolerates BOM and encodings."""
    if not content:
        raise ValueError("empty file")
    raw = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            raw = content.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if raw is None:
        raise ValueError("unrecognized file encoding")
    text = raw.lstrip("\ufeff")
    sample = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ","
    if sample.count("\t") >= sample.count(",") and "\t" in sample:
        delimiter = "\t"
    elif sample.count(";") > sample.count(","):
        delimiter = ";"
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    rows = list(reader)
    return rows, []


def _parse_rows(raw_rows: list[dict], header_keys: list[str]) -> list[dict]:
    resolved = _resolve_columns(header_keys)
    return [_clean_row(row, resolved) for row in raw_rows]


def _get_or_create_department(db: Session, company_id: str, name: str) -> str:
    """Return a department id, creating the department if needed."""
    from models.organization import Department

    name = name.strip()
    existing = db.scalar(
        select(Department).where(
            Department.company_id == str(company_id),
            Department.name.ilike(name),
        )
    )
    if existing is not None:
        return str(existing.id)
    code = re.sub(r"[^A-Za-z0-9]+", "", name.upper())[:10] or None
    dept = Department(company_id=str(company_id), name=name, code=code)
    db.add(dept)
    db.flush()
    return str(dept.id)


def _get_or_create_designation(db: Session, company_id: str, name: str) -> str:
    """Return a designation id, creating the designation if needed."""
    from models.organization import Designation

    name = name.strip()
    existing = db.scalar(
        select(Designation).where(
            Designation.company_id == str(company_id),
            Designation.name.ilike(name),
        )
    )
    if existing is not None:
        return str(existing.id)
    code = re.sub(r"[^A-Za-z0-9]+", "", name.upper())[:10] or None
    desig = Designation(company_id=str(company_id), name=name, code=code)
    db.add(desig)
    db.flush()
    return str(desig.id)


def _employee_code_for(user_id: str, badge: str) -> str:
    if badge:
        return badge
    if user_id.isdigit():
        return f"E{int(user_id):04d}"
    return f"E{user_id}"


def import_device_users(
    db: Session,
    company_id: str,
    device_id: str,
    content: bytes,
    *,
    default_department: str | None = None,
    default_designation: str | None = None,
    create_accounts: bool = True,
    user_id: str | None = None,
) -> dict:
    """Import employees from an eSSL/eTimeTrackLite CSV export and map them to a device."""
    from models.device import Device

    device = db.get(Device, device_id)
    if device is None or str(device.company_id) != str(company_id):
        raise ValueError("device does not belong to this company")

    raw_rows, _ = parse_csv(content)
    header_keys = list(raw_rows[0].keys()) if raw_rows else []
    rows = _parse_rows(raw_rows, header_keys)

    summary: dict = {
        "rows": len(rows),
        "created": 0,
        "updated": 0,
        "mapped": 0,
        "skipped": 0,
        "errors": [],
    }

    device_id_s = str(device_id)
    cid = str(company_id)

    for index, row in enumerate(rows, start=2):
        try:
            with db.begin_nested():
                _import_one(
                    db,
                    cid,
                    device_id_s,
                    row,
                    default_department=default_department,
                    default_designation=default_designation,
                    create_accounts=create_accounts,
                    summary=summary,
                )
        except Exception as exc:  # noqa: BLE001 - per-row failures must not abort the import
            summary["errors"].append({"row": index, "reason": str(exc)})
            summary["skipped"] += 1

    db.commit()
    log_audit(
        db,
        "device_users.import",
        entity_type="device",
        entity_id=device_id_s,
        new_value={
            **{k: v for k, v in summary.items() if k != "errors"},
            "error_count": len(summary["errors"]),
        },
        company_id=cid,
        user_id=user_id,
        commit=False,
    )
    db.commit()
    return summary


def _import_one(
    db: Session,
    company_id: str,
    device_id: str,
    row: dict,
    *,
    default_department: str | None,
    default_designation: str | None,
    create_accounts: bool,
    summary: dict,
) -> None:
    user_dev_id = row.get("device_user_id") or row.get("badge")
    if not user_dev_id:
        raise ValueError("missing user id")
    name = row.get("name") or row.get("device_user_id")
    first_name, last_name = _split_name(name)
    badge = row.get("badge")
    employee_code = _employee_code_for(user_dev_id, badge)

    email = row.get("email")
    phone = row.get("phone")
    gender = row.get("gender")
    joining_date = _parse_date(row.get("joining_date"))
    employment_type = _parse_employment(row.get("employment_type")) or EmploymentType.FULL_TIME

    department_id = (row.get("department") or default_department or "").strip() or None
    designation_id = (row.get("designation") or default_designation or "").strip() or None
    if department_id:
        department_id = _get_or_create_department(db, company_id, department_id)
    if designation_id:
        designation_id = _get_or_create_designation(db, company_id, designation_id)

    code = employee_code

    def _employee_created() -> bool:
        existing = db.scalar(
            select(Employee).where(
                Employee.company_id == company_id,
                Employee.employee_code == code,
            )
        )
        if existing is not None:
            changed = False
            if (existing.email or "") != (email or ""):
                existing.email = email
                changed = True
            if (existing.phone or "") != (phone or ""):
                existing.phone = phone
                changed = True
            if last_name and (existing.last_name or "") != last_name:
                existing.last_name = last_name
                changed = True
            if department_id and str(existing.department_id or "") != department_id:
                existing.department_id = department_id
                changed = True
            if designation_id and str(existing.designation_id or "") != designation_id:
                existing.designation_id = designation_id
                changed = True
            if gender and (existing.gender or "") != gender:
                existing.gender = gender
                changed = True
            if joining_date and existing.joining_date != joining_date:
                existing.joining_date = joining_date
                changed = True
            if changed:
                summary["updated"] += 1
            return False

        emp = Employee(
            company_id=company_id,
            employee_code=code,
            first_name=first_name or code,
            last_name=last_name or None,
            email=email or None,
            phone=phone or None,
            gender=gender or None,
            joining_date=joining_date,
            department_id=department_id,
            designation_id=designation_id,
            employment_type=employment_type,
            status=EmployeeStatus.ACTIVE,
        )
        db.add(emp)
        db.flush()
        summary["created"] += 1
        return True

    is_new = _employee_created()

    emp = db.scalar(
        select(Employee).where(
            Employee.company_id == company_id,
            Employee.employee_code == code,
        )
    )
    if emp is None:
        raise ValueError(f"employee {code} could not be resolved")

    existing_map = db.scalar(
        select(EmployeeDevice).where(
            EmployeeDevice.company_id == company_id,
            EmployeeDevice.device_id == device_id,
            EmployeeDevice.device_user_id == user_dev_id,
        )
    )
    if existing_map is not None:
        if str(existing_map.employee_id) != str(emp.id):
            raise ValueError(f"device user {user_dev_id} already mapped to another employee")
        summary["mapped"] += 1
    else:
        db.add(
            EmployeeDevice(
                company_id=company_id,
                employee_id=str(emp.id),
                device_id=device_id,
                device_user_id=user_dev_id,
                sync_status=MappingSyncStatus.PENDING,
            )
        )
        db.flush()
        summary["mapped"] += 1

    if is_new and create_accounts and email:
        existing_user = db.scalar(select(User).where(User.email == email))
        if existing_user is None:
            plain_password = secrets.token_urlsafe(14)
            db.add(
                User(
                    company_id=company_id,
                    email=email,
                    password_hash=hash_password(plain_password),
                    full_name=f"{first_name} {last_name}".strip() or code,
                    role=Role.EMPLOYEE,
                    employee_id=str(emp.id),
                )
            )
            db.flush()


def mapped_employees(db: Session, company_id: str, device_id: str) -> list[dict]:
    """Return the device->employee mapping list for a device."""
    from models.device import Device

    device = db.get(Device, device_id)
    if device is None or str(device.company_id) != str(company_id):
        raise ValueError("device does not belong to this company")
    rows = list(
        db.scalars(
            select(EmployeeDevice)
            .where(
                EmployeeDevice.company_id == str(company_id),
                EmployeeDevice.device_id == str(device_id),
            )
            .order_by(EmployeeDevice.device_user_id)
        )
    )
    result = []
    for row in rows:
        emp = db.get(Employee, row.employee_id)
        result.append(
            {
                "id": str(row.id),
                "device_user_id": row.device_user_id,
                "employee_id": str(row.employee_id),
                "employee_code": emp.employee_code if emp else None,
                "employee_name": " ".join(
                    p for p in (emp.first_name, emp.last_name or "") if p
                )
                if emp
                else None,
                "sync_status": row.sync_status.value if row.sync_status else None,
                "face_registered": row.face_registered,
                "fingerprint_registered": row.fingerprint_registered,
            }
        )
    return result