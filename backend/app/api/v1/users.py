"""User administration endpoints under /users."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict, user_payload
from core.database import get_db
from core.deps import get_current_user
from core.errors import NotFoundError, ValidationError, success_response
from models.enums import Role
from models.user import User
from schemas.reset_password import ResetPasswordRequest
from schemas.user import UserCreateRequest, UserUpdateRequest
from services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_users(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "users.view")
    scope = company_scope(user=user)
    rows = user_service.list_users(db, scope)
    return success_response([user_payload(u) for u in rows])


@router.post("")
def create_user(
    payload: UserCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "users.create")
    scope = company_scope(user=user)
    try:
        role = Role(payload.role)
    except ValueError:
        raise ValidationError(f"invalid role '{payload.role}'")
    if role == Role.SUPER_ADMIN:
        raise ValidationError("cannot create SUPER_ADMIN via /users")
    new_user = user_service.create_user(
        db,
        scope,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role=role,
        phone=payload.phone,
    )
    return success_response(user_payload(new_user))


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "users.edit")
    scope = company_scope(user=user)
    target = db.get(User, user_id)
    if target is None or str(target.company_id) != scope:
        raise NotFoundError("User")
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "role" in data:
        try:
            data["role"] = Role(data["role"])
        except ValueError:
            raise ValidationError(f"invalid role '{data['role']}'")
    if data.get("role") == Role.SUPER_ADMIN:
        raise ValidationError("cannot change role to SUPER_ADMIN")
    for key, value in data.items():
        if hasattr(target, key):
            setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return success_response(user_payload(target))


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str,
    payload: ResetPasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "users.edit")
    scope = company_scope(user=user)
    target = db.get(User, user_id)
    if target is None or str(target.company_id) != scope:
        raise NotFoundError("User")
    user_service.set_password(db, target, payload.new_password)
    return success_response({"message": "password reset"})