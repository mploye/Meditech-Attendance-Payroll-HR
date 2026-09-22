from typing import Any

from models.enums import MappingSyncStatus


class ESSLException(Exception):
    """Base eSSL integration error."""

    code: str = "ESSL_ERROR"

    def __init__(self, message: str, details: Any = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class ESSLConnectionErrorESSL(ESSLException):
    """Device or endpoint unreachable."""

    code: str = "ESSL_CONNECTION_ERROR"


class ESSLAuthError(ESSLException):
    """Authentication with the eTimeTrackLite endpoint failed."""

    code: str = "ESSL_AUTH_ERROR"


class ESSLTimeoutError(ESSLException):
    """Request to the endpoint timed out."""

    code: str = "ESSL_TIMEOUT"


class ESSLInvalidResponseError(ESSLException):
    """Endpoint returned an unparseable or unexpected payload."""

    code: str = "ESSL_INVALID_RESPONSE"


class ESSLUnknownUserError(ESSLException):
    """Device user could not be resolved."""

    code: str = "ESSL_UNKNOWN_USER"


class ESSLSyncFailedError(ESSLException):
    """A device synchronization operation failed."""

    code: str = "ESSL_SYNC_FAILED"


_STATUS_MESSAGES: dict[str, str] = {
    "ESSL_CONNECTION_ERROR": "Device unreachable",
    "ESSL_AUTH_ERROR": "ESSL authentication failed",
    "ESSL_TIMEOUT": "ESSL request timed out",
    "ESSL_INVALID_RESPONSE": "ESSL returned an invalid response",
    "ESSL_UNKNOWN_USER": "Unknown device user",
    "ESSL_SYNC_FAILED": "ESSL device sync failed",
}


def sync_status_from_exception(exc: ESSLException) -> tuple[str, str]:
    """Map an exception to (sync status string, error code)."""
    status = MappingSyncStatus.FAILED.value
    code = getattr(exc, "code", "ESSL_ERROR")
    return status, code


def human_message_for_code(code: str) -> str:
    """Return a human-readable message for a known error code."""
    return _STATUS_MESSAGES.get(code, "ESSL operation failed")