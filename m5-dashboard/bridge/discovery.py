from __future__ import annotations

import socket
import threading
import time
from typing import Optional


DISCOVERY_QUERY = b"M5DASH_DISCOVER_V1"
DISCOVERY_RESPONSE_PREFIX = "M5DASH_BRIDGE_V1"
COMPLETION_EVENT_PREFIX = "M5DASH_EVENT_V1|completion|"
COMPLETION_EVENT_PORT = 42101


def build_discovery_response(http_port: int) -> bytes:
    if not 1 <= int(http_port) <= 65535:
        raise ValueError("invalid HTTP port")
    return ("%s|%d" % (DISCOVERY_RESPONSE_PREFIX, int(http_port))).encode("ascii")


def build_completion_event(provider: str) -> bytes:
    normalized = str(provider or "").lower()
    if normalized not in {"codex", "claude"}:
        raise ValueError("invalid completion provider")
    return (COMPLETION_EVENT_PREFIX + normalized).encode("ascii")


class CompletionBeacon:
    """Send content-free completion hints only to authenticated HTTP clients."""

    def __init__(self, port: int = COMPLETION_EVENT_PORT, client_ttl_seconds: int = 86400) -> None:
        self.port = int(port)
        self.client_ttl_seconds = max(60, int(client_ttl_seconds))
        self._lock = threading.Lock()
        self._clients: dict[str, float] = {}

    def note_client(self, address: str) -> None:
        if address in ("", "127.0.0.1", "::1"):
            return
        with self._lock:
            self._clients[str(address)] = time.monotonic()

    def notify(self, provider: str) -> int:
        payload = build_completion_event(provider)
        now = time.monotonic()
        with self._lock:
            active = [
                address
                for address, seen_at in self._clients.items()
                if now - seen_at <= self.client_ttl_seconds
            ]
            self._clients = {address: self._clients[address] for address in active}
        sent = 0
        if not active:
            return sent
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for address in active:
                try:
                    sock.sendto(payload, (address, self.port))
                    sent += 1
                except OSError:
                    continue
        finally:
            sock.close()
        return sent


class DiscoveryResponder(threading.Thread):
    """Advertise the bridge address without disclosing its API token."""

    daemon = True

    def __init__(self, bind: str, discovery_port: int, http_port: int) -> None:
        super().__init__(name="m5-dashboard-discovery")
        self.bind = "" if bind in ("", "0.0.0.0") else bind
        self.discovery_port = int(discovery_port)
        self.response = build_discovery_response(http_port)
        self._stop_event = threading.Event()
        self._socket: Optional[socket.socket] = None

    def stop(self) -> None:
        self._stop_event.set()
        sock = self._socket
        if sock:
            try:
                sock.close()
            except OSError:
                pass

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket = sock
        seen_clients: set[str] = set()
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind((self.bind, self.discovery_port))
            sock.settimeout(0.5)
            print("M5 discovery listening on UDP port %d" % self.discovery_port, flush=True)
            while not self._stop_event.is_set():
                try:
                    payload, address = sock.recvfrom(256)
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop_event.is_set():
                        break
                    raise
                if payload.strip() == DISCOVERY_QUERY:
                    if address[0] not in seen_clients:
                        seen_clients.add(address[0])
                        print("Dashboard discovery request from %s" % address[0], flush=True)
                    sock.sendto(self.response, address)
        finally:
            self._socket = None
            try:
                sock.close()
            except OSError:
                pass
