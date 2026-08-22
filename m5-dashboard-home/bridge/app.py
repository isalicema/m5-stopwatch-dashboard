from __future__ import annotations

import argparse
import hmac
import json
import signal
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .claude_client import ClaudeMonitor
from .codex_client import CodexMonitor
from .discovery import DiscoveryResponder
from .state import DashboardState
from .usb_serial import UsbSerialResponder
from .weather import WeatherMonitor


def load_config(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("config root must be an object")
    server = value.get("server") or {}
    if not server.get("api_token") or server.get("api_token") == "CHANGE_ME_TO_A_LONG_RANDOM_VALUE":
        raise ValueError("set server.api_token in config.json before starting")
    return value


def build_handler(state: DashboardState, api_token: str) -> type[BaseHTTPRequestHandler]:
    seen_clients: set[str] = set()

    class Handler(BaseHTTPRequestHandler):
        server_version = "M5Dashboard/0.1"

        def _json(self, status: int, body: Dict[str, Any]) -> None:
            raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/healthz":
                self._json(HTTPStatus.OK, {"ok": True})
                return
            if path != "/api/state":
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
                return
            supplied = self.headers.get("X-Dashboard-Token", "")
            if not hmac.compare_digest(supplied, api_token):
                self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            client_ip = self.client_address[0]
            if client_ip not in ("127.0.0.1", "::1") and client_ip not in seen_clients:
                seen_clients.add(client_ip)
                print("Dashboard client connected: %s" % client_ip, flush=True)
            self._json(HTTPStatus.OK, state.snapshot())

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Codex + Claude companion bridge for M5Stack StopWatch")
    parser.add_argument("--config", default="config.json", help="path to config.json")
    args = parser.parse_args(argv)
    config = load_config(Path(args.config).expanduser().resolve())
    codex_config = config.get("codex") or {}
    claude_config = config.get("claude") or {}
    weather_config = config.get("weather") or {}
    dashboard = DashboardState()
    workers: list[Any] = []

    if codex_config.get("enabled", True):
        monitor = CodexMonitor(codex_config, dashboard.set_codex)
        monitor.start()
        workers.append(monitor)
    if claude_config.get("enabled", False):
        monitor = ClaudeMonitor(claude_config, dashboard.set_claude)
        monitor.start()
        workers.append(monitor)
    if weather_config.get("enabled", True):
        monitor = WeatherMonitor(weather_config, dashboard.set_weather)
        monitor.start()
        workers.append(monitor)

    server_config = config["server"]
    server = ThreadingHTTPServer(
        (str(server_config.get("bind") or "0.0.0.0"), int(server_config.get("port", 8765))),
        build_handler(dashboard, str(server_config["api_token"])),
    )
    discovery = DiscoveryResponder(
        str(server_config.get("bind") or "0.0.0.0"),
        int(server_config.get("discovery_port", 8766)),
        int(server.server_address[1]),
    )
    discovery.start()
    workers.append(discovery)
    usb = UsbSerialResponder(dashboard.snapshot, str(server_config["api_token"]))
    usb.start()
    workers.append(usb)
    stopped = threading.Event()

    def shutdown(*_: Any) -> None:
        if stopped.is_set():
            return
        stopped.set()
        for worker in workers:
            worker.stop()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        print("M5 Dashboard listening on http://%s:%d" % server.server_address, flush=True)
        server.serve_forever(poll_interval=0.5)
    finally:
        shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
