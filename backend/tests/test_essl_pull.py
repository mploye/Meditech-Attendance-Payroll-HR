"""End-to-end tests for the clean-room pull client against a fake terminal."""
from datetime import datetime, timedelta, timezone

import pytest

from integrations.essl.pulldevice import ZKDevice
from models.device import Device, ESSLConfig
from models.enums import DeviceProvider, DeviceStatus, EventType
from tests.conftest import make_company
from tests.fake_zk_device import FakeZKDeviceServer, running_fake_device

HOST = "127.0.0.1"
TZ = timezone.utc

USERS = [
    {"uid": 1, "user_id": 1001, "name": "Alice", "privilege": 0, "card": 0},
    {"uid": 2, "user_id": 1002, "name": "Bob", "privilege": 0, "card": 0},
]

RECORDS_16 = [
    {"user_id": 1001, "timestamp": datetime(2024, 7, 15, 9, 5, 0, tzinfo=TZ), "punch": 0, "status": 0},
    {"user_id": 1002, "timestamp": datetime(2024, 7, 15, 9, 10, 0, tzinfo=TZ), "punch": 0, "status": 0},
    {"user_id": 1001, "timestamp": datetime(2024, 7, 15, 18, 2, 0, tzinfo=TZ), "punch": 1, "status": 0},
]


def _device_row(db, company_id, ip=HOST, port=4370, protocol="zk"):
    device = Device(
        company_id=company_id,
        name="Front Door",
        serial_number="ZX628011",
        provider=DeviceProvider.ESSL,
        status=DeviceStatus.ONLINE,
        ip_address=ip,
        port=port,
        protocol=protocol,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _essl_config(db, company_id):
    cfg = ESSLConfig(company_id=company_id, enabled=True, timeout_sec=5)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def test_zkdevice_reads_users_and_attendance_with_filter():
    with running_fake_device(users=USERS, records=RECORDS_16, record_size=16) as (host, port):
        device = ZKDevice(host, port, timeout=5)
        users = device.get_users()
        assert len(users) == 2
        assert {u.user_id for u in users} == {"1001", "1002"}
        assert users[0].name == "Alice"

        tx = device.read_transactions()
        assert len(tx) == 3
        in_events = [t for t in tx if t.event_type == EventType.IN]
        out_events = [t for t in tx if t.event_type == EventType.OUT]
        assert len(in_events) == 2
        assert len(out_events) == 1
        assert out_events[0].device_user_id == "1001"


def test_read_transactions_respects_window():
    with running_fake_device(users=USERS, records=RECORDS_16, record_size=16) as (host, port):
        device = ZKDevice(host, port, timeout=5)
        from_ = datetime(2024, 7, 15, 10, 0, tzinfo=TZ)
        to = datetime(2024, 7, 16, 0, 0, tzinfo=TZ)
        tx = device.read_transactions(from_, to)
        assert len(tx) == 1
        assert tx[0].device_user_id == "1001"
        assert tx[0].event_type == EventType.OUT


def test_unknown_punch_maps_to_unknown_event():
    records = [{"user_id": 1001, "timestamp": datetime(2024, 7, 15, 9, 5, 0, tzinfo=TZ), "punch": 255, "status": 0}]
    with running_fake_device(users=USERS, records=records, record_size=16) as (host, port):
        device = ZKDevice(host, port, timeout=5)
        tx = device.read_transactions()
        assert tx[0].event_type == EventType.UNKNOWN


def test_clear_after_pull_empties_terminal():
    with running_fake_device(users=USERS, records=RECORDS_16, record_size=16) as (host, port):
        device = ZKDevice(host, port, timeout=5, clear_after_pull=True)
        assert len(device.read_transactions()) == 3
        assert len(device.get_attendance()) == 0


def test_legacy_40byte_records_parse():
    records = [
        {"uid": 1, "user_id": "E001", "timestamp": datetime(2024, 7, 15, 9, 5, 0, tzinfo=TZ), "punch": 0, "status": 0},
        {"uid": 1, "user_id": "E001", "timestamp": datetime(2024, 7, 15, 18, 2, 0, tzinfo=TZ), "punch": 1, "status": 0},
    ]
    with running_fake_device(users=(), records=records, record_size=40, user_packet_size=28) as (host, port):
        device = ZKDevice(host, port, timeout=5)
        tx = device.read_transactions()
        assert len(tx) == 2
        assert {t.device_user_id for t in tx} == {"E001"}


def test_essl_service_pull_transactions_uses_ip_branch(db):
    company = make_company(db)
    _essl_config(db, str(company.id))
    with running_fake_device(users=USERS, records=RECORDS_16, record_size=16) as (host, port):
        device_row = _device_row(db, str(company.id), ip=host, port=port, protocol="zk")

        from integrations.essl.config import ESSLConfiguration
        from integrations.essl.service import ESSLService

        service = ESSLService(db=db, config=ESSLConfiguration.from_settings(), mock_override=False)
        tx = asyncio_run(
            service.pull_transactions(company, device_row, datetime(2024, 7, 15, 0, 0, tzinfo=TZ), datetime(2024, 7, 16, 0, 0, tzinfo=TZ))
        )
        assert len(tx) == 3


def test_essl_service_http_protocol_falls_back_to_client(db):
    import asyncio

    from integrations.essl.config import ESSLConfiguration
    from integrations.essl.mock import MockESSLClient
    from integrations.essl.service import ESSLService

    company = make_company(db)
    _essl_config(db, str(company.id))
    device_row = _device_row(db, str(company.id), protocol="http")

    mock = MockESSLClient(ESSLConfiguration.from_settings())
    mock.generate_transaction(
        "D123", datetime(2024, 7, 15, 9, 30, 0, tzinfo=TZ), "IN"
    )
    service = ESSLService(db=db, config=ESSLConfiguration.from_settings(), client=mock, mock_override=False)
    tx = asyncio.run(
        service.pull_transactions(company, device_row, datetime(2024, 7, 15, 0, 0, tzinfo=TZ), datetime(2024, 7, 16, 0, 0, tzinfo=TZ))
    )
    assert len(tx) == 1
    assert tx[0].device_user_id == "D123"


def test_device_service_pull_connection_test(db):
    from services import device_service

    company = make_company(db)
    _essl_config(db, str(company.id))
    with running_fake_device(users=USERS, records=(), record_size=16) as (host, port):
        device_row = _device_row(db, str(company.id), ip=host, port=port, protocol="zk")
        result = device_service.test_device_connection(db, device_row)
        assert result.get("success") is True
        assert result.get("status") == "CONNECTED"


def test_device_service_pull_connection_failure(db):
    from services import device_service

    company = make_company(db)
    _essl_config(db, str(company.id))
    # Port 1 refuses connections; probe should fail cleanly.
    device_row = _device_row(db, str(company.id), ip=HOST, port=1, protocol="zk")
    result = device_service.test_device_connection(db, device_row)
    assert result.get("success") is False


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)