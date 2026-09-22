"""Designation CRUD endpoints under /designations."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import success_response
from models.user import User
from schemas.designation import DesignationCreateRequest, DesignationUpdateRequest
from services import designation_service

router = APIRouter(prefix="/designations", tags=["designations"])


@router.get("")
def list_designations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "designations.view")
    scope = company_scope(user=user)
    return success_response(orm_to_dict(designation_service.list_all(db, scope)))


@router.post("")
def create_designation(
    payload: DesignationCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "designations.create")
    scope = company_scope(user=user)
    item = designation_service.create(db, scope, payload.model_dump())
    return success_response(orm_to_dict(item))


@router.get("/{obj_id}")
def get_designation(
    obj_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "designations.view")
    scope = company_scope(user=user)
    return success_response(orm_to_dict(designation_service.get(db, scope, obj_id)))


@router.patch("/{obj_id}")
def update_designation(
    obj_id: str,
    payload: DesignationUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "designations.edit")
    scope = company_scope(user=user)
    item = designation_service.update(db, scope, obj_id, payload.model_dump(exclude_unset=True))
    return success_response(orm_to_dict(item))


@router.delete("/{obj_id}")
def delete_designation(
    obj_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "designations.delete")
    scope = company_scope(user=user)
    designation_service.delete(db, scope, obj_id)
    return success_response({"message": "deleted"})