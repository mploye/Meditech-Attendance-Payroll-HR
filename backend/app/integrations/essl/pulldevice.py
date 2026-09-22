"""Pull client for eSSL/ZKTeco standalone terminals (clean-room).

Speaks the TCP TOP protocol implemented in :mod:`protocol` over the SDK's
documented command set to pull attendance transactions, users and capacity
information directly from the device (the vendor "Pull SDK" model).

The device model rows (``Device.ip_address`` / ``Device.port``) identify how
to reach each terminal. This module is intentionally independent of the SDK
DLLs and the eTimeTrackLite portal client; it talks to the device directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from integrations.essl.exceptions import (
    ESSLConnectionErrorESSL,
    ESSLInvalidResponseError,
    ESSLTimeoutError,
)
from integrations.essl.protocol import (
    CMD_ATTLOG_RRQ,
    CMD_CLEAR_ATTLOG,
    CMD_DISABLEDEVICE,
    CMD_ENABLEDEVICE,
    CMD_GET_FREE_SIZES,
    CMD_USERTEMP_RRQ,
    FCT_ATTLOG,
    FCT_USER,
    USER_SIZE_ZK6,
    USER_SIZE_ZK8,
    USHRT_MAX,
    WireError,
    WireTimeoutError,
    ZKConnection,
    decode_time4,
    unpack,
)
from integrations.essl.schemas import ESSLTransaction
from models.enums import EventType

DEFAULT_PORT = 4370


@dataclass
class DeviceUser:
    """A user record as stored on the terminal."""

    uid: int
    name: str
    privilege: int
    password: str = ""
    group_id: str = ""
    user_id: str = ""
    card: int = 0


@dataclass
class AttendanceRecord:
    """A raw attendance/log record as stored on the terminal."""

    user_id: str
    timestamp: datetime
    status: int = 0
    punch: int = 0
    uid: int = 0
    work_code: int = 0


@dataclass
class DeviceCapabilities:
    """Parsed CMD_GET_FREE_SIZES payload."""

    users: int = field(default=0)
    records: int = field(default=0)
    fingers: int = field(default=0)
    cards: int = field(default=0)
    user_packet_size: int = field(default=USER_SIZE_ZK8)


def _event_type(punch: int, status: int) -> EventType:
    """Map a device punch field to the attendance event type.

    The SDK returns ``inOutMode`` (0 = IN, 1 = OUT, 255 = none) with the
    verification status in ``verifyMode``. When the punch mark is ambiguous
    the record is treated as UNKNOWN rather than guessing.
    """
    if punch == 1:
        return EventType.OUT
    if punch == 0:
        return EventType.IN
    return EventType.UNKNOWN


class ZKDevice:
    """High-level pull client bound to one physical terminal."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = 10.0,
        password: int = 0,
        clear_after_pull: bool = False,
    ) -> None:
        self.host = host
        self.port = port or DEFAULT_PORT
        self.timeout = timeout
        self.password = password
        self.clear_after_pull = clear_after_pull
        self.capabilities = DeviceCapabilities()
        self._connection: Optional[ZKConnection] = None

    # -- lifecycle ------------------------------------------------------------

    def _connect(self) -> ZKConnection:
        if self._connection is not None and self._connection.is_connected:
            return self._connection
        conn = ZKConnection(self.host, self.port, self.timeout, self.password)
        try:
            conn.connect()
        except WireTimeoutError as exc:
            raise ESSLTimeoutError("eSSL device did not answer", details=str(exc)) from exc
        except WireError as exc:
            raise ESSLConnectionErrorESSL("eSSL device unreachable", details=str(exc)) from exc
        self._connection = conn
        return conn

    def disconnect(self) -> None:
        if self._connection is not None:
            try:
                self._connection.send_command(CMD_DISABLEDEVICE)
            except WireError:
                pass
            self._connection.close()
        self._connection = None

    # -- basic commands ---------------------------------------------------------

    def enable_device(self) -> bool:
        if not self._connect().command_ok(CMD_ENABLEDEVICE):
            raise ESSLInvalidResponseError("device refused to enable")
        return True

    def disable_device(self) -> bool:
        if not self._connect().command_ok(CMD_DISABLEDEVICE):
            raise ESSLInvalidResponseError("device refused to disable")
        return True

    def ping(self) -> bool:
        """Verify reachability and a working session without touching data."""
        conn = self._connect()
        code, _session, _reply, _data = conn.send_command(CMD_GET_FREE_SIZES)
        return code != USHRT_MAX

    def test_connection(self) -> dict:
        """Return a provider-style connection test result."""
        try:
            conn = self._connect()
            code, _session, _reply, data = conn.send_command(CMD_GET_FREE_SIZES)
            if code == 0xFFFF or len(data) < 20:
                return {"success": False, "status": "ERROR", "message": "device returned an invalid response"}
            return {"success": True, "status": "CONNECTED", "message": f"eSSL device at {self.host}:{self.port}"}
        except (ESSLConnectionErrorESSL, ESSLTimeoutError, ESSLInvalidResponseError) as exc:
            return {"success": False, "status": "ERROR", "message": str(exc)}
        finally:
            self.disconnect()

    # -- data reads ------------------------------------------------------------

    def read_sizes(self) -> DeviceCapabilities:
        """Read memory usage so block parsing knows expected record layouts."""
        conn = self._connect()
        code, _session, _reply, data = conn.send_command(CMD_GET_FREE_SIZES)
        if code == USHRT_MAX:
            raise ESSLInvalidResponseError("device refused capacity query")
        if len(data) < 80:
            raise ESSLInvalidResponseError("capacity payload too short")
        ints = list(unpack("20i", data[:80]))
        caps = DeviceCapabilities(
            users=ints[4],
            fingers=ints[6],
            records=ints[8],
            cards=ints[10],
        )
        dup = data[80:]
        if len(dup) >= 16:
            extra = list(unpack("4i", dup[:16]))
            caps = DeviceCapabilities(
                users=int(extra[0]) or ints[4],
                records=int(extra[1]) or ints[8],
                fingers=int(extra[2]) or ints[6],
                cards=int(extra[3]) or ints[10],
            )
        self.capabilities = caps
        return caps

    def get_users(self) -> list[DeviceUser]:
        """Read all enrolled users from the device."""
        self.read_sizes()
        if self.capabilities.users == 0:
            return []
        conn = self._connect()
        try:
            raw = conn.read_block(CMD_USERTEMP_RRQ, FCT_USER)
        except WireError as exc:
            raise ESSLInvalidResponseError("could not read user block", details=str(exc)) from exc
        if not raw or len(raw) < 4:
            return []
        declared = int.from_bytes(raw[:4], "little")
        payload = raw[4:]
        per_user = declared // max(self.capabilities.users, 1) if declared else 0
        if per_user not in (USER_SIZE_ZK6, USER_SIZE_ZK8):
            per_user = USER_SIZE_ZK6 if declared % USER_SIZE_ZK6 == 0 else USER_SIZE_ZK8
        users: list[DeviceUser] = []
        fmt6 = "<HB5s8sIxBhI"
        fmt8 = "<HB8s24sIx7sx24s"
        while len(payload) >= per_user:
            record = payload[:per_user]
            payload = payload[per_user:]
            if per_user == USER_SIZE_ZK6:
                try:
                    uid, privilege, password, name, card, group_id, _tz, user_id = unpack(fmt6, record)
                except Exception:
                    continue
                user_id = str(user_id)
            else:
                try:
                    uid, privilege, password, name, card, group_id, user_id = unpack(fmt8, record)
                except Exception:
                    continue
                user_id = user_id.split(b"\x00")[0].decode("utf-8", "ignore")
            password = password.split(b"\x00")[0].decode("utf-8", "ignore")
            name = name.split(b"\x00")[0].decode("utf-8", "ignore").strip()
            users.append(
                DeviceUser(
                    uid=uid,
                    name=name or f"NN-{user_id}",
                    privilege=privilege,
                    password=password,
                    group_id=str(group_id),
                    user_id=user_id,
                    card=card,
                )
            )
        return users

    def get_attendance(self) -> list[AttendanceRecord]:
        """Read all attendance records from the device.

        Uses the user table to resolve the stable user id for short records.
        """
        self.read_sizes()
        records = self.capabilities.records
        if records == 0:
            return []
        users = self.get_users()
        by_uid = {u.uid: u for u in users}
        by_user_id = {u.user_id: u for u in users}
        conn = self._connect()
        try:
            raw = conn.read_block(CMD_ATTLOG_RRQ, FCT_ATTLOG)
        except WireError as exc:
            raise ESSLInvalidResponseError("could not read attendance block", details=str(exc)) from exc
        if not raw or len(raw) < 4:
            return []
        declared = int.from_bytes(raw[:4], "little")
        payload = raw[4:]
        record_size = declared // max(records, 1) if declared else 0
        if record_size not in (8, 16, 40):
            if record_size > 0 and len(payload) % record_size == 0:
                pass
            else:
                record_size = 16
        attendances: list[AttendanceRecord] = []
        while len(payload) >= record_size:
            record = payload[:record_size]
            payload = payload[record_size:]
            if record_size == 8:
                try:
                    uid, status, packed_time, punch = unpack("<HB4sB", record)
                except Exception:
                    continue
                resolved = by_uid.get(uid)
                user_id = resolved.user_id if resolved else str(uid)
                timestamp = decode_time4(packed_time)
                attendances.append(
                    AttendanceRecord(user_id=user_id, timestamp=timestamp, status=status, punch=punch, uid=uid)
                )
            elif record_size == 16:
                try:
                    user_id_int, packed_time, status, punch, _reserved, work_code = unpack("<I4sBB2sI", record)
                except Exception:
                    continue
                resolved = by_user_id.get(str(user_id_int))
                user_id = resolved.user_id if resolved else str(user_id_int)
                attendances.append(
                    AttendanceRecord(
                        user_id=user_id,
                        timestamp=decode_time4(packed_time),
                        status=status,
                        punch=punch,
                        uid=resolved.uid if resolved else int(user_id_int),
                        work_code=work_code,
                    )
                )
            else:  # legacy 40-byte format with free-form user id
                try:
                    uid, user_id_bytes, status, packed_time, punch, _space = unpack("<H24sB4sB8s", record)
                except Exception:
                    continue
                user_id = user_id_bytes.split(b"\x00")[0].decode("utf-8", "ignore")
                attendances.append(
                    AttendanceRecord(
                        user_id=user_id,
                        timestamp=decode_time4(packed_time),
                        status=status,
                        punch=punch,
                        uid=uid,
                    )
                )
        return attendances

    def clear_attendance(self) -> bool:
        conn = self._connect()
        if conn.command_ok(CMD_CLEAR_ATTLOG):
            return True
        raise ESSLInvalidResponseError("device refused to clear attendance")

    # -- adapter ---------------------------------------------------------------

    def read_transactions(
        self,
        from_: Optional[datetime] = None,
        to: Optional[datetime] = None,
        clear_after: Optional[bool] = None,
    ) -> list[ESSLTransaction]:
        """Pull attendance as normalized transactions, connecting as needed."""
        try:
            self._connect()
            try:
                self.enable_device()
            except ESSLInvalidResponseError:
                pass
            attendances = self.get_attendance()
            (self.clear_attendance() if (clear_after if clear_after is not None else self.clear_after_pull) else None)
            transactions: list[ESSLTransaction] = []
            for record in attendances:
                timestamp = record.timestamp
                if not timestamp.tzinfo:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                if from_ is not None and timestamp < from_:
                    continue
                if to is not None and timestamp > to:
                    continue
                transactions.append(
                    ESSLTransaction(
                        device_user_id=record.user_id,
                        timestamp=timestamp,
                        event_type=_event_type(record.punch, record.status),
                        raw={
                            "uid": record.uid,
                            "status": record.status,
                            "punch": record.punch,
                            "work_code": record.work_code,
                        },
                    )
                )
            transactions.sort(key=lambda t: t.timestamp)
            return transactions
        finally:
            self.disconnect()