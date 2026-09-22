"""Authentication endpoints: bootstrap, login, me, change-password, company onboarding."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v1.deps import ensure_perm, orm_to_dict, user_payload
from core.database import get_db
from core.deps import get_current_user
from core.errors import ConflictError, UnauthorizedError, ValidationError, success_response
from core.security import create_access_token, hash_password, verify_password
from models.enums import Role
from models.user import User
from schemas.auth import RegisterSuperAdminRequest
from schemas.change_password import ChangePasswordRequest
from schemas.login import LoginRequest
from services import company_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthCompanyAdmin(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str


class AuthCompanyRequest(BaseModel):
    name: str
    short_name: str
    legal_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    pincode: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    gstin: Optional[str] = None
    pan: Optional[str] = None
    statutory_state: Optional[str] = None
    admin_user: AuthCompanyAdmin


@router.post("/register-super-admin")
def register_super_admin(
    payload: RegisterSuperAdminRequest, db: Session = Depends(get_db)
):
    """Bootstrap the first SUPER_ADMIN. Fails if one already exists."""
    existing = db.scalar(
        select(User).where(User.role == Role.SUPER_ADMIN).limit(1)
    )
    if existing is not None:
        raise ConflictError("a SUPER_ADMIN already exists; use login")
    user = User(
        email=payload.email.strip().lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=Role.SUPER_ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response(user_payload(user))


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("User account is inactive")
    user.last_login_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.commit()
    token = create_access_token(
        str(user.id),
        extra={"role": user.role.value, "company_id": str(user.company_id) if user.company_id else None},
    )
    return success_response({"access_token": token, "token_type": "bearer", "user": user_payload(user)})


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return success_response(user_payload(user))


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise UnauthorizedError("Old password is incorrect")
    user_service.set_password(db, user, payload.new_password)
    return success_response({"message": "password updated"})


@router.post("/companies")
def create_company_with_admin(
    payload: AuthCompanyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """SUPER_ADMIN onboards a company together with its COMPANY_ADMIN user."""
    ensure_perm(user, "companies.edit")
    company = company_service.create_company(
        db,
        name=payload.name,
        short_name=payload.short_name,
        legal_name=payload.legal_name,
        email=payload.email,
        phone=payload.phone,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        pincode=payload.pincode,
        timezone=payload.timezone,
        gstin=payload.gstin,
        pan=payload.pan,
        statutory_state=payload.statutory_state,
    )
    admin = user_service.create_user(
        db,
        str(company.id),
        email=payload.admin_user.email,
        password=payload.admin_user.password,
        full_name=payload.admin_user.full_name,
        role=Role.COMPANY_ADMIN,
    )
    return success_response({"company": orm_to_dict(company), "admin_user": user_payload(admin)})