from __future__ import annotations

import argparse
import hmac
import json
import signal
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

from .ai_hotspots import AIHotspotMonitor
from .ai_usage_client import AIUsageMonitor
from .claude_client import ClaudeMonitor
from .codex_client import CodexMonitor
from .discovery import DiscoveryResponder
from .obsidian_dice import ObsidianDice
from .peer_state import PeerStateMonitor, resolve_peer_auth
from .state import DashboardState
from .ticktick_client import ACTIONS, TickTickMonitor
from .typeless_client import TypelessController
from .usb_serial import UsbSerialResponder, UsbSnapshotSource
from .weather import WeatherMonitor


EXTRA_ACTION_ROUTES = {
    "/api/ai/ack": "ai-ack",
    "/api/ai/open": "ai-open",
    "/api/obsidian/roll": "obsidian-roll",
    "/api/obsidian/open": "obsidian-open",
    "/api/typeless/start": "typeless-start",
    "/api/typeless/stop": "typeless-stop",
}


def load_config(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("config root must be an object")
    server = value.get("server") or {}
    if not server.get("api_token") or server.get("api_token") == "CHANGE_ME_TO_A_LONG_RANDOM_VALUE":
        raise ValueError("set server.api_token in config.json before starting")
    return value


def dispatch_ticktick_action(
    path: str,
    supplied_token: str,
    api_token: str,
    action_callback: Optional[Callable[[str], Dict[str, Any]]],
) -> tuple[int, Dict[str, Any]]:
    if not hmac.compare_digest(supplied_token, api_token):
        return HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"}
    action = path.removeprefix("/api/ticktick/") if path.startswith("/api/ticktick/") else ""
    if action not in ACTIONS or action_callback is None:
        return HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"}
    try:
        action_callback(action)
        return HTTPStatus.OK, {"ok": True}
    except (OSError, ValueError) as exc:
        return HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)}


def dispatch_dashboard_action(
    path: str,
    supplied_token: str,
    api_token: str,
    action_callbacks: Dict[str, Callable[[], Dict[str, Any]]],
) -> tuple[int, Dict[str, Any]]:
    if not hmac.compare_digest(supplied_token, api_token):
        return HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"}
    action = EXTRA_ACTION_ROUTES.get(path)
    callback = action_callbacks.get(action or "")
    if callback is None:
        return HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"}
    try:
        callback()
        return HTTPStatus.OK, {"ok": True}
    except (OSError, ValueError) as exc:
        return HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)}


def build_handler(
    state: DashboardState,
    api_token: str,
    ticktick_action: Optional[Callable[[str], Dict[str, Any]]] = None,
    action_callbacks: Optional[Dict[str, Callable[[], Dict[str, Any]]]] = None,
) -> type[BaseHTTPRequestHandler]:
    seen_clients: set[str] = set()
    extra_actions = dict(action_callbacks or {})

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

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path.startswith("/api/ticktick/"):
                status, body = dispatch_ticktick_action(
                    path, self.headers.get("X-Dashboard-Token", ""), api_token, ticktick_action
                )
            else:
                status, body = dispatch_dashboard_action(
                    path,
                    self.headers.get("X-Dashboard-Token", ""),
                    api_token,
                    extra_actions,
                )
            if status == HTTPStatus.OK:
                self._json(HTTPStatus.OK, state.snapshot())
            else:
                self._json(status, body)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="TickTick + Codex bridge for M5Stack StopWatch")
    parser.add_argument("--config", default="config.json", help="path to config.json")
    args = parser.parse_args(argv)
    config = load_config(Path(args.config).expanduser().resolve())
    ticktick_config = config.get("ticktick") or {}
    codex_config = config.get("codex") or {}
    claude_config = config.get("claude") or {}
    weather_config = config.get("weather") or {}
    ai_usage_config = config.get("ai_usage") or {}
    ai_hotspot_config = config.get("ai_hotspot") or {}
    obsidian_config = config.get("obsidian") or {}
    typeless_config = config.get("typeless") or {}
    server_config = config["server"]
    configured_peers = config.get("peers") if isinstance(config.get("peers"), list) else []
    peer_sources = resolve_peer_auth(
        configured_peers,
        codex_config.get("peer_usage_sources") or [],
    )
    dashboard = DashboardState(str(server_config.get("device_label") or "Air"), bool(peer_sources))
    workers: list[Any] = []
    action_callbacks: Dict[str, Callable[[], Dict[str, Any]]] = {}

    ticktick_monitor: Optional[TickTickMonitor] = None
    if ticktick_config.get("enabled", True):
        ticktick_monitor = TickTickMonitor(ticktick_config, dashboard.set_ticktick)
        monitor = ticktick_monitor
        monitor.start()
        workers.append(monitor)
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
    if ai_usage_config.get("enabled", False):
        monitor = AIUsageMonitor(ai_usage_config, dashboard.set_ai_usage)
        monitor.start()
        workers.append(monitor)
    if ai_hotspot_config.get("enabled", False):
        monitor = AIHotspotMonitor(ai_hotspot_config, dashboard.set_ai_hotspot)
        monitor.start()
        workers.append(monitor)
        action_callbacks["ai-ack"] = monitor.acknowledge
        action_callbacks["ai-open"] = monitor.open_current
    if obsidian_config.get("enabled", False):
        monitor = ObsidianDice(obsidian_config, dashboard.set_obsidian)
        monitor.start()
        workers.append(monitor)
        action_callbacks["obsidian-roll"] = monitor.roll
        action_callbacks["obsidian-open"] = monitor.open_selected
    if typeless_config.get("enabled", True):
        typeless = TypelessController(typeless_config)
        action_callbacks["typeless-start"] = lambda: typeless.perform("start")
        action_callbacks["typeless-stop"] = lambda: typeless.perform("stop")
    if peer_sources:
        monitor = PeerStateMonitor(
            peer_sources,
            str(server_config["api_token"]),
            dashboard.set_peer_states,
            int(config.get("peer_refresh_seconds", 2)),
        )
        monitor.start()
        workers.append(monitor)

    server = ThreadingHTTPServer(
        (str(server_config.get("bind") or "0.0.0.0"), int(server_config.get("port", 8765))),
        build_handler(
            dashboard,
            str(server_config["api_token"]),
            ticktick_monitor.perform if ticktick_monitor is not None else None,
            action_callbacks,
        ),
    )
    if server_config.get("discovery_enabled", True):
        discovery = DiscoveryResponder(
            str(server_config.get("bind") or "0.0.0.0"),
            int(server_config.get("discovery_port", 8766)),
            int(server.server_address[1]),
        )
        discovery.start()
        workers.append(discovery)
    if server_config.get("usb_enabled", True):
        usb_snapshot = UsbSnapshotSource(dashboard.snapshot, server_config.get("usb_upstream"))
        usb_api_token = str(server_config.get("usb_api_token") or server_config["api_token"])
        def usb_action(action: str) -> Dict[str, Any]:
            if action in ACTIONS and ticktick_monitor is not None:
                return ticktick_monitor.perform(action)
            callback = action_callbacks.get(action)
            if callback is None:
                raise ValueError("dashboard action is unavailable")
            return callback()

        usb = UsbSerialResponder(usb_snapshot, usb_api_token, usb_action)
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
