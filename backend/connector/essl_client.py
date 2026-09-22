from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from connector.config import ConnectorConfig


class LocalESSLClient:
    """Synchronous client for the local eTimeTrackLite endpoint."""

    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config

    def _operation_url(self, operation: str) -> str:
        base = self.config.essl_local_base_url.rstrip("/")
        return f"{base}/{operation}"

    def _post(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        body = {
            "operation": operation,
            "params": params,
            "auth": {
                "api_key": "",
                "username": self.config.essl_local_username,
                "password": self.config.essl_local_password,
            },
        }
        with httpx.Client(timeout=self.config.timeout_seconds, verify=False) as http:
            response = http.post(self._operation_url(operation), json=body)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Local eSSL endpoint returned an unexpected response shape")
        return data

    def test_connection(self) -> dict[str, Any]:
        """Probe the local eSSL endpoint and return a health dict."""
        try:
            data = self._post("GetCommandStatus", {"command_id": "ping"})
            return {
                "success": bool(data.get("success", True)),
                "status": "CONNECTED",
                "message": data.get("message") or "Local eSSL endpoint reachable",
                "error_code": None,
            }
        except httpx.HTTPError as exc:
            return {"success": False, "status": "FAILED", "message": str(exc), "error_code": "ESSL_CONNECTION_ERROR"}
        except (ValueError, KeyError) as exc:
            return {"success": False, "status": "FAILED", "message": str(exc), "error_code": "ESSL_INVALID_RESPONSE"}

    def fetch_transactions(self, from_: datetime, to: datetime) -> list[dict[str, Any]]:
        """Pull raw transaction records from the local eSSL device."""
        params: dict[str, Any] = {
            "from": from_.astimezone(timezone.utc).isoformat(),
            "to": to.astimezone(timezone.utc).isoformat(),
        }
        data = self._post("GetTransactionsLog", params)
        items: Any = data.get("transactions") or data.get("data") or data.get("records") or data.get("result")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]