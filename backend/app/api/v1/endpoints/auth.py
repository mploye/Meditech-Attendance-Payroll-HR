from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db, user_dict
from core.config import settings
from core.errors import ConflictError, UnauthorizedError, ValidationError, error_response, success_response
from core.security import create_access_token, hash_password, verify_password
from models.enums import Role
from models.user import User

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterSuperAdminRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CreateCompanyRequest(BaseModel):
    company: dict
    admin_user: dict


@router.post("/register-super-admin")
def register_super_admin(body: RegisterSuperAdminRequest, db: Session = Depends(get_db)):
    exists = db.scalar(select(func.count(User.id)).where(User.role == Role.SUPER_ADMIN)) or 0
    if exists > 0:
        raise ConflictError("SUPER_ADMIN already exists")
    user = User(
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=Role.SUPER_ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response(user_dict(user))


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(
        str(user.id),
        extra={"role": user.role.value, "company_id": str(user.company_id) if user.company_id else None},
    )
    return success_response({"access_token": token, "token_type": "bearer", "user": user_dict(user)})


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return success_response(user_dict(user))


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.old_password, user.password_hash):
        raise ValidationError("Old password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return success_response({"message": "Password updated"})


@router.post("/companies")
def create_company_and_admin(
    body: CreateCompanyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != Role.SUPER_ADMIN:
        from api.deps import ensure_perm

        ensure_perm(user, "companies.create")
    from services.company_service import create_company, ensure_default_shift
    from services.user_service import create_user

    company = create_company(db, **body.company)
    admin = body.admin_user or {}
    admin_user = create_user(
        db,
        str(company.id),
        email=admin.get("email"),
        password=admin.get("password") or "changeme",
        full_name=admin.get("full_name") or admin.get("email"),
        role=Role.COMPANY_ADMIN,
    )
    ensure_default_shift(db, str(company.id))
    return success_response(
        {"company": orm_dict(company), "admin_user": user_dict(admin_user), "essl": None}
    )


def orm_dict(obj):
    from api.deps import orm_to_dict

    return orm_to_dict(obj)