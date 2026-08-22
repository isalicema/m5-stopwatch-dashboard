from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict

from .peer_state import merge_provider_states


def _quota_window(windows: list[Dict[str, Any]], short: bool) -> Dict[str, Any]:
    for window in windows:
        if not isinstance(window, dict):
            continue
        seconds = max(0, int(window.get("window_seconds") or 0))
        label = str(window.get("label") or "")
        is_short = (seconds > 0 and seconds <= 12 * 3600) or "5小时" in label
        if is_short == short:
            return window
    return {}


def _apply_usage_board_provider(
    provider: Dict[str, Any], ai_usage: Dict[str, Any], provider_id: str
) -> Dict[str, Any]:
    enriched = copy.deepcopy(provider)
    channels = ai_usage.get("channels") if isinstance(ai_usage.get("channels"), list) else []
    channel = next(
        (item for item in channels if isinstance(item, dict) and item.get("id") == provider_id),
        {},
    )
    if not enriched.get("today_tokens") and channel:
        enriched["today_tokens"] = max(0, int(channel.get("tokens") or 0))
    if provider_id == "codex":
        usage = enriched.setdefault("usage", {})
        if not usage.get("today_tokens") and channel:
            usage["today_tokens"] = max(0, int(channel.get("tokens") or 0))

    quotas = (
        ai_usage.get("provider_quotas")
        if isinstance(ai_usage.get("provider_quotas"), dict)
        else {}
    )
    quota = quotas.get(provider_id) if isinstance(quotas.get(provider_id), dict) else {}
    windows = quota.get("windows") if isinstance(quota.get("windows"), list) else []
    if quota.get("status") in ("online", "stale") and windows:
        enriched["connected"] = True
        if not enriched.get("error_count"):
            enriched["error"] = ""

    if provider_id == "codex" and windows:
        normalized_limits = []
        for window in windows:
            if not isinstance(window, dict) or int(window.get("used_percent", -1)) < 0:
                continue
            normalized_limits.append(
                {
                    "id": "codex",
                    "name": str(window.get("label") or "Codex"),
                    "used_percent": int(window["used_percent"]),
                    "window_minutes": max(0, int(window.get("window_seconds") or 0)) // 60,
                    "resets_at": max(0, int(window.get("resets_at") or 0)),
                }
            )
        if normalized_limits:
            enriched["limits"] = normalized_limits
    elif provider_id == "claude" and windows:
        short = _quota_window(windows, True)
        week = _quota_window(windows, False)
        if short:
            enriched["short_used_percent"] = int(short.get("used_percent", -1))
            enriched["short_resets_at"] = max(0, int(short.get("resets_at") or 0))
        if week:
            enriched["week_used_percent"] = int(week.get("used_percent", -1))
            enriched["week_resets_at"] = max(0, int(week.get("resets_at") or 0))
    return enriched


class DashboardState:
    def __init__(
        self, device_label: str = "Air", aggregate_peers: bool = False,
    ) -> None:
        self._lock = threading.RLock()
        self._started_at = int(time.time())
        self._device_label = str(device_label or "Air")[:16]
        self._aggregate_peers = bool(aggregate_peers)
        self._peer_states: list[Dict[str, Any]] = []
        self._ticktick: Dict[str, Any] = {
            "connected": False,
            "stopwatch": {"state": "idle", "elapsed_seconds": 0},
            "countdown": {"state": "idle", "duration_seconds": 1500, "remaining_seconds": 1500},
            "updated_at": 0,
            "error": "starting",
        }
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
        self._ai_usage: Dict[str, Any] = {
            "connected": False,
            "complete": False,
            "date": "",
            "today_total_tokens": 0,
            "today_authoritative_tokens": 0,
            "breakdown": {},
            "channels": [],
            "incomplete_channels": [],
            "approximate": False,
            "updated_at": 0,
            "error": "starting",
        }
        self._ai_hotspot: Dict[str, Any] = {
            "connected": False,
            "active": False,
            "unread_count": 0,
            "alert": {},
            "updated_at": 0,
            "error": "starting",
        }
        self._obsidian: Dict[str, Any] = {
            "connected": False,
            "available_count": 0,
            "selected": {},
            "rolled_at": 0,
            "updated_at": 0,
            "error": "starting",
        }

    def set_ticktick(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._ticktick = copy.deepcopy(value)

    def set_codex(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._codex = copy.deepcopy(value)

    def set_claude(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._claude = copy.deepcopy(value)

    def set_weather(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._weather = copy.deepcopy(value)

    def set_ai_usage(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._ai_usage = copy.deepcopy(value)

    def set_ai_hotspot(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._ai_hotspot = copy.deepcopy(value)

    def set_obsidian(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._obsidian = copy.deepcopy(value)

    def set_peer_states(self, value: list[Dict[str, Any]]) -> None:
        with self._lock:
            self._peer_states = copy.deepcopy(value)

    def snapshot(self) -> Dict[str, Any]:
        now = int(time.time())
        with self._lock:
            codex = copy.deepcopy(self._codex)
            claude = copy.deepcopy(self._claude)
            ai_usage = copy.deepcopy(self._ai_usage)
            codex = _apply_usage_board_provider(codex, ai_usage, "codex")
            claude = _apply_usage_board_provider(claude, ai_usage, "claude")
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
                "ticktick": copy.deepcopy(self._ticktick),
                "codex": codex,
                "claude": claude,
                "weather": copy.deepcopy(self._weather),
                "ai_usage": ai_usage,
                "ai_hotspot": copy.deepcopy(self._ai_hotspot),
                "obsidian": copy.deepcopy(self._obsidian),
            }
