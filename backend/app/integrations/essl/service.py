import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from integrations.essl.client import ESSLClient
from integrations.essl.config import ESSLConfiguration, encrypt_value
from integrations.essl.exceptions import ESSLException, ESSLSyncFailedError
from integrations.essl.mock import MockESSLClient
from integrations.essl.schemas import ESSLTransaction
from models.device import Device, ESSLConfig
from models.employee import Employee
from models.employee_device import EmployeeDevice
from models.enums import MappingSyncStatus


def _device_uses_pull_protocol(device: Device) -> bool:
    """A device is pulled directly when it has an IP and is not portal-only."""
    if not device.ip_address:
        return False
    protocol = (device.protocol or "").lower()
    return protocol in ("", "zk", "zk_tcp", "tcp", "pull")


class ESSLService:
    """Orchestrates eSSL device operations against the persistence layer."""

    def __init__(
        self,
        db: Session,
        config: ESSLConfiguration,
        client: Optional[ESSLClient | MockESSLClient] = None,
        mock_override: Optional[bool] = None,
    ) -> None:
        self.db = db
        self.config = config
        mock_mode = mock_override if mock_override is not None else settings.ESSL_MOCK_MODE
        use_mock = mock_mode or (not config.enabled and settings.ESSL_MOCK_MODE)
        self.client = client or (MockESSLClient(config) if use_mock else ESSLClient(config))

    async def test_connection(self) -> dict[str, Any]:
        result = await self.client.test_connection()
        payload: dict[str, Any] = {
            "success": result.success,
            "provider": "eSSL",
            "status": "CONNECTED" if result.success else "FAILED",
            "message": result.message,
        }
        if result.error_code:
            payload["error_code"] = result.error_code
        return payload

    async def test_device_connection(self, device: Device) -> dict[str, Any]:
        """Test connectivity: direct terminal probe when pull addressing is set,
        otherwise fall back to the configured eTimeTrackLite endpoint."""
        if _device_uses_pull_protocol(device):
            pull = self._build_pull_device(device)
            result = await asyncio.to_thread(pull.test_connection)
            result.setdefault("provider", "eSSL")
            return result
        return await self.test_connection()

    def _employee_display_name(self, employee: Employee) -> str:
        name = " ".join(part for part in (employee.first_name, employee.last_name or "") if part)
        return name or employee.employee_code

    async def sync_employee(
        self,
        company: Any,
        employee: Employee,
        device: Device,
        employee_device: EmployeeDevice,
    ) -> dict[str, Any]:
        """Add an employee to a device and record biometric metadata flags only."""
        device_user_id = employee_device.device_user_id
        add_result = await self.client.add_employee(
            employee.employee_code, self._employee_display_name(employee), device_user_id
        )
        if not add_result.success:
            raise ESSLSyncFailedError(
                f"Failed to add employee {device_user_id}: {add_result.message}",
                details=add_result.error_code,
            )
        enroll_results: list[dict[str, Any]] = []
        partial = False
        if employee_device.face_registered:
            face_result = await self.client.enroll_user_face(device_user_id, None)
            enroll_results.append({"biometric": "face", "success": face_result.success, "message": face_result.message})
            partial = partial or not face_result.success
        if employee_device.fingerprint_registered:
            fp_result = await self.client.enroll_user_fp(device_user_id, None)
            enroll_results.append({"biometric": "fingerprint", "success": fp_result.success, "message": fp_result.message})
            partial = partial or not fp_result.success
        employee_device.sync_status = MappingSyncStatus.PARTIAL if partial else MappingSyncStatus.SYNCED
        employee_device.last_synced_at = datetime.now(timezone.utc)
        self.db.add(employee_device)
        self.db.commit()
        return {
            "success": True,
            "operation": "sync_employee",
            "device_user_id": device_user_id,
            "sync_status": employee_device.sync_status.value,
            "enrollments": enroll_results,
        }

    async def delete_employee_from_device(self, employee_device: EmployeeDevice) -> dict[str, Any]:
        device_user_id = employee_device.device_user_id
        result = await self.client.delete_user(device_user_id)
        if not result.success:
            raise ESSLSyncFailedError(
                f"Failed to delete employee {device_user_id}: {result.message}",
                details=result.error_code,
            )
        employee_device.sync_status = MappingSyncStatus.SYNCED
        employee_device.last_synced_at = datetime.now(timezone.utc)
        self.db.add(employee_device)
        self.db.commit()
        return {
            "success": True,
            "operation": "delete_user",
            "device_user_id": device_user_id,
            "sync_status": employee_device.sync_status.value,
        }

    async def pull_transactions(
        self,
        company: Any,
        device: Device,
        from_: datetime,
        to: datetime,
    ) -> list[ESSLTransaction]:
        """Fetch raw transactions from the device for the given window.

        Devices with a reachable ``ip_address`` are pulled directly over the
        terminal's wire protocol; otherwise the eTimeTrackLite client is used.
        """
        from_ = self._aware_utc(from_)
        to = self._aware_utc(to)
        if _device_uses_pull_protocol(device):
            pull = self._build_pull_device(device)
            return await asyncio.to_thread(pull.read_transactions, from_, to, None)
        transactions = await self.client.get_transactions(from_, to, None)
        return transactions

    def _build_pull_device(self, device: Device):
        """Build a direct terminal client for a device with a network address."""
        from integrations.essl.pulldevice import ZKDevice

        return ZKDevice(
            host=device.ip_address,
            port=device.port,
            timeout=float(self.config.timeout_sec),
            password=0,
            clear_after_pull=False,
        )

    @staticmethod
    def _aware_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def get_essl_config_for_company(db: Session, company_id: str) -> Optional[ESSLConfig]:
        """Return the ESSLConfig row for a company, or None."""
        stmt = select(ESSLConfig).where(ESSLConfig.company_id == company_id)
        return db.execute(stmt).scalar_one_or_none()

    def save_essl_config(self, db: Session, company_id: str, data: dict[str, Any]) -> ESSLConfig:
        """Persist an ESSLConfig for a company, encrypting secrets before storage."""
        record = self.get_essl_config_for_company(db, company_id)
        if record is None:
            record = ESSLConfig(company_id=company_id)
        record.base_url = data.get("base_url", record.base_url)
        record.username = data.get("username", record.username)
        if data.get("password"):
            record.password_encrypted = encrypt_value(str(data["password"]))
        if data.get("api_key"):
            record.api_key_encrypted = encrypt_value(str(data["api_key"]))
        record.company_short_name = data.get("company_short_name", record.company_short_name)
        record.timeout_sec = int(data.get("timeout_sec", record.timeout_sec))
        record.sync_interval_sec = int(data.get("sync_interval_sec", record.sync_interval_sec))
        if "capabilities" in data:
            import json

            record.capabilities = json.dumps(data["capabilities"])
        record.enabled = bool(data.get("enabled", record.enabled))
        db.add(record)
        db.commit()
        db.refresh(record)
        return record