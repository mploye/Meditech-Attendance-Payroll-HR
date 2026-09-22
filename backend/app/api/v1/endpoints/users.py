from fastapi import APIRouter, Depends

from api.deps import ensure_perm, get_current_user, get_db, resolve_company_id, user_dict
from core.errors import success_response
from core.security import hash_password
from models.enums import Role
from models.user import User
from services import user_service

router = APIRouter()


@router.get("/")
def list_users(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "users.view")
    cid = resolve_company_id(user)
    users = user_service.list_users(db, cid)
    return success_response([user_dict(u) for u in users])


@router.post("/")
def create_user(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "users.create")
    cid = resolve_company_id(user)
    role = Role(body.get("role") or Role.EMPLOYEE.value) if isinstance(body.get("role"), str) else Role.EMPLOYEE
    created = user_service.create_user(
        db,
        cid,
        email=body["email"],
        password=body.get("password") or "Welcome@123",
        full_name=body.get("full_name") or body["email"],
        role=role,
        phone=body.get("phone"),
    )
    return success_response(user_dict(created))


@router.patch("/{user_id}")
def update_user(user_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "users.edit")
    cid = resolve_company_id(user)
    target = db.get(User, user_id)
    if target is None or (target.company_id and str(target.company_id) != cid):
        from core.errors import NotFoundError

        raise NotFoundError("User")
    if "role" in body:
        target.role = Role(body["role"]) if isinstance(body["role"], str) else body["role"]
    if "is_active" in body:
        target.is_active = bool(body["is_active"])
    if "full_name" in body:
        target.full_name = body["full_name"]
    db.commit()
    db.refresh(target)
    return success_response(user_dict(target))


@router.post("/{user_id}/reset-password")
def reset_password(user_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "users.edit")
    cid = resolve_company_id(user)
    target = db.get(User, user_id)
    if target is None or (target.company_id and str(target.company_id) != cid):
        from core.errors import NotFoundError

        raise NotFoundError("User")
    new_password = body.get("new_password") or body.get("password")
    if not new_password:
        from core.errors import ValidationError

        raise ValidationError("new_password is required")
    user_service.set_password(db, target, new_password)
    return success_response({"message": "Password reset"})