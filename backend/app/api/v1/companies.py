"""Company management endpoints under /companies."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import ValidationError, success_response
from models.enums import Role
from models.user import User
from schemas.company_request import CompanyCreateRequest, CompanySettingsRequest, CompanyUpdateRequest
from services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
def list_companies(
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "companies.view")
    if user.role != Role.SUPER_ADMIN:
        return success_response([orm_to_dict(company_service.get_company(db, str(user.company_id)))])
    rows = company_service.list_companies(db, search=search)
    return success_response(orm_to_dict(rows))


@router.post("")
def create_company(
    payload: CompanyCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "companies.edit")
    data = payload.model_dump(exclude_unset=True)
    company = company_service.create_company(db, **data)
    return success_response(orm_to_dict(company))


@router.get("/{company_id}")
def get_company(
    company_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "companies.view")
    scope = company_scope(user=user, company_id=company_id)
    company = company_service.get_company(db, scope)
    return success_response(orm_to_dict(company))


@router.patch("/{company_id}")
def update_company(
    company_id: str,
    payload: CompanyUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "companies.edit")
    scope = company_scope(user=user, company_id=company_id)
    data = payload.model_dump(exclude_unset=True)
    company = company_service.update_company(db, scope, data)
    return success_response(orm_to_dict(company))


@router.patch("/{company_id}/settings")
def update_company_settings(
    company_id: str,
    payload: CompanySettingsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "companies.edit")
    scope = company_scope(user=user, company_id=company_id)
    data = payload.model_dump(exclude_none=True)
    if not data:
        raise ValidationError("no settings provided")
    company = company_service.update_company_settings(db, scope, data)
    return success_response(orm_to_dict(company))