from sqlalchemy import select
from sqlalchemy.orm import Session

from core.errors import ConflictError, ValidationError
from core.security import hash_password
from core.supabase_sync import sync_supabase_password, sync_supabase_user
from models.enums import Role
from models.user import User


def create_user(
    db: Session,
    company_id: str,
    *,
    email: str,
    password: str,
    full_name: str,
    role: Role,
    phone: str | None = None,
) -> User:
    """Create a user for a company, rejecting a duplicate email."""
    email = (email or "").strip().lower()
    if not email or not password:
        raise ValidationError("email and password are required")
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError(f"user with email '{email}' already exists")
    role = role if isinstance(role, Role) else Role(role)
    user = User(
        company_id=company_id,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        phone=phone,
    )
    db.add(user)
    db.flush()
    db.commit()
    db.refresh(user)
    sync_supabase_user(email, password, full_name)
    return user


def set_password(db: Session, user: User, new_password: str) -> None:
    """Hash and persist a new password for a user."""
    if not new_password:
        raise ValidationError("new password is required")
    user.password_hash = hash_password(new_password)
    db.flush()
    db.commit()
    sync_supabase_password(user.email, new_password)


def list_users(db: Session, company_id: str) -> list[User]:
    """List users belonging to a company."""
    return list(
        db.scalars(
            select(User).where(User.company_id == company_id).order_by(User.created_at)
        )
    )