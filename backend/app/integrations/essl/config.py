import base64
import json
from dataclasses import dataclass, field
from typing import Any

from core.config import settings
from models.device import ESSLConfig

from integrations.essl.constants import DEFAULT_CAPABILITIES


def encrypt_value(value: str) -> str:
    """XOR-encode a secret string with the JWT secret (never plaintext storage)."""
    key = settings.JWT_SECRET.encode("utf-8")
    data = value.encode("utf-8")
    encoded = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.urlsafe_b64encode(encoded).decode("ascii")


def decrypt_value(encoded: str) -> str:
    """Decode a value produced by encrypt_value."""
    key = settings.JWT_SECRET.encode("utf-8")
    data = base64.urlsafe_b64decode(encoded.encode("ascii"))
    decoded = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return decoded.decode("utf-8")


@dataclass
class ESSLConfiguration:
    """Runtime configuration for the eSSL/eTimeTrackLite integration."""

    base_url: str = settings.ESSL_BASE_URL
    username: str = settings.ESSL_USERNAME
    password: str = settings.ESSL_PASSWORD
    api_key: str = settings.ESSL_API_KEY
    company_short_name: str = settings.ESSL_COMPANY_SHORT_NAME
    timeout_sec: int = settings.ESSL_TIMEOUT_SECONDS
    sync_interval_sec: int = settings.ESSL_SYNC_INTERVAL_SECONDS
    capabilities: list[str] = field(default_factory=lambda: list(DEFAULT_CAPABILITIES))
    enabled: bool = True

    @classmethod
    def from_settings(cls) -> "ESSLConfiguration":
        """Build a configuration from the global core.config.settings."""
        return cls(
            base_url=settings.ESSL_BASE_URL,
            username=settings.ESSL_USERNAME,
            password=settings.ESSL_PASSWORD,
            api_key=settings.ESSL_API_KEY,
            company_short_name=settings.ESSL_COMPANY_SHORT_NAME,
            timeout_sec=settings.ESSL_TIMEOUT_SECONDS,
            sync_interval_sec=settings.ESSL_SYNC_INTERVAL_SECONDS,
            capabilities=list(DEFAULT_CAPABILITIES),
            enabled=True,
        )

    @classmethod
    def from_db_record(cls, essl_config: ESSLConfig | None) -> "ESSLConfiguration":
        """Build a configuration from a persisted ESSLConfig record."""
        if essl_config is None:
            return cls.from_settings()
        capabilities = list(DEFAULT_CAPABILITIES)
        if essl_config.capabilities:
            try:
                parsed = json.loads(essl_config.capabilities)
                if isinstance(parsed, list):
                    capabilities = [str(c) for c in parsed]
            except (TypeError, ValueError):
                capabilities = list(DEFAULT_CAPABILITIES)
        password = (
            decrypt_value(essl_config.password_encrypted)
            if essl_config.password_encrypted
            else settings.ESSL_PASSWORD
        )
        api_key = (
            decrypt_value(essl_config.api_key_encrypted)
            if essl_config.api_key_encrypted
            else settings.ESSL_API_KEY
        )
        return cls(
            base_url=essl_config.base_url or settings.ESSL_BASE_URL,
            username=essl_config.username or settings.ESSL_USERNAME,
            password=password,
            api_key=api_key,
            company_short_name=essl_config.company_short_name or settings.ESSL_COMPANY_SHORT_NAME,
            timeout_sec=essl_config.timeout_sec,
            sync_interval_sec=essl_config.sync_interval_sec,
            capabilities=capabilities,
            enabled=essl_config.enabled,
        )

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        """Serializable representation; secrets omitted unless explicitly requested."""
        data: dict[str, Any] = {
            "base_url": self.base_url,
            "username": self.username,
            "company_short_name": self.company_short_name,
            "timeout_sec": self.timeout_sec,
            "sync_interval_sec": self.sync_interval_sec,
            "capabilities": list(self.capabilities),
            "enabled": self.enabled,
        }
        if include_secrets:
            data["password"] = self.password
            data["api_key"] = self.api_key
        return data