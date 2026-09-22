"""In-memory fake of an eSSL/ZKTeco standalone terminal speaking the TOP protocol.

Used by the pull-client tests to exercise the full wire round-trip without
hardware: session handshake, capacity reads, buffered user/attendance blocks
and clear commands. The frame building/parsing helpers come from the same
:mod:`integrations.essl.protocol` module the client uses, so the fake and the
client agree on the exact wire format.
"""

import contextlib
import socket
import threading

from integrations.essl.protocol import (
    CMD_ACK_ERROR,
    CMD_ACK_OK,
    CMD_ATTLOG_RRQ,
    CMD_AUTH,
    CMD_CLEAR_ATTLOG,
    CMD_CONNECT,
    CMD_DATA,
    CMD_DISABLEDEVICE,
    CMD_ENABLEDEVICE,
    CMD_EXIT,
    CMD_GET_FREE_SIZES,
    CMD_RWB,
    CMD_USERTEMP_RRQ,
    FCT_ATTLOG,
    FCT_USER,
    USER_SIZE_ZK6,
    build_frame,
    encode_time4,
    pack,
    read_frame,
)


class FakeZKDeviceServer:
    """Accept a single connection and answer framed protocol requests."""

    def __init__(
        self,
        users=(),
        records=(),
        user_packet_size=USER_SIZE_ZK6,
        record_size=16,
        host="127.0.0.1",
    ) -> None:
        self.host = host
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self.users = list(users)
        self.records = list(records)
        self.user_packet_size = user_packet_size
        self.record_size = record_size
        self.session = 0
        self._stop = False
        self._thread = threading.Thread(target=self._serve, daemon=True)

    @property
    def address(self):
        return (self.host, self.port)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop = True
        try:
            self._sock.close()
        except OSError:
            pass

    # ------------------------------------------------------------------ serve

    def _serve(self):
        conn = None
        try:
            while not self._stop:
                conn, _addr = self._sock.accept()
                conn.settimeout(15)
                self._handle_connection(conn)
                conn.close()
                conn = None
        except OSError:
            pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass

    def _handle_connection(self, conn):
        while not self._stop:
            try:
                command, session, reply, payload = read_frame(conn)
            except Exception:
                return
            response = self._respond(command, session, reply, payload)
            if response is None:
                return
            try:
                conn.sendall(response)
            except OSError:
                return

    # -------------------------------------------------------------- responses

    def _respond(self, command, session, reply, payload):
        if command == CMD_CONNECT:
            self.session = 0x0101
            return build_frame(CMD_ACK_OK, self.session, reply, b"\x00" * 12)
        if command == CMD_AUTH:
            return build_frame(CMD_ACK_OK, self.session, reply, b"")
        if command in (CMD_ENABLEDEVICE, CMD_DISABLEDEVICE):
            return build_frame(CMD_ACK_OK, self.session, reply, b"")
        if command == CMD_EXIT:
            return build_frame(CMD_ACK_OK, self.session, reply, b"")
        if command == CMD_CLEAR_ATTLOG:
            self.records = []
            return build_frame(CMD_ACK_OK, self.session, reply, b"")
        if command == CMD_GET_FREE_SIZES:
            return build_frame(CMD_ACK_OK, self.session, reply, self._sizes_payload())
        if command == CMD_RWB:
            return self._respond_rw_buffered(payload, reply)
        return build_frame(CMD_ACK_ERROR, self.session, reply, b"")

    def _respond_rw_buffered(self, payload, reply):
        if len(payload) < 10:
            return build_frame(CMD_ACK_ERROR, self.session, reply, b"")
        _version, read_command, fct, _ext = __import__("struct").unpack("<bhii", payload)
        if read_command == CMD_USERTEMP_RRQ and fct == FCT_USER:
            block = self._users_block()
        elif read_command == CMD_ATTLOG_RRQ and fct == FCT_ATTLOG:
            block = self._attendance_block()
        else:
            return build_frame(CMD_ACK_ERROR, self.session, reply, b"")
        return build_frame(CMD_DATA, self.session, reply, block)

    # ----------------------------------------------------------------- block

    def _users_block(self):
        records = bytearray()
        for user in self.users:
            password = user.get("password", "").encode("utf-8")[:5].ljust(5, b"\x00")
            name = user.get("name", "").encode("utf-8")[:8].ljust(8, b"\x00")
            if self.user_packet_size == USER_SIZE_ZK6:
                records += pack(
                    "<HB5s8sIxBhI",
                    user["uid"],
                    user.get("privilege", 0),
                    password,
                    name,
                    user.get("card", 0),
                    user.get("group_id", 0),
                    0,
                    user["user_id"],
                )
            else:
                group = str(user.get("group_id", "")).encode("utf-8")[:7].ljust(7, b"\x00")
                uid_bytes = str(user["user_id"]).encode("utf-8")[:24].ljust(24, b"\x00")
                records += pack(
                    "<HB8s24sIx7sx24s",
                    user["uid"],
                    user.get("privilege", 0),
                    password,
                    name,
                    user.get("card", 0),
                    group,
                    uid_bytes,
                )
        return len(records).to_bytes(4, "little") + bytes(records)

    def _attendance_block(self):
        records = bytearray()
        for record in self.records:
            packed_time = encode_time4(record["timestamp"])
            if self.record_size == 8:
                records += pack(
                    "<HB4sB",
                    record["uid"],
                    record.get("status", 0),
                    packed_time,
                    record.get("punch", 0),
                )
            elif self.record_size == 40:
                user_id_bytes = str(record.get("user_id", record["uid"])).encode("utf-8")[:24].ljust(24, b"\x00")
                records += pack(
                    "<H24sB4sB8s",
                    record["uid"],
                    user_id_bytes,
                    record.get("status", 0),
                    packed_time,
                    record.get("punch", 0),
                    b"\x00" * 8,
                )
            else:
                records += pack(
                    "<I4sBB2sI",
                    record["user_id"],
                    packed_time,
                    record.get("status", 0),
                    record.get("punch", 0),
                    b"\x00\x00",
                    record.get("work_code", 0),
                )
        return len(records).to_bytes(4, "little") + bytes(records)

    def _sizes_payload(self):
        values = [0] * 20
        values[4] = len(self.users)
        values[6] = 0
        values[8] = len(self.records)
        values[10] = 0
        return pack("20i", *values)


@contextlib.contextmanager
def running_fake_device(users=(), records=(), **kwargs):
    """Start a fake terminal and yield (host, port), stopping it afterwards."""
    server = FakeZKDeviceServer(users=users, records=records, **kwargs)
    server.start()
    try:
        yield (server.host, server.port)
    finally:
        server.stop()