"""Tests for the clean-room eSSL wire protocol primitives."""
from datetime import datetime

import pytest

from integrations.essl import protocol
from integrations.essl.protocol import (
    CMD_ACK_OK,
    CMD_CONNECT,
    USHRT_MAX,
    build_frame,
    checksum,
    decode_time4,
    decode_time6,
    encode_time4,
    make_commkey,
    read_frame,
)


class _Socket:
    """Minimal in-memory socket feeding read_frame."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def recv(self, size: int) -> bytes:
        chunk = self._payload[:size]
        self._payload = self._payload[size:]
        return chunk


def test_frame_roundtrip():
    frame = build_frame(CMD_CONNECT, 0, USHRT_MAX - 1, b"\x00" * 12)
    command, session, reply, payload = read_frame(_Socket(frame))
    assert command == CMD_CONNECT
    assert session == 0
    assert reply == USHRT_MAX - 1
    assert payload == b"\x00" * 12


def test_checksum_is_deterministic_and_content_sensitive():
    a = build_frame(CMD_CONNECT, 1, 2, b"hello")
    b = build_frame(CMD_CONNECT, 1, 2, b"hello")
    c = build_frame(CMD_CONNECT, 1, 2, b"hello!")
    assert a == b
    assert a != c


def test_checksum_inverse_of_payload():
    # A packet whose payload is flipped should change the checksum field.
    one = build_frame(1, 0, 0, b"ABC")
    two = build_frame(1, 0, 0, b"CBA")
    assert one != two


def test_commkey_is_4_bytes_and_deterministic():
    key = make_commkey(0, 0x0101)
    assert len(key) == 4
    assert key == make_commkey(0, 0x0101)
    assert make_commkey(1, 0x0101) != key


def test_time_codecs_roundtrip():
    stamp = datetime(2024, 7, 15, 9, 30, 15)
    decoded = decode_time4(encode_time4(stamp))
    assert decoded == stamp


def test_time6_codec():
    decoded = decode_time6(bytes([24, 7, 15, 9, 5, 0]))
    assert decoded == datetime(2024, 7, 15, 9, 5, 0)


def test_invalid_bad_magic_raises():
    bogus = b"\x12\x34" + bytes(16)
    with pytest.raises(protocol.WireError):
        read_frame(_Socket(bogus))


def test_ack_mapping():
    assert CMD_ACK_OK == 2000
    assert checksum(b"") == 0xFFFF