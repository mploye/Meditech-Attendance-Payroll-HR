from datetime import datetime, timezone
from typing import Any, Optional

from integrations.essl.client import ESSLConnectionResult
from integrations.essl.config import ESSLConfiguration
from integrations.essl.schemas import ESSLOperationResult, ESSLTransaction
from models.enums import EventType


class MockESSLClient:
    """In-memory stand-in for ESSLClient; useful for tests and local development."""

    last_called: list[str] = []

    def __init__(self, config: ESSLConfiguration) -> None:
        self.config = config
        self._users: dict[str, dict[str, Any]] = {}
        self._transactions: list[ESSLTransaction] = []

    def _record_call(self, operation: str) -> None:
        MockESSLClient.last_called.append(operation)

    def supports(self, op: str) -> bool:
        """Whether the configured capabilities allow the given operation."""
        return op in self.config.capabilities

    def generate_transaction(
        self,
        device_user_id: str,
        timestamp: Optional[datetime] = None,
        event_type: str = "IN",
    ) -> ESSLTransaction:
        """Seed a transaction for tests."""
        ts = timestamp or datetime.now(timezone.utc)
        parsed_type = EventType(event_type) if event_type in ("IN", "OUT") else EventType.UNKNOWN
        tx = ESSLTransaction(
            device_user_id=device_user_id,
            timestamp=ts,
            event_type=parsed_type,
            raw={"seeded": True, "device_user_id": device_user_id},
        )
        self._transactions.append(tx)
        return tx

    async def test_connection(self) -> ESSLConnectionResult:
        self._record_call("test_connection")
        return ESSLConnectionResult(
            success=True,
            status="CONNECTED",
            message="Mock ESSL endpoint reachable",
            error_code=None,
        )

    async def add_employee(self, employee_code: str, employee_name: str, device_user_id: str) -> ESSLOperationResult:
        self._record_call("add_employee")
        self._users[device_user_id] = {"code": employee_code, "name": employee_name}
        return ESSLOperationResult(
            success=True,
            operation="add_employee",
            device_user_id=device_user_id,
            message="AddEmployee completed",
        )

    async def delete_user(self, device_user_id: str) -> ESSLOperationResult:
        self._record_call("delete_user")
        self._users.pop(device_user_id, None)
        return ESSLOperationResult(
            success=True,
            operation="delete_user",
            device_user_id=device_user_id,
            message="DeleteUser completed",
        )

    async def enroll_user_face(self, device_user_id: str, image_b64: Optional[str]) -> ESSLOperationResult:
        self._record_call("enroll_face")
        user = self._users.setdefault(device_user_id, {"code": device_user_id, "name": ""})
        user["face_registered"] = True
        return ESSLOperationResult(
            success=True,
            operation="enroll_face",
            device_user_id=device_user_id,
            message="EnrollUserFace completed",
        )

    async def enroll_user_fp(self, device_user_id: str, template: Optional[str]) -> ESSLOperationResult:
        self._record_call("enroll_fp")
        user = self._users.setdefault(device_user_id, {"code": device_user_id, "name": ""})
        user["fingerprint_registered"] = True
        return ESSLOperationResult(
            success=True,
            operation="enroll_fp",
            device_user_id=device_user_id,
            message="EnrollUserFP completed",
        )

    async def block_unblock_user(self, device_user_id: str, blocked: bool) -> ESSLOperationResult:
        self._record_call("block_user" if blocked else "unblock_user")
        user = self._users.setdefault(device_user_id, {"code": device_user_id, "name": ""})
        user["blocked"] = blocked
        return ESSLOperationResult(
            success=True,
            operation="block_user" if blocked else "unblock_user",
            device_user_id=device_user_id,
            message="BlockUnblockUser completed",
        )

    async def get_transactions(
        self,
        from_: datetime,
        to: datetime,
        device_user_id: Optional[str] = None,
    ) -> list[ESSLTransaction]:
        self._record_call("get_transactions")
        result = []
        for tx in self._transactions:
            if device_user_id and tx.device_user_id != device_user_id:
                continue
            if tx.timestamp < from_ or tx.timestamp > to:
                continue
            result.append(tx)
        return result

    async def get_command_status(self, command_id: str) -> ESSLOperationResult:
        self._record_call("get_command_status")
        return ESSLOperationResult(
            success=True,
            operation="get_command_status",
            message="GetCommandStatus completed",
        )