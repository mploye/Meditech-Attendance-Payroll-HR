"""eSSL/ZKTeco standalone device wire protocol (clean-room implementation).

Implements the TCP "TOP" framing used by eSSL/ZKTeco standalone terminals
(referenced by the official "Communication Protocol SDK" manual, v6.3.x):
command codes, packet layout, checksum and the commkey scramble are public
protocol facts described in the vendor documentation.

Packet layout (little-endian throughout):

    TCP frame: 8-byte TOP header + inner packet
        TOP  : <HHI>  magic1=0x5050, magic2=0x7282, inner_length
        inner: <4H>   command, checksum, session_id, reply_id
               then <I> payload_length followed by payload bytes.

The checksum covers the inner header (checksum field zeroed) plus the
payload, summed as 16-bit little-endian words folded at 0xFFFF then
inverted (ones-complement residue).
"""

from __future__ import annotations

import socket
from datetime import datetime
from struct import pack, unpack
from typing import Optional, Tuple

# --- Command codes (from the eSSL SDK manual command list) -------------------
CMD_CONNECT = 1000
CMD_EXIT = 1001
CMD_ENABLEDEVICE = 1002
CMD_DISABLEDEVICE = 1003
CMD_RESTART = 1004
CMD_POWEROFF = 1005
CMD_REFRESHDATA = 1013
CMD_GET_VERSION = 1100
CMD_AUTH = 1102
CMD_PREPARE_DATA = 1500
CMD_DATA = 1501
CMD_FREE_DATA = 1502
CMD_RWB = 1503
CMD_RDB = 1504
CMD_ACK_OK = 2000
CMD_ACK_ERROR = 2001
CMD_ACK_DATA = 2002
CMD_ACK_UNAUTH = 2005
CMD_UNKNOWN = 0xFFFF

# --- Data read commands ------------------------------------------------------
CMD_GET_FREE_SIZES = 50
CMD_ATTLOG_RRQ = 13
CMD_CLEAR_ATTLOG = 15
CMD_USER_RRQ = 5
CMD_USERTEMP_RRQ = 9
CMD_DELETE_USER = 18

# --- Data field types used by CMD_PREPARE_DATA / CMD_RWB ---------------------
FCT_ATTLOG = 1
FCT_FINGERTMP = 2
FCT_USER = 5
FCT_OPLOG = 4
FCT_WORKCODE = 8

# --- Framing constants -------------------------------------------------------
MAGIC_PREPARE_DATA_1 = 0x5050
MAGIC_PREPARE_DATA_2 = 0x7282
USHRT_MAX = 65535

# The user packet sizes supported by firmware generations
USER_SIZE_ZK6 = 28
USER_SIZE_ZK8 = 72


class WireError(Exception):
    """Raised when a frame cannot be read or is malformed."""


class WireTimeoutError(WireError):
    """Raised when a peer does not answer within the socket timeout."""


# --- Packet building / parsing ------------------------------------------------

def _s16(total: int) -> int:
    return (total & 0xFFFF) | (-0x10000 if total & 0x8000 else 0)


def checksum(*contents: bytes) -> int:
    """Compute the 16-bit ones-complement checksum of concatenated content."""
    data = b"".join(contents)
    if len(data) & 1:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        total += data[i] | (data[i + 1] << 8)
        if total > USHRT_MAX:
            total -= USHRT_MAX
    return (~total) & USHRT_MAX


def build_inner(command: int, session_id: int, reply_id: int, payload: bytes = b"") -> bytes:
    """Build the inner packet: 8-byte header (command, checksum, session, reply)
    followed by the payload."""
    header_without_checksum = pack("<4H", command, 0, session_id & 0xFFFF, reply_id & 0xFFFF)
    ck = checksum(header_without_checksum, payload)
    return pack("<4H", command, ck, session_id & 0xFFFF, reply_id & 0xFFFF) + payload


