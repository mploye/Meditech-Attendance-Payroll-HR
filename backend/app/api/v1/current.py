"""Shared auth helpers for v1 endpoints.

Re-exports the canonical, working versions of ensure_perm / company_scope.
Endpoint routers should import these from this module.
"""

from core import rbac
from core.errors import PermissionDeniedError, ValidationError
from models.enums import Role
from models.user import User


def ensure_perm(user: User, permission: str) -> None:
    """Check a permission against the current user's role, raising 403 if denied."""
    if user is None or not rbac.has_permission(user.role, permission):
        raise PermissionDeniedError("You do not have permission to perform this action")


def company_scope(*, user: User, company_id: str | None = None) -> str:
    """Resolve the active company scope for a request.

    SUPER_ADMIN must pass an explicit company_id; everyone else is scoped to
    their own company automatically.
    """
    if user.role == Role.SUPER_ADMIN:
        if not company_id:
            raise ValidationError("company_id is required for SUPER_ADMIN")
        return company_id
    if user.company_id is None:
        raise ValidationError("current user is not associated with a company")
    return str(user.company_id)