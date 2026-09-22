import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from models.enums import EventType


def build_idempotency_key(
    company_id: str | None,
    device_user_id: str,
    timestamp: datetime,
    event_type: EventType,
) -> str:
    """Deterministic SHA-256 idempotency key for an attendance transaction."""
    ts = timestamp.astimezone(timezone.utc).isoformat()
    raw = f"{company_id or ''}|{device_user_id}|{ts}|{event_type.value}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ESSLTransaction(BaseModel):
    """Normalized transaction received from an eSSL device."""

    device_user_id: str
    timestamp: datetime
    event_type: EventType
    external_event_id: Optional[str] = None
    raw: Optional[dict] = None


class ESSLEnrollmentStatus(BaseModel):
    """Enrollment state of a device user."""

    device_user_id: str
    face_registered: bool = False
    fingerprint_registered: bool = False
    status: str = "UNKNOWN"


class ESSLOperationResult(BaseModel):
    """Outcome of a single eSSL device operation."""

    model_config = ConfigDict(from_attributes=True)

    success: bool
    operation: str
    device_user_id: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None