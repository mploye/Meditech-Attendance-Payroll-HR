from datetime import date
from typing import Optional, Sequence, Union

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from core.config import settings
from models.company import Company
from models.enums import StatutoryRuleType
from models.salary import StatutoryRule

_PF_DEFAULT_THRESHOLD = 15000.0
_TDS_SLABS = (
    (0.0, 300000.0, 0.0, 0.0),
    (0.05, 300000.0, 15000.0, 600000.0),
    (0.10, 600000.0, 15000.0, 900000.0),
    (0.20, 900000.0, 45000.0, float("inf")),
)


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def statutory_defaults(company: Company) -> dict:
    """Return statutory fallback parameters from settings plus company region."""
    return {
        "pf_rate": float(settings.DEFAULT_PF_RATE),
        "pf_threshold": _PF_DEFAULT_THRESHOLD,
        "esi_employee_rate": float(settings.DEFAULT_ESI_RATE_EMPLOYEE),
        "esi_employer_rate": float(settings.DEFAULT_ESI_RATE_EMPLOYER),
        "esi_threshold": float(settings.DEFAULT_ESI_THRESHOLD),
        "pt_max": float(settings.DEFAULT_PT_MAX),
        "region": company.statutory_state,
    }


def resolve_rules(
    db: Session, company_id: str, rule_type: StatutoryRuleType
) -> StatutoryRule | None:
    """Return the single effective StatutoryRule for a company and rule type."""
    today = date.today()
    return db.scalar(
        select(StatutoryRule)
        .where(
            and_(
                StatutoryRule.company_id == company_id,
                StatutoryRule.rule_type == rule_type,
                StatutoryRule.status.is_(True),
                or_(StatutoryRule.effective_from.is_(None), StatutoryRule.effective_from <= today),
                or_(StatutoryRule.effective_to.is_(None), StatutoryRule.effective_to >= today),
            )
        )
        .order_by(StatutoryRule.effective_from.desc().nullslast(), StatutoryRule.created_at.desc())
        .limit(1)
    )


def _rule_rate(rule: StatutoryRule | None, default_rate: float) -> float:
    """Return the rule rate when explicitly configured, else the default."""
    if rule is not None and rule.rate:
        return float(rule.rate)
    return default_rate


def calculate_pf(
    basic_gross: float, rule: StatutoryRule | None, defaults: dict
) -> float:
    """Return the employee PF contribution (12% of capped basic)."""
    threshold = float(rule.threshold) if rule is not None and rule.threshold else float(defaults.get("pf_threshold") or 0)
    capped = basic_gross
    if threshold > 0:
        capped = min(basic_gross, threshold)
    rate = _rule_rate(rule, float(defaults.get("pf_rate") or settings.DEFAULT_PF_RATE))
    return round(capped * rate, 1)


def calculate_esi(
    gross: float, rule: StatutoryRule | None, defaults: dict
) -> tuple[float, float]:
    """Return (employee_share, employer_share) ESI contributions or zeros above threshold."""
    threshold = (
        float(rule.threshold)
        if rule is not None and rule.threshold
        else float(defaults.get("esi_threshold") or 0)
    )
    if threshold > 0 and gross > threshold:
        return 0.0, 0.0
    emp_rate = _rule_rate(
        rule, float(defaults.get("esi_employee_rate") or settings.DEFAULT_ESI_RATE_EMPLOYEE)
    )
    empr_rate = float(defaults.get("esi_employer_rate") or settings.DEFAULT_ESI_RATE_EMPLOYER)
    return _round2(gross * emp_rate), _round2(gross * empr_rate)


def _pick_pt_rule(
    rules: Union[StatutoryRule, Sequence[StatutoryRule], None], region: str | None
) -> StatutoryRule | None:
    """Pick a professionally-configured PT rule matching a region if available."""
    if rules is None:
        return None
    pool: Sequence[StatutoryRule] = rules if isinstance(rules, (list, tuple)) else [rules]
    for rule in pool:
        if rule.rule_type != StatutoryRuleType.PT:
            continue
        if rule.region and region and rule.region.lower() == str(region).lower():
            return rule
    for rule in pool:
        if rule.rule_type == StatutoryRuleType.PT and not rule.region:
            return rule
    return pool[0] if pool else None


def calculate_pt(
    gross: float, region: str | None, rules: Union[StatutoryRule, Sequence[StatutoryRule], None]
) -> float:
    """Return the professional tax for a gross salary using the configured slab."""
    rule = _pick_pt_rule(rules, region)
    if rule is not None and rule.rate:
        return _round2(rule.rate)
    threshold = float(rule.threshold) if rule is not None and rule.threshold else None
    if threshold is not None and gross <= threshold:
        return 0.0
    if gross <= 15000:
        return 0.0
    if gross <= 20000:
        return 150.0
    if gross <= 25000:
        return 200.0
    return 200.0


def calculate_tds(gross_annualized: float, rule: StatutoryRule | None) -> float:
    """Return the monthly TDS share for an annualized gross salary."""
    annual = float(gross_annualized or 0)
    if rule is not None and rule.rate and rule.threshold:
        annual_tax = max(0.0, annual - float(rule.threshold)) * float(rule.rate)
        return _round2(annual_tax / 12)
    if annual <= 300000:
        annual_tax = 0.0
    elif annual <= 600000:
        annual_tax = 0.05 * (annual - 300000)
    elif annual <= 900000:
        annual_tax = 15000.0 + 0.10 * (annual - 600000)
    else:
        annual_tax = 45000.0 + 0.20 * (annual - 900000)
    return _round2(annual_tax / 12)