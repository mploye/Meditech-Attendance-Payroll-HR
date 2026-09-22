"""Salary structure and statutory rule endpoints under /salary."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.v1.deps import company_scope, ensure_perm, orm_to_dict
from core.database import get_db
from core.deps import get_current_user
from core.errors import NotFoundError, success_response
from models.enums import SalaryFrequency, StatutoryRuleType
from models.salary import SalaryStructure, SalaryStructureComponent, StatutoryRule
from models.user import User
from schemas.salary_structure import SalaryStructureCreateRequest, SalaryStructureUpdateRequest
from schemas.statutory_rule import StatutoryRuleUpsertRequest

router = APIRouter(prefix="/salary", tags=["salary"])


def _get_structure(db: Session, company_id: str, structure_id: str) -> SalaryStructure:
    structure = db.scalar(
        select(SalaryStructure).where(SalaryStructure.id == structure_id, SalaryStructure.company_id == company_id)
    )
    if structure is None:
        raise NotFoundError("SalaryStructure")
    return structure


@router.get("/structures")
def list_structures(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.view")
    scope = company_scope(user=user)
    rows = list(
        db.scalars(select(SalaryStructure).where(SalaryStructure.company_id == scope).order_by(SalaryStructure.name))
    )
    return success_response(orm_to_dict(rows))


@router.post("/structures")
def create_structure(
    payload: SalaryStructureCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.create")
    scope = company_scope(user=user)
    data = payload.model_dump()
    frequency = SalaryFrequency(data.get("payment_frequency", "MONTHLY") or "MONTHLY")
    structure = SalaryStructure(
        company_id=scope,
        name=data["name"],
        code=data.get("code"),
        payment_frequency=frequency,
        effective_from=_parse_date(data.get("effective_from")) if data.get("effective_from") else None,
        effective_to=_parse_date(data.get("effective_to")) if data.get("effective_to") else None,
        monthly_gross=data.get("monthly_gross") or 0,
        active=data.get("active", True),
    )
    db.add(structure)
    db.commit()
    db.refresh(structure)
    return success_response(orm_to_dict(structure))


@router.get("/structures/{structure_id}")
def get_structure(
    structure_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.view")
    scope = company_scope(user=user)
    structure = _get_structure(db, scope, structure_id)
    return success_response(orm_to_dict(structure))


@router.patch("/structures/{structure_id}")
def update_structure(
    structure_id: str,
    payload: SalaryStructureUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.edit")
    scope = company_scope(user=user)
    structure = _get_structure(db, scope, structure_id)
    data = payload.model_dump(exclude_unset=True)
    if "payment_frequency" in data and data["payment_frequency"]:
        structure.payment_frequency = SalaryFrequency(data["payment_frequency"])
    for key in ("name", "code", "monthly_gross", "active"):
        if key in data:
            setattr(structure, key, data[key])
    if "effective_from" in data:
        structure.effective_from = _parse_date(data["effective_from"]) if data["effective_from"] else None
    if "effective_to" in data:
        structure.effective_to = _parse_date(data["effective_to"]) if data["effective_to"] else None
    db.commit()
    db.refresh(structure)
    return success_response(orm_to_dict(structure))


@router.get("/statutory-rules")
def list_statutory_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.view")
    scope = company_scope(user=user)
    rows = list(
        db.scalars(select(StatutoryRule).where(StatutoryRule.company_id == scope).order_by(StatutoryRule.rule_type))
    )
    return success_response(orm_to_dict(rows))


@router.post("/statutory-rules")
def create_statutory_rule(
    payload: StatutoryRuleUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.create")
    scope = company_scope(user=user)
    data = payload.model_dump()
    rule = StatutoryRule(
        company_id=scope,
        rule_type=StatutoryRuleType(data["rule_type"]),
        region=data.get("region"),
        employee_category=data.get("employee_category"),
        effective_from=_parse_date(data["effective_from"]) if data.get("effective_from") else None,
        effective_to=_parse_date(data["effective_to"]) if data.get("effective_to") else None,
        threshold=data.get("threshold") or 0,
        rate=data.get("rate") or 0,
        maximum=data.get("maximum") or 0,
        calculation_method=data.get("calculation_method"),
        status=data.get("status", True),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return success_response(orm_to_dict(rule))


@router.patch("/statutory-rules/{rule_id}")
def update_statutory_rule(
    rule_id: str,
    payload: StatutoryRuleUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.edit")
    scope = company_scope(user=user)
    rule = db.scalar(
        select(StatutoryRule).where(StatutoryRule.id == rule_id, StatutoryRule.company_id == scope)
    )
    if rule is None:
        raise NotFoundError("StatutoryRule")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "rule_type":
            rule.rule_type = StatutoryRuleType(value)
        elif key in ("effective_from", "effective_to"):
            setattr(rule, key, _parse_date(value) if value else None)
        elif hasattr(rule, key):
            setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return success_response(orm_to_dict(rule))


@router.post("/structures/{structure_id}/simulate")
def simulate_structure(
    structure_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_perm(user, "salary.view")
    scope = company_scope(user=user)
    _get_structure(db, scope, structure_id)
    basic = float(payload.get("basic_salary") or 0)
    return success_response({"basic_salary": basic, "gross_salary": basic, "deductions": [], "simulated": True})


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])