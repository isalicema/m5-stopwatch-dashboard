from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from .codex_client import fetch_peer_stats
from .claude_local import build_local_claude_payload
from .local_activity import LocalClaudeActivity
from .transcript import LocalClaudeTranscripts


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _percent(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return -1


def _timestamp(value: Any) -> int:
    if not isinstance(value, str) or not value:
        return 0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return int(parsed.timestamp())


def _usage_window(container: Dict[str, Any], *names: str) -> Dict[str, Any]:
    for name in names:
        value = container.get(name)
        if isinstance(value, dict):
            return value
    return {}


def _window_percent(window: Dict[str, Any]) -> int:
    for key in ("used_pct", "used_percent", "utilization"):
        if key in window:
            return _percent(window.get(key))
    return -1


def _window_reset(window: Dict[str, Any]) -> int:
    for key in ("resets_at", "reset_at"):
        value = window.get(key)
        if isinstance(value, (int, float)):
            return max(0, int(value))
        parsed = _timestamp(value)
        if parsed:
            return parsed
    return 0


def normalize_claude_stats(
    payload: Dict[str, Any], now: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    generated_at = payload.get("generated_at")
    generated_epoch = _timestamp(generated_at)
    if not generated_epoch:
        return None
    generated = datetime.fromtimestamp(generated_epoch, tz=current.tzinfo)
    if generated.date() != current.date():
        return None

    claude = payload.get("claude")
    if not isinstance(claude, dict):
        return None
    today = claude.get("today") if isinstance(claude.get("today"), dict) else {}
    total = claude.get("total") if isinstance(claude.get("total"), dict) else {}
    windows = claude.get("windows") if isinstance(claude.get("windows"), dict) else {}
    five_hours = _usage_window(windows, "five_hours", "five_hour")
    seven_days = _usage_window(windows, "seven_days", "seven_day")

    official = (
        claude.get("official_usage")
        if isinstance(claude.get("official_usage"), dict)
        else {}
    )
    rate_limits = (
        claude.get("rate_limits")
        if isinstance(claude.get("rate_limits"), dict)
        else {}
    )
    short_limit = _usage_window(official, "five_hours", "five_hour", "primary")
    week_limit = _usage_window(official, "seven_days", "seven_day", "secondary")
    if not short_limit:
        short_limit = _usage_window(rate_limits, "five_hours", "five_hour", "primary")
    if not week_limit:
        week_limit = _usage_window(rate_limits, "seven_days", "seven_day", "secondary")

    day_over_day = (
        today.get("day_over_day") if isinstance(today.get("day_over_day"), dict) else {}
    )
    return {
        "connected": True,
        "active_count": _nonnegative_int(claude.get("active_count")),
        "waiting_count": _nonnegative_int(claude.get("waiting_count")),
        "error_count": _nonnegative_int(claude.get("error_count")),
        "today_tokens": _nonnegative_int(today.get("total_tokens")),
        "today_messages": _nonnegative_int(today.get("msg_count")),
        "five_hour_tokens": _nonnegative_int(five_hours.get("used_tokens")),
        "seven_day_tokens": _nonnegative_int(seven_days.get("used_tokens")),
        "lifetime_tokens": _nonnegative_int(total.get("total_tokens")),
        "lifetime_messages": _nonnegative_int(total.get("msg_count")),
        "day_over_day_percent": float(day_over_day.get("pct") or 0.0),
        "short_used_percent": _window_percent(short_limit),
        "short_resets_at": _window_reset(short_limit),
        "week_used_percent": _window_percent(week_limit),
        "week_resets_at": _window_reset(week_limit),
        "updated_at": generated_epoch,
        "error": "",
    }


class ClaudeMonitor(threading.Thread):
    daemon = True

    def __init__(self, config: Dict[str, Any], on_state: Any) -> None:
        super().__init__(name="claude-monitor")
        self.config = config
        self.on_state = on_state
        self._stop_event = threading.Event()
        source = config.get("source") if isinstance(config.get("source"), dict) else {}
        self._local_activity = LocalClaudeActivity(
            str(config.get("activity_projects_root") or source.get("projects_root") or "~/.claude/projects"),
            int(config.get("activity_stale_seconds", 1800)),
        )
        self._transcripts = LocalClaudeTranscripts(
            str(config.get("activity_projects_root") or source.get("projects_root") or "~/.claude/projects"),
            int(config.get("activity_stale_seconds", 1800)),
        )

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        refresh_seconds = max(15, int(self.config.get("refresh_seconds", 60)))
        activity_refresh_seconds = max(
            1 if self.config.get("expose_transcript", False) else 2,
            int(self.config.get("activity_refresh_seconds", 3)),
        )
        next_usage = 0.0
        last: Dict[str, Any] = {}
        while not self._stop_event.is_set():
            if time.monotonic() >= next_usage:
                try:
                    source = self.config.get("source") or {}
                    if source.get("mode") == "local_claude_desktop":
                        payload = build_local_claude_payload(source)
                    else:
                        payload = fetch_peer_stats(source)
                    normalized = normalize_claude_stats(payload)
                    if normalized is None:
                        raise ValueError("Claude usage source is stale or missing")
                    last = normalized
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    failed = dict(last)
                    transcripts = self._transcripts.snapshots(
                        bool(self.config.get("expose_transcript", False))
                    )
                    failed.update(
                        {
                            "connected": False,
                            "active_count": max(
                                _nonnegative_int(failed.get("active_count")), len(transcripts)
                            ),
                            "transcripts": transcripts,
                            "results": self._transcripts.completed_today(
                                bool(self.config.get("expose_transcript", False))
                            ),
                            "error": str(exc)[:160],
                        }
                    )
                    self.on_state(failed)
                next_usage = time.monotonic() + refresh_seconds
            if last:
                current = dict(last)
                transcripts = self._transcripts.snapshots(
                    bool(self.config.get("expose_transcript", False))
                )
                current["active_count"] = max(
                    _nonnegative_int(current.get("active_count")),
                    self._local_activity.active_count(),
                    len(transcripts),
                )
                current["transcripts"] = transcripts
                current["results"] = self._transcripts.completed_today(
                    bool(self.config.get("expose_transcript", False))
                )
                self.on_state(current)
            self._stop_event.wait(activity_refresh_seconds)
