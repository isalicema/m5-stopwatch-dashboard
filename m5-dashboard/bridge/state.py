from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict

from .peer_state import merge_provider_states


def _compact_transcripts(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    tasks: list[Dict[str, Any]] = []
    for source in value[:3]:
        if not isinstance(source, dict):
            continue
        task = {
            key: copy.deepcopy(source[key])
            for key in ("id", "title", "status", "content_visible")
            if key in source
        }
        messages = source.get("messages")
        if isinstance(messages, list):
            task["messages"] = [
                {
                    key: copy.deepcopy(message[key])
                    for key in ("role", "text")
                    if key in message
                }
                for message in messages[:6]
                if isinstance(message, dict)
            ]
        tasks.append(task)
    return tasks


def _compact_results(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {
            key: copy.deepcopy(source[key])
            for key in ("id", "title", "completed_at")
            if key in source
        }
        for source in value[:6]
        if isinstance(source, dict)
    ]


def compact_dashboard_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Return only fields consumed by the watch firmware."""

    def section(name: str) -> Dict[str, Any]:
        value = snapshot.get(name)
        return value if isinstance(value, dict) else {}

    def picked(source: Dict[str, Any], keys: tuple[str, ...]) -> Dict[str, Any]:
        return {key: copy.deepcopy(source[key]) for key in keys if key in source}

    codex = section("codex")
    claude = section("claude")
    ai_usage = section("ai_usage")
    hotspot = section("ai_hotspot")
    obsidian = section("obsidian")
    compact_codex = picked(
        codex,
        (
            "connected",
            "active_count",
            "waiting_count",
            "error_count",
            "limits",
            "usage",
        ),
    )
    codex_sessions = codex.get("sessions")
    compact_codex["sessions"] = [
        picked(item, ("title", "status"))
        for item in (codex_sessions[:1] if isinstance(codex_sessions, list) else [])
        if isinstance(item, dict)
    ]
    compact_codex["transcripts"] = _compact_transcripts(codex.get("transcripts"))
    compact_codex["results"] = _compact_results(codex.get("results"))

    compact_claude = picked(
        claude,
        (
            "connected",
            "active_count",
            "waiting_count",
            "error_count",
            "today_tokens",
            "lifetime_tokens",
            "short_used_percent",
            "short_resets_at",
            "week_used_percent",
            "week_resets_at",
        ),
    )
    compact_claude["transcripts"] = _compact_transcripts(claude.get("transcripts"))
    compact_claude["results"] = _compact_results(claude.get("results"))

    return {
        "ok": snapshot.get("ok") is True,
        "server_time": max(0, int(snapshot.get("server_time") or 0)),
        "ticktick": picked(
            section("ticktick"),
            ("connected", "stopwatch", "countdown", "today_focus_seconds", "error"),
        ),
        "codex": compact_codex,
        "claude": compact_claude,
        "weather": picked(
            section("weather"),
            ("available", "city", "temperature_c", "weather_code", "label", "updated_at"),
        ),
        "ai_usage": picked(
            ai_usage,
            (
                "connected",
                "complete",
                "approximate",
                "today_total_tokens",
                "today_authoritative_tokens",
            ),
        ),
        "ai_hotspot": {
            **picked(hotspot, ("connected", "active", "unread_count")),
            "alert": picked(
                hotspot.get("alert") if isinstance(hotspot.get("alert"), dict) else {},
                ("id", "title", "source", "url", "received_at"),
            ),
        },
        "obsidian": {
            **picked(obsidian, ("connected", "available_count", "rolled_at")),
            "selected": picked(
                obsidian.get("selected")
                if isinstance(obsidian.get("selected"), dict)
                else {},
                ("title", "folder", "excerpt", "relative_path"),
            ),
        },
    }


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
    if provider_id == "claude" and not enriched.get("lifetime_tokens") and channel:
        enriched["lifetime_tokens"] = max(
            0, int(channel.get("lifetime_tokens") or 0)
        )
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

    def add_completion(self, provider: str, value: Dict[str, Any]) -> Dict[str, Any]:
        """Merge an authenticated Stop receipt before notifying the device."""
        if provider not in {"codex", "claude"}:
            raise ValueError("invalid completion provider")
        completion_id = str(value.get("id") or "")[:64]
        completed_at = max(0, int(value.get("completed_at") or 0))
        if not completion_id or completed_at <= 0:
            raise ValueError("invalid completion receipt")
        title = str(value.get("title") or ("Codex" if provider == "codex" else "Claude"))[:36]
        result = {"id": completion_id, "title": title, "completed_at": completed_at}
        with self._lock:
            target = self._codex if provider == "codex" else self._claude
            existing = target.get("results") if isinstance(target.get("results"), list) else []
            merged = [result]
            merged.extend(
                item
                for item in existing
                if isinstance(item, dict) and str(item.get("id") or "") != completion_id
            )
            merged.sort(key=lambda item: int(item.get("completed_at") or 0), reverse=True)
            target["results"] = merged[:6]
            target["updated_at"] = int(time.time())
        return result

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

    def device_snapshot(self) -> Dict[str, Any]:
        return compact_dashboard_snapshot(self.snapshot())
