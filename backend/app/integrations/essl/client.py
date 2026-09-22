from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from integrations.essl.config import ESSLConfiguration
from integrations.essl.exceptions import (
    ESSLConnectionErrorESSL,
    ESSLInvalidResponseError,
    ESSLTimeoutError,
)
from integrations.essl.schemas import ESSLOperationResult, ESSLTransaction
from models.enums import EventType


@dataclass
class ESSLConnectionResult:
    """Result of a connection test against the eSSL endpoint."""

    success: bool
    status: str
    message: str
    error_code: Optional[str] = None


class ESSLClient:
    """
    HTTP adapter for the eTimeTrackLite eSSL portal API.

    NOTE: the real eTimeTrackLite contract is WSDL/HTTP based and varies by
    installed version. This client is intentionally conservative and sends a
    JSON envelope ({operation, params, auth} -> JSON response). The request
    shape MUST be aligned with the installed eTimeTrackLite version's
    documentation before production use; do not invent undocumented formats.
    """

    def __init__(self, config: ESSLConfiguration) -> None:
        self.config = config

    def supports(self, op: str) -> bool:
        """Whether the configured capabilities allow the given operation."""
        return op in self.config.capabilities

    def _enforce_enabled(self) -> None:
        if not self.config.enabled:
            raise ESSLConnectionErrorESSL("ESSL not enabled for this company")

    def _operation_url(self, operation: str) -> str:
        base = self.config.base_url.rstrip("/")
        return f"{base}/{operation}"

    def _build_params(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = dict(params)
        if self.config.company_short_name:
            payload.setdefault("company_short_name", self.config.company_short_name)
        return payload

    async def _post(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON envelope and return the parsed JSON response dict."""
        self._enforce_enabled()
        url = self._operation_url(operation)
        body = {
            "operation": operation,
            "params": self._build_params(operation, params),
            "auth": {"api_key": self.config.api_key, "username": self.config.username},
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_sec, verify=False) as http:
                response = await http.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise ESSLTimeoutError("ESSL request timed out", details=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ESSLConnectionErrorESSL("ESSL endpoint unreachable", details=str(exc)) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise ESSLInvalidResponseError("ESSL returned non-JSON response", details=str(exc)) from exc
        if not isinstance(data, dict):
            raise ESSLInvalidResponseError("ESSL returned an unexpected response shape")
        return data

    def _to_operation_result(
        self,
        data: dict[str, Any],
        operation: str,
        device_user_id: Optional[str],
        display: str,
    ) -> ESSLOperationResult:
        success = bool(data.get("success"))
        error = data.get("error")
        if isinstance(error, dict):
            error_code = error.get("code")
            message = error.get("message")
        elif isinstance(error, str):
            error_code = None
            message = error
        else:
            error_code = None
            message = None
        if success and not message:
            message = f"{display} completed"
        return ESSLOperationResult(
            success=success,
            operation=operation,
            device_user_id=device_user_id,
            error_code=error_code,
            message=message,
        )

    async def test_connection(self) -> ESSLConnectionResult:
        status = self._post("GetCommandStatus", {"command_id": "ping", "command_name": "ping"})
        return ESSLConnectionResult(
            success=True,
            status="CONNECTED",
            message=status.get("message") or "ESSL endpoint reachable",
            error_code=None,
        )

    async def add_employee(self, employee_code: str, employee_name: str, device_user_id: str) -> ESSLOperationResult:
        data = await self._post(
            "AddEmployee",
            {"employee_code": employee_code, "employee_name": employee_name, "employee_device_id": device_user_id},
        )
        return self._to_operation_result(data, "add_employee", device_user_id, "AddEmployee")

    async def delete_user(self, device_user_id: str) -> ESSLOperationResult:
        data = await self._post("DeleteUser", {"employee_device_id": device_user_id})
        return self._to_operation_result(data, "delete_user", device_user_id, "DeleteUser")

    async def enroll_user_face(self, device_user_id: str, image_b64: Optional[str]) -> ESSLOperationResult:
        data = await self._post(
            "EnrollUserFace", {"employee_device_id": device_user_id, "image_b64": image_b64}
        )
        return self._to_operation_result(data, "enroll_face", device_user_id, "EnrollUserFace")

    async def enroll_user_fp(self, device_user_id: str, template: Optional[str]) -> ESSLOperationResult:
        data = await self._post(
            "EnrollUserFP", {"employee_device_id": device_user_id, "template": template}
        )
        return self._to_operation_result(data, "enroll_fp", device_user_id, "EnrollUserFP")

    async def block_unblock_user(self, device_user_id: str, blocked: bool) -> ESSLOperationResult:
        data = await self._post("BlockUnblockUser", {"employee_device_id": device_user_id, "blocked": blocked})
        return self._to_operation_result(data, "block_user" if blocked else "unblock_user", device_user_id, "BlockUnblockUser")

    def _try_parse_text(self, text: str) -> Optional[datetime]:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _parse_timestamp(self, item: dict[str, Any]) -> Optional[datetime]:
        value = item.get("timestamp") or item.get("DateTime") or item.get("punch_time") or item.get("verify_time") or item.get("time")
        if value is None:
            date_part = item.get("date") or item.get("punch_date") or item.get("Date")
            time_part = item.get("time") or item.get("punch_time") or item.get("Time")
            if date_part and time_part:
                value = f"{date_part} {time_part}"
        if value is None:
            return None
        if isinstance(value, datetime):
            ts = value
        elif isinstance(value, (int, float)):
            ts = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            ts = self._try_parse_text(str(value).strip())
        if ts is None:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    def _parse_event_type(self, item: dict[str, Any]) -> EventType:
        value = item.get("event_type") or item.get("attstate") or item.get("state") or item.get("status") or item.get("Punch") or item.get("punch")
        if value is None:
            return EventType.UNKNOWN
        token = str(value).strip().lower()
        if token in ("in", "1", "check_in", "0"):
            return EventType.IN
        if token in ("out", "2", "check_out", "255"):
            return EventType.OUT
        return EventType.UNKNOWN

    def _parse_transaction(self, item: Any) -> Optional[ESSLTransaction]:
        if not isinstance(item, dict):
            return None
        device_user_id = (
            item.get("device_user_id")
            or item.get("UserNo")
            or item.get("EnrollId")
            or item.get("employee_code")
        )
        if not device_user_id:
            return None
        ts = self._parse_timestamp(item)
        if ts is None:
            return None
        event_type = self._parse_event_type(item)
        external_event_id = item.get("external_event_id") or item.get("LogId") or item.get("record_id") or item.get("id")
        return ESSLTransaction(
            device_user_id=str(device_user_id),
            timestamp=ts,
            event_type=event_type,
            external_event_id=str(external_event_id) if external_event_id is not None else None,
            raw=item,
        )

    async def get_transactions(
        self,
        from_: datetime,
        to: datetime,
        device_user_id: Optional[str] = None,
    ) -> list[ESSLTransaction]:
        params: dict[str, Any] = {
            "from": from_.astimezone(timezone.utc).isoformat(),
            "to": to.astimezone(timezone.utc).isoformat(),
        }
        if device_user_id:
            params["employee_device_id"] = device_user_id
        data = await self._post("GetTransactionsLog", params)
        items = data.get("transactions") or data.get("data") or data.get("records") or data.get("result")
        if not isinstance(items, list):
            return []
        transactions: list[ESSLTransaction] = []
        for item in items:
            parsed = self._parse_transaction(item)
            if parsed is not None:
                transactions.append(parsed)
        return transactions

    async def get_command_status(self, command_id: str) -> ESSLOperationResult:
        data = await self._post("GetCommandStatus", {"command_id": command_id})
        return self._to_operation_result(data, "get_command_status", None, "GetCommandStatus")