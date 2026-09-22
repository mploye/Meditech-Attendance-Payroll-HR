from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import ensure_perm, get_current_user, get_db, orm_to_dict, resolve_company_id
from core.errors import NotFoundError, success_response
from models.salary import SalaryStructure, SalaryStructureComponent, StatutoryRule
from models.user import User

router = APIRouter()


def _get_structure(db, cid: str, structure_id: str) -> SalaryStructure:
    row = db.get(SalaryStructure, structure_id)
    if row is None or str(row.company_id) != cid:
        raise NotFoundError("Salary structure")
    return row


def _structure_detail(db, structure: SalaryStructure) -> dict:
    data = orm_to_dict(structure)
    data["components"] = [orm_to_dict(c) for c in structure.components]
    return data


@router.get("/structures")
def list_structures(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.view")
    cid = resolve_company_id(user)
    from sqlalchemy import select

    rows = list(db.scalars(select(SalaryStructure).where(SalaryStructure.company_id == cid)))
    return success_response([orm_to_dict(r) for r in rows])


@router.post("/structures")
def create_structure(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.create")
    cid = resolve_company_id(user)
    structure = SalaryStructure(
        company_id=cid,
        name=body["name"],
        code=body.get("code"),
        payment_frequency=body.get("payment_frequency", "MONTHLY"),
        effective_from=date.fromisoformat(body["effective_from"]) if body.get("effective_from") else None,
        effective_to=date.fromisoformat(body["effective_to"]) if body.get("effective_to") else None,
        monthly_gross=float(body.get("monthly_gross", 0)),
        active=bool(body.get("active", True)),
    )
    from models.enums import CalculationType, SalaryComponentType, SalaryFrequency

    if isinstance(structure.payment_frequency, str):
        structure.payment_frequency = SalaryFrequency(structure.payment_frequency)
    db.add(structure)
    db.flush()
    for comp in body.get("components") or []:
        db.add(
            SalaryStructureComponent(
                company_id=cid,
                salary_structure_id=str(structure.id),
                name=comp["name"],
                component_type=SalaryComponentType(comp.get("component_type", "EARNING")),
                calculation_type=CalculationType(comp.get("calculation_type", "FIXED")),
                value=float(comp.get("value", 0)),
                formula=comp.get("formula"),
                sort_order=int(comp.get("sort_order", 0)),
            )
        )
    db.commit()
    db.refresh(structure)
    return success_response(_structure_detail(db, structure))


@router.get("/structures/{structure_id}")
def get_structure(structure_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.view")
    cid = resolve_company_id(user)
    return success_response(_structure_detail(db, _get_structure(db, cid, structure_id)))


@router.patch("/structures/{structure_id}")
def update_structure(structure_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.edit")
    cid = resolve_company_id(user)
    structure = _get_structure(db, cid, structure_id)
    for key in ("name", "code"):
        if key in body:
            setattr(structure, key, body[key])
    if "monthly_gross" in body:
        structure.monthly_gross = float(body["monthly_gross"])
    if "active" in body:
        structure.active = bool(body["active"])
    if "components" in body:
        from models.enums import CalculationType, SalaryComponentType

        for comp in list(structure.components):
            db.delete(comp)
        db.flush()
        for comp in body["components"]:
            db.add(
                SalaryStructureComponent(
                    company_id=cid,
                    salary_structure_id=str(structure.id),
                    name=comp["name"],
                    component_type=SalaryComponentType(comp.get("component_type", "EARNING")),
                    calculation_type=CalculationType(comp.get("calculation_type", "FIXED")),
                    value=float(comp.get("value", 0)),
                    formula=comp.get("formula"),
                    sort_order=int(comp.get("sort_order", 0)),
                )
            )
    db.commit()
    db.refresh(structure)
    return success_response(_structure_detail(db, structure))


@router.post("/structures/{structure_id}/simulate")
def simulate(structure_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.view")
    cid = resolve_company_id(user)
    structure = _get_structure(db, cid, structure_id)
    basic = float(body.get("basic_salary", 0))
    from payroll.calculator import compute_structure_components

    components = compute_structure_components(structure, basic)
    total = sum(c.amount for c in components if c.component_type.value == "EARNING")
    return success_response(
        {
            "components": [
                {
                    "name": c.name,
                    "component_type": c.component_type.value,
                    "amount": round(c.amount, 2),
                }
                for c in components
            ],
            "gross": round(total, 2),
        }
    )


@router.get("/statutory-rules")
def list_rules(user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.view")
    cid = resolve_company_id(user)
    from sqlalchemy import select

    rows = list(db.scalars(select(StatutoryRule).where(StatutoryRule.company_id == cid)))
    return success_response([orm_to_dict(r) for r in rows])


@router.post("/statutory-rules")
def create_rule(body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.create")
    cid = resolve_company_id(user)
    from models.enums import StatutoryRuleType

    rule = StatutoryRule(
        company_id=cid,
        rule_type=StatutoryRuleType(body["rule_type"]),
        region=body.get("region"),
        employee_category=body.get("employee_category"),
        effective_from=date.fromisoformat(body["effective_from"]) if body.get("effective_from") else None,
        effective_to=date.fromisoformat(body["effective_to"]) if body.get("effective_to") else None,
        threshold=float(body.get("threshold", 0)),
        rate=float(body.get("rate", 0)),
        maximum=float(body.get("maximum", 0)),
        calculation_method=body.get("calculation_method"),
        status=bool(body.get("status", True)),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return success_response(orm_to_dict(rule))


@router.patch("/statutory-rules/{rule_id}")
def update_rule(rule_id: str, body: dict, user: User = Depends(get_current_user), db=Depends(get_db)):
    ensure_perm(user, "salary.edit")
    cid = resolve_company_id(user)
    rule = db.get(StatutoryRule, rule_id)
    if rule is None or str(rule.company_id) != cid:
        raise NotFoundError("Statutory rule")
    for key in ("region", "employee_category", "calculation_method"):
        if key in body:
            setattr(rule, key, body[key])
    for key in ("threshold", "rate", "maximum"):
        if key in body:
            setattr(rule, key, float(body[key]))
    if "status" in body:
        rule.status = bool(body["status"])
    db.commit()
    db.refresh(rule)
    return success_response(orm_to_dict(rule))