from __future__ import annotations

import json
import os
import socket
import ssl
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple


def _encode_remaining_length(length: int) -> bytes:
    encoded = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length:
            digit |= 0x80
        encoded.append(digit)
        if not length:
            return bytes(encoded)


def _utf8(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("!H", len(raw)) + raw


def _packet(first_byte: int, body: bytes = b"") -> bytes:
    return bytes((first_byte,)) + _encode_remaining_length(len(body)) + body


def build_connect(client_id: str, username: str, password: str, keepalive: int = 30) -> bytes:
    variable = _utf8("MQTT") + bytes((4, 0xC2)) + struct.pack("!H", keepalive)
    payload = _utf8(client_id) + _utf8(username) + _utf8(password)
    return _packet(0x10, variable + payload)


def build_subscribe(topic: str, packet_id: int = 1) -> bytes:
    return _packet(0x82, struct.pack("!H", packet_id) + _utf8(topic) + b"\x00")


def build_publish(topic: str, payload: bytes) -> bytes:
    return _packet(0x30, _utf8(topic) + payload)


def _read_exact(sock: ssl.SSLSocket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("MQTT socket closed")
        chunks.extend(chunk)
    return bytes(chunks)


def read_packet(sock: ssl.SSLSocket) -> Tuple[int, int, bytes]:
    first = _read_exact(sock, 1)[0]
    multiplier = 1
    remaining = 0
    for _ in range(4):
        digit = _read_exact(sock, 1)[0]
        remaining += (digit & 127) * multiplier
        if not digit & 128:
            break
        multiplier *= 128
    else:
        raise ValueError("invalid MQTT remaining length")
    return first >> 4, first & 0x0F, _read_exact(sock, remaining)


def parse_publish(flags: int, body: bytes) -> Tuple[str, bytes]:
    if len(body) < 2:
        raise ValueError("short MQTT PUBLISH")
    topic_len = struct.unpack("!H", body[:2])[0]
    offset = 2 + topic_len
    topic = body[2:offset].decode("utf-8", errors="replace")
    qos = (flags >> 1) & 0x03
    if qos:
        offset += 2
    return topic, body[offset:]


def resolve_connection(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve LAN or cloud settings without putting cloud tokens in config.json."""
    values = dict(config)
    credential_path = str(config.get("credentials_file") or "")
    if credential_path:
        path = Path(os.path.expanduser(credential_path))
        try:
            credentials = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError("cannot read Bambu credentials file: %s" % path) from exc
        except json.JSONDecodeError as exc:
            raise ValueError("invalid Bambu credentials file: %s" % path) from exc
        if not isinstance(credentials, dict):
            raise ValueError("Bambu credentials file must contain an object")
        values.update(credentials)

    mode = str(values.get("mode") or "lan").lower()
    serial = str(values.get("serial") or "").strip()
    if not serial:
        raise ValueError("Bambu printer serial is missing")
    if mode == "cloud":
        region = str(values.get("region") or "global").lower()
        host = "cn.mqtt.bambulab.com" if region == "cn" else "us.mqtt.bambulab.com"
        user_id = str(values.get("user_id") or "").strip()
        if user_id and not user_id.startswith("u_"):
            user_id = "u_" + user_id
        token = str(values.get("access_token") or "")
        if not user_id or not token:
            raise ValueError("Bambu cloud user_id or access_token is missing")
        return {
            "mode": "cloud",
            "host": str(values.get("host") or host),
            "port": int(values.get("port", 8883)),
            "username": user_id,
            "password": token,
            "serial": serial,
            "verify_tls": True,
            "ca_file": str(values.get("ca_file") or ""),
            "full_refresh_seconds": max(300, int(values.get("full_refresh_seconds", 300))),
        }
    if mode != "lan":
        raise ValueError("Bambu mode must be 'lan' or 'cloud'")
    access_code = str(values.get("access_code") or "")
    if not access_code:
        raise ValueError("Bambu LAN access_code is missing")
    return {
        "mode": "lan",
        "host": str(values.get("host") or ""),
        "port": int(values.get("port", 8883)),
        "username": "bblp",
        "password": access_code,
        "serial": serial,
        "verify_tls": bool(values.get("verify_tls", False)),
        "ca_file": str(values.get("ca_file") or ""),
        "full_refresh_seconds": max(10, int(values.get("full_refresh_seconds", 30))),
    }


class BambuMonitor(threading.Thread):
    daemon = True

    def __init__(
        self,
        config: Dict[str, Any],
        on_report: Callable[[Dict[str, Any]], None],
        on_connection: Callable[[bool], None],
    ) -> None:
        super().__init__(name="bambu-monitor")
        self.config = config
        self.on_report = on_report
        self.on_connection = on_connection
        self._stop_event = threading.Event()
        self._sock: Optional[ssl.SSLSocket] = None
        self._connection: Optional[Dict[str, Any]] = None

    def stop(self) -> None:
        self._stop_event.set()
        sock = self._sock
        if sock:
            try:
                sock.close()
            except OSError:
                pass

    def _tls_context(self, connection: Dict[str, Any]) -> ssl.SSLContext:
        if connection.get("verify_tls"):
            cafile = connection.get("ca_file") or None
            return ssl.create_default_context(cafile=cafile)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def _connect(self) -> ssl.SSLSocket:
        connection = resolve_connection(self.config)
        self._connection = connection
        host = str(connection["host"])
        port = int(connection["port"])
        raw = socket.create_connection((host, port), timeout=8)
        raw.settimeout(2)
        sock = self._tls_context(connection).wrap_socket(raw, server_hostname=host)
        client_id = "m5dash-%x" % int(time.time())
        sock.sendall(
            build_connect(client_id, str(connection["username"]), str(connection["password"]))
        )
        packet_type, _, body = read_packet(sock)
        if packet_type != 2 or len(body) != 2 or body[1] != 0:
            reason = body[1] if len(body) == 2 else -1
            raise ConnectionError("Bambu MQTT rejected connection (code %s)" % reason)
        serial = str(connection["serial"])
        sock.sendall(build_subscribe("device/%s/report" % serial))
        packet_type, _, body = read_packet(sock)
        if packet_type != 9 or len(body) < 3 or body[2] == 0x80:
            raise ConnectionError("Bambu MQTT subscription was rejected")
        self._sock = sock
        self.on_connection(True)
        return sock

    def _request_full(self, sock: ssl.SSLSocket) -> None:
        if not self._connection:
            return
        serial = str(self._connection["serial"])
        request = {
            "pushing": {
                "sequence_id": str(int(time.time())),
                "command": "pushall",
                "version": 1,
                "push_target": 1,
            }
        }
        payload = json.dumps(request, separators=(",", ":")).encode("utf-8")
        sock.sendall(build_publish("device/%s/request" % serial, payload))

    def _session(self) -> None:
        sock = self._connect()
        if not self._connection:
            raise ConnectionError("Bambu connection settings were not resolved")
        refresh = int(self._connection["full_refresh_seconds"])
        self._request_full(sock)
        last_full = time.monotonic()
        last_ping = time.monotonic()
        while not self._stop_event.is_set():
            now = time.monotonic()
            if now - last_full >= refresh:
                self._request_full(sock)
                last_full = now
            if now - last_ping >= 20:
                sock.sendall(b"\xC0\x00")
                last_ping = now
            try:
                packet_type, flags, body = read_packet(sock)
            except socket.timeout:
                continue
            if packet_type != 3:
                continue
            _, payload = parse_publish(flags, body)
            try:
                report = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(report, dict):
                self.on_report(report)

    def run(self) -> None:
        delay = 1
        while not self._stop_event.is_set():
            try:
                self._session()
                delay = 1
            except (OSError, ValueError, ConnectionError, ssl.SSLError) as exc:
                self.on_connection(False)
                self._sock = None
                print("Bambu monitor: %s" % exc, file=sys.stderr, flush=True)
                self._stop_event.wait(delay)
                delay = min(delay * 2, 30)
        self.on_connection(False)
