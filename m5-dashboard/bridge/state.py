from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict

from .peer_state import merge_provider_states


def deep_merge(target: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Merge delta-style printer reports without losing unchanged values."""
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_printer_state(raw: Dict[str, Any], connected: bool, name: str) -> Dict[str, Any]:
    state = str(raw.get("gcode_state") or "UNKNOWN").upper()
    error_code = str(raw.get("mc_print_error_code") or "0")
    hms = raw.get("hms") if isinstance(raw.get("hms"), list) else []
    if error_code not in ("", "0", "0000000000000000"):
        state = "FAILED"

    state_labels = {
        "RUNNING": "PRINTING",
        "PREPARE": "PREPARING",
        "PAUSE": "PAUSED",
        "FINISH": "FINISHED",
        "FAILED": "ERROR",
        "IDLE": "IDLE",
    }
    filename = raw.get("subtask_name") or raw.get("gcode_file") or ""
    return {
        "connected": connected,
        "name": name,
        "state": state,
        "state_label": state_labels.get(state, state),
        "progress": max(0, min(100, int(_number(raw.get("mc_percent"))))),
        "remaining_min": max(0, int(_number(raw.get("mc_remaining_time")))),
        "nozzle_temp": round(_number(raw.get("nozzle_temper")), 1),
        "nozzle_target": round(_number(raw.get("nozzle_target_temper")), 1),
        "bed_temp": round(_number(raw.get("bed_temper")), 1),
        "bed_target": round(_number(raw.get("bed_target_temper")), 1),
        "chamber_temp": round(_number(raw.get("chamber_temper")), 1),
        "layer": max(0, int(_number(raw.get("layer_num")))),
        "total_layers": max(0, int(_number(raw.get("total_layer_num")))),
        "file": str(filename),
        "error_code": error_code,
        "hms_count": len(hms),
    }


class DashboardState:
    def __init__(
        self, printer_name: str = "P2S", device_label: str = "Air",
        aggregate_peers: bool = False,
    ) -> None:
        self._lock = threading.RLock()
        self._started_at = int(time.time())
        self._printer_name = printer_name
        self._device_label = str(device_label or "Air")[:16]
        self._aggregate_peers = bool(aggregate_peers)
        self._peer_states: list[Dict[str, Any]] = []
        self._printer_raw: Dict[str, Any] = {}
        self._printer_connected = False
        self._printer_updated_at = 0
        self._codex: Dict[str, Any] = {
            "connected": False,
            "active_count": 0,
            "waiting_count": 0,
            "error_count": 0,
            "sessions": [],
            "transcripts": [],
            "results": [],
            "limits": [],
            "usage": {},
            "updated_at": 0,
            "error": "starting",
        }
        self._claude: Dict[str, Any] = {
            "connected": False,
            "active_count": 0,
            "waiting_count": 0,
            "error_count": 0,
            "transcripts": [],
            "results": [],
            "today_tokens": 0,
            "lifetime_tokens": 0,
            "short_used_percent": -1,
            "short_resets_at": 0,
            "week_used_percent": -1,
            "week_resets_at": 0,
            "updated_at": 0,
            "error": "starting",
        }
        self._weather: Dict[str, Any] = {
            "available": False,
            "city": "苏州",
            "temperature_c": 0,
            "weather_code": -1,
            "label": "",
            "updated_at": 0,
            "error": "starting",
        }

    def merge_printer(self, report: Dict[str, Any]) -> None:
        payload = report.get("print")
        if not isinstance(payload, dict):
            payload = report.get("pushing")
        if not isinstance(payload, dict):
            return
        with self._lock:
            deep_merge(self._printer_raw, payload)
            self._printer_connected = True
            self._printer_updated_at = int(time.time())

    def set_printer_connected(self, connected: bool) -> None:
        with self._lock:
            self._printer_connected = connected

    def set_codex(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._codex = copy.deepcopy(value)

    def set_claude(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._claude = copy.deepcopy(value)

    def set_weather(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._weather = copy.deepcopy(value)

    def set_peer_states(self, value: list[Dict[str, Any]]) -> None:
        with self._lock:
            self._peer_states = copy.deepcopy(value)

    def snapshot(self) -> Dict[str, Any]:
        now = int(time.time())
        with self._lock:
            # Cloud MQTT can stay healthy for minutes without a printer report,
            # especially after a job finishes. Connection health comes from the
            # MQTT socket; report age is metadata, not an offline signal.
            printer_connected = self._printer_connected and self._printer_updated_at > 0
            printer = normalize_printer_state(
                copy.deepcopy(self._printer_raw), printer_connected, self._printer_name
            )
            printer["updated_at"] = self._printer_updated_at
            codex = copy.deepcopy(self._codex)
            claude = copy.deepcopy(self._claude)
            if self._aggregate_peers:
                codex = merge_provider_states(
                    codex, self._peer_states, "codex", self._device_label
                )
                claude = merge_provider_states(
                    claude, self._peer_states, "claude", self._device_label
                )
            return {
                "ok": True,
                "device_label": self._device_label,
                "server_time": now,
                "uptime_sec": now - self._started_at,
                "printer": printer,
                "codex": codex,
                "claude": claude,
                "weather": copy.deepcopy(self._weather),
            }
