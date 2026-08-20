from __future__ import annotations

import socket
import threading
from typing import Optional


DISCOVERY_QUERY = b"M5DASH_DISCOVER_V1"
DISCOVERY_RESPONSE_PREFIX = "M5DASH_BRIDGE_V1"


def build_discovery_response(http_port: int) -> bytes:
    if not 1 <= int(http_port) <= 65535:
        raise ValueError("invalid HTTP port")
    return ("%s|%d" % (DISCOVERY_RESPONSE_PREFIX, int(http_port))).encode("ascii")


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