def build_frame(command: int, session_id: int, reply_id: int, payload: bytes = b"") -> bytes:
    """Wrap an inner packet in the 8-byte TCP TOP header."""
    inner = build_inner(command, session_id, reply_id, payload)
    return pack("<HHI", MAGIC_PREPARE_DATA_1, MAGIC_PREPARE_DATA_2, len(inner)) + inner


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise WireError("connection closed while reading frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(sock: socket.socket) -> Tuple[int, int, int, bytes]:
    """Read one complete TCP frame and return (command, session_id, reply_id, payload)."""
    try:
        top = _recv_exact(sock, 8)
    except socket.timeout as exc:
        raise WireTimeoutError("timed out waiting for device response") from exc
    magic1, magic2, inner_length = unpack("<HHI", top)
    if magic1 != MAGIC_PREPARE_DATA_1 or magic2 != MAGIC_PREPARE_DATA_2:
        raise WireError(f"bad TOP header magic {magic1:#06x},{magic2:#06x}")
    inner = _recv_exact(sock, inner_length)
    if len(inner) < 8:
        raise WireError("frame too short")
    command, _ck, session_id, reply_id = unpack("<4H", inner[:8])
    return command, session_id, reply_id, inner[8:]


# --- CommKey scramble (public algorithm from eSSL commpro.c MakeKey) ----------

def make_commkey(password: int, session_id: int, ticks: int = 50) -> bytes:
    """Derive the authentication key from the device password and session id."""
    key = int(password) & 0xFFFFFFFF
    session = int(session_id) & 0xFFFFFFFF
    scrambled = 0
    for i in range(32):
        scrambled = (scrambled << 1) | (1 if (key & (1 << i)) else 0)
    scrambled += session
    k = bytearray(scrambled.to_bytes(4, "little"))
    k[0] ^= ord("Z")
    k[1] ^= ord("K")
    k[2] ^= ord("S")
    k[3] ^= ord("O")
    word0 = k[0] | (k[1] << 8)
    word1 = k[2] | (k[3] << 8)
    swapped = (word1 << 16) | word0
    k = bytearray(swapped.to_bytes(4, "little"))
    b = ticks & 0xFF
    k[0] ^= b
    k[1] ^= b
    k[2] = b
    k[3] ^= b
    return bytes(k)


# --- Time codecs ----------------------------------------------------------------

def decode_time4(raw: bytes) -> datetime:
    """Decode the 32-bit packed timestamp found in attendance/user records."""
    value = int.from_bytes(raw[:4], "little")
    second = value % 60
    value //= 60
    minute = value % 60
    value //= 60
    hour = value % 24
    value //= 24
    day = value % 31 + 1
    value //= 31
    month = value % 12 + 1
    value //= 12
    year = value + 2000
    return datetime(year, month, day, hour, minute, second)


def encode_time4(dt: datetime) -> bytes:
    """Encode a datetime to the 32-bit packed timestamp used by the device."""
    value = (
        (((dt.year % 100) * 12 * 31 + (dt.month - 1) * 31 + dt.day - 1) * 86400)
        + (dt.hour * 60 + dt.minute) * 60
        + dt.second
    )
    return value.to_bytes(4, "little")


def decode_time6(raw: bytes) -> datetime:
    """Decode the 6-byte (Y M D H M S) timestamp used in real-time events."""
    year, month, day, hour, minute, second = unpack("6B", raw[:6])
    return datetime(2000 + year, month, day, hour, minute, second)


# --- Reusable connection state machine ------------------------------------------

class ZKConnection:
    """Owns a socket connection to a device and speaks the framed protocol."""

    def __init__(self, host: str, port: int = 4370, timeout: float = 10.0, password: int = 0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.password = int(password)
        self._sock: Optional[socket.socket] = None
        self._session_id = 0
        self._reply_id = USHRT_MAX - 1
        self.is_connected = False

    @property
    def session_id(self) -> int:
        return self._session_id

    @property
    def reply_id(self) -> int:
        return self._reply_id

    def _open(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
        except OSError as exc:
            sock.close()
            raise WireError(f"cannot connect to {self.host}:{self.port}: {exc}") from exc
        self._sock = sock

    def connect(self) -> None:
        """Perform the session handshake and (if required) authentication."""
        if self.is_connected:
            return
        if self._sock is None:
            self._open()
        try:
            command, session_id, _reply, _payload = self.send_command(CMD_CONNECT)
            if command == CMD_ACK_UNAUTH:
                command, session_id, _reply, _payload = self.send_command(
                    CMD_AUTH, make_commkey(self.password, session_id)
                )
            if command != CMD_ACK_OK:
                raise WireError(f"connect rejected by device (code {command})")
            self._session_id = session_id
            self.is_connected = True
        except Exception:
            self._close()
            raise

    def send_command(self, command: int, payload: bytes = b"") -> Tuple[int, int, int, bytes]:
        """Send a framed command and return (response_code, session, reply, payload)."""
        if self._sock is None:
            raise WireError("not connected")
        frame = build_frame(command, self._session_id, self._reply_id, payload)
        try:
            self._sock.sendall(frame)
            response_code, session_id, reply_id, data = read_frame(self._sock)
        except (OSError, socket.timeout) as exc:
            raise WireError(str(exc)) from exc
        self._session_id = session_id
        self._reply_id = (reply_id + 1) % USHRT_MAX
        return response_code, session_id, reply_id, data

    def command_ok(self, command: int, payload: bytes = b"") -> bool:
        """Send a command and return whether the device answered CMD_ACK_OK."""
        code, _session, _reply, _data = self.send_command(command, payload)
        return code == CMD_ACK_OK

    def read_block(self, read_command: int, fct: int = 0, ext: int = 0) -> bytes:
        """Fetch a data block from the device using the buffered read (CMD_RWB).

        Devices supporting CMD_RWB answer directly with CMD_DATA; older units
        answer CMD_PREPARE_DATA with a size and are then drained through
        CMD_RDB chunks followed by CMD_FREE_DATA.
        """
        code, _session, _reply, data = self.send_command(CMD_RWB, pack("<bhii", 1, read_command, fct, ext))
        if code == CMD_DATA:
            return data
        if code != CMD_PREPARE_DATA:
            raise WireError(f"device refused data block (code {code})")
        size = int.from_bytes(data[:4], "little")
        chunks = bytearray()
        start = 0
        while size > 0:
            chunk_size = min(size, 0xFFC0)
            c2, _s, _r, chunk = self.send_command(CMD_RDB, pack("<ii", start, chunk_size))
            if c2 != CMD_DATA:
                break
            chunks += chunk
            start += len(chunk)
            size -= len(chunk)
        self.send_command(CMD_FREE_DATA)
        return bytes(chunks)

    def close(self) -> None:
        self._close()

    def _close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self.is_connected = False

    def __enter__(self) -> "ZKConnection":
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()