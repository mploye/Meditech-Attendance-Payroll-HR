"""Department CRUD endpoints under /departments."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.user import User
from schemas.department import DepartmentCreateRequest, DepartmentUpdateRequest
from services import department_service

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("")
def list_departments(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "departments.view")
    scope = company_scope(user=user)
    return success_response(orm_to_dict(department_service.list_all(db, scope)))


@router.post("")
def create_department(
    payload: DepartmentCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "departments.create")
    scope = company_scope(user=user)
    item = department_service.create(db, scope, payload.model_dump())
    return success_response(orm_to_dict(item))


@router.get("/{obj_id}")
def get_department(
    obj_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "departments.view")
    scope = company_scope(user=user)
    return success_response(orm_to_dict(department_service.get(db, scope, obj_id)))


@router.patch("/{obj_id}")
def update_department(
    obj_id: str,
    payload: DepartmentUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "departments.edit")
    scope = company_scope(user=user)
    item = department_service.update(db, scope, obj_id, payload.model_dump(exclude_unset=True))
    return success_response(orm_to_dict(item))


@router.delete("/{obj_id}")
def delete_department(
    obj_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "departments.delete")
    scope = company_scope(user=user)
    department_service.delete(db, scope, obj_id)
    return success_response({"message": "deleted"})