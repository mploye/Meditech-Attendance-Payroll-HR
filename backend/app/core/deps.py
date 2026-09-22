from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.errors import PermissionDeniedError, UnauthorizedError
from core.rbac import has_permission
from core.security import decode_token
from models.company import Company
from models.enums import Role
from models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise UnauthorizedError("Invalid or expired token")
    subject = payload.get("sub")
    if not subject:
        raise UnauthorizedError("Invalid token payload")
    user = db.get(User, subject)
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


def get_current_company(current_user: User = Depends(get_current_user)) -> Optional[Company]:
    if current_user.role == Role.SUPER_ADMIN:
        return None
    return current_user.company


def require_roles(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError()
        return user

    return checker


def require_perm(permission: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise PermissionDeniedError()
        return user

    return checker


async def resolve_request_user(request: Request, db: Session) -> Optional[User]:
    """Best-effort resolve user for audit from optional Authorization header."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    try:
        payload = decode_token(auth.split(" ", 1)[1])
    except Exception:
        return None
    subject = payload.get("sub")
    if not subject:
        return None
    return db.get(User, subject)


def get_device_connector_auth(x_api_key: Optional[str] = Header(None)):
    if not x_api_key or x_api_key != settings.DEVICE_CONNECTOR_API_KEY:
        raise UnauthorizedError("Invalid connector API key")
    return x_api_key