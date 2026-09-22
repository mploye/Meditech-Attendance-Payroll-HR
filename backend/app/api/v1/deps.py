"""Shared helpers for v1 endpoints: auth helpers, ORM serialization, envelopes."""

import uuid
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Optional

from core.errors import success_response
from models.user import User

from api.v1.current import company_scope, ensure_perm  # noqa: F401


def orm_to_dict(obj: Any, include: Optional[set[str]] = None, exclude: Optional[set[str]] = None) -> Any:
    """Best-effort serialize a SQLAlchemy ORM object to a JSON-safe dict."""
    if obj is None:
        return None
    if isinstance(obj, (list, tuple, set)):
        return [orm_to_dict(o, include=include, exclude=exclude) for o in obj]
    if isinstance(obj, dict):
        return {k: orm_to_dict(v, include=include, exclude=exclude) for k, v in obj.items()}
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    try:
        from sqlalchemy import inspect

        mapper = inspect(type(obj)).mapper
    except Exception:
        return obj
    data: dict[str, Any] = {}
    for column in mapper.column_attrs:
        key = column.key
        if include and key not in include:
            continue
        if exclude and key in exclude:
            continue
        value = getattr(obj, key)
        if isinstance(value, (datetime, date, time)):
            value = value.isoformat()
        elif isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, Enum):
            value = value.value
        data[key] = value
    return data


def page_dict(paginated: dict) -> dict:
    """Normalize a service paginated result into the standard page payload."""
    items = paginated.get("items", [])
    return {
        "items": orm_to_dict(items),
        "total": paginated.get("total", len(items)),
        "page": paginated.get("page", 1),
        "page_size": paginated.get("page_size", 20),
        "pages": paginated.get("pages", 0),
    }


def user_payload(user: User) -> dict:
    return orm_to_dict(user, exclude={"password_hash"})