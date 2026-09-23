from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from core.deps import get_current_user, get_db  # noqa: F401  (re-export)
from core.errors import PermissionDeniedError
from core.rbac import has_permission
from models.enums import Role
from models.user import User


def resolve_company_id(user: User, company_id: Optional[str] = None) -> str:
    """Resolve the tenant scope from the caller (SUPER_ADMIN may target any company)."""
    if user.role == Role.SUPER_ADMIN:
        if company_id:
            return str(company_id)
        default = getattr(user, "default_company_id", None)
        if default:
            return str(default)
        raise PermissionDeniedError("company_id is required for SUPER_ADMIN")
    if not user.company_id:
        raise PermissionDeniedError("User is not associated with a company")
    return str(user.company_id)


def ensure_perm(user: User, permission: str) -> None:
    """Raise PermissionDeniedError unless the caller role has the permission."""
    if not has_permission(user.role, permission):
        raise PermissionDeniedError()


def orm_to_dict(obj: Any) -> dict[str, Any]:
    """Serialize a SQLAlchemy model instance to a plain, JSON-safe dict."""
    if obj is None:
        return None
    result: dict[str, Any] = {}
    for column in inspect(obj.__class__).mapper.column_attrs:
        value = getattr(obj, column.key)
        if isinstance(value, UUID):
            value = str(value)
        elif isinstance(value, Enum):
            value = value.value
        elif isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, date):
            value = value.isoformat()
        result[column.key] = value
    return result


def user_dict(user: User) -> dict[str, Any]:
    """Return a safe dictionary of user fields for API responses."""
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "company_id": str(user.company_id) if user.company_id else None,
        "employee_id": str(user.employee_id) if user.employee_id else None,
        "phone": user.phone,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }