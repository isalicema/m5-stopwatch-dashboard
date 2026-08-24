from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .codex_client import fetch_peer_stats
from .local_activity import LocalClaudeActivity
from .transcript import LocalClaudeTranscripts


def load_hook_sessions(path: str) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    sessions = payload.get("sessions") if isinstance(payload, dict) else {}
    return sessions if isinstance(sessions, dict) else {}


def hook_completion_results(
    hooks: Dict[str, Dict[str, Any]],
    transcript_candidates: list[Dict[str, Any]],
    expose_titles: bool,
    limit: int = 6,
    now: Optional[datetime] = None,
) -> list[Dict[str, Any]]:
    """Expose Claude completion only when the official Stop hook fired."""
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    titles = {
        str(candidate.get("id") or ""): str(candidate.get("title") or "")
        for candidate in transcript_candidates
    }
    output = []
    for index, (session_id, session) in enumerate(hooks.items(), 1):
        completed_at = int(session.get("completed_at") or 0)
        if completed_at < day_start:
            continue
        short_id = session_id[-8:]
        title = titles.get(short_id) if expose_titles else ""
        output.append(
            {
                "id": str(session.get("completion_id") or session_id)[-32:],
                "title": title or "Claude %d" % index,
                "completed_at": completed_at,
            }
        )
    output.sort(key=lambda item: int(item["completed_at"]), reverse=True)
    return output[: max(0, int(limit))]


def jsonl_completion_results(
    transcript_candidates: list[Dict[str, Any]],
    expose_titles: bool,
    limit: int = 6,
) -> list[Dict[str, Any]]:
    """Use Claude's visible final end_turn records as durable completions."""
    output = []
    for index, candidate in enumerate(transcript_candidates, 1):
        session_id = str(candidate.get("id") or "")[-8:]
        completed_at = _nonnegative_int(candidate.get("completed_at"))
        if not session_id or completed_at <= 0:
            continue
        title = str(candidate.get("title") or "") if expose_titles else ""
        output.append(
            {
                "id": session_id,
                "title": title or "Claude %d" % index,
                "completed_at": completed_at,
            }
        )
    output.sort(key=lambda item: int(item["completed_at"]), reverse=True)
    return output[: max(0, int(limit))]


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


def local_claude_state(updated_at: Optional[int] = None) -> Dict[str, Any]:
    """State used by a peer node that exposes activity but owns no quota source."""
    return {
        "connected": True,
        "active_count": 0,
        "waiting_count": 0,
        "error_count": 0,
        "today_tokens": 0,
        "today_messages": 0,
        "five_hour_tokens": 0,
        "seven_day_tokens": 0,
        "lifetime_tokens": 0,
        "lifetime_messages": 0,
        "day_over_day_percent": 0.0,
        "short_used_percent": -1,
        "short_resets_at": 0,
        "week_used_percent": -1,
        "week_resets_at": 0,
        "updated_at": int(time.time()) if updated_at is None else int(updated_at),
        "error": "",
    }


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
        self._wake_event = threading.Event()
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
        self._wake_event.set()

    def wake(self) -> Dict[str, Any]:
        """Interrupt the normal polling delay after Claude's Stop hook."""
        self._wake_event.set()
        return {"provider": "claude", "woken": True}

    def _wait(self, seconds: float) -> None:
        self._wake_event.wait(seconds)
        self._wake_event.clear()

    def _completion_results(
        self, candidates: list[Dict[str, Any]], expose_titles: bool
    ) -> list[Dict[str, Any]]:
        source = str(self.config.get("completion_source") or "jsonl").strip().lower()
        if source == "hook":
            return hook_completion_results(
                load_hook_sessions(str(self.config.get("hook_state_path") or "")),
                candidates,
                expose_titles,
            )
        return jsonl_completion_results(candidates, expose_titles)

    def run(self) -> None:
        refresh_seconds = max(15, int(self.config.get("refresh_seconds", 60)))
        activity_refresh_seconds = max(
            1 if self.config.get("expose_transcript", False) else 2,
            int(self.config.get("activity_refresh_seconds", 3)),
        )
        local_only = bool(self.config.get("local_only", False))
        next_usage = 0.0
        last: Dict[str, Any] = local_claude_state() if local_only else {}
        while not self._stop_event.is_set():
            if not local_only and time.monotonic() >= next_usage:
                try:
                    normalized = normalize_claude_stats(
                        fetch_peer_stats(self.config.get("source") or {})
                    )
                    if normalized is None:
                        raise ValueError("Claude usage source is stale or missing")
                    last = normalized
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    failed = dict(last)
                    transcripts = self._transcripts.snapshots(
                        bool(self.config.get("expose_transcript", False))
                    )
                    title_candidates = self._transcripts.completed_today(True)
                    failed.update(
                        {
                            "connected": False,
                            "active_count": max(
                                _nonnegative_int(failed.get("active_count")), len(transcripts)
                            ),
                            "transcripts": transcripts,
                            "results": self._completion_results(
                                title_candidates,
                                bool(self.config.get("expose_transcript", False)),
                            ),
                            "error": str(exc)[:160],
                        }
                    )
                    self.on_state(failed)
                next_usage = time.monotonic() + refresh_seconds
            if last:
                current = dict(last)
                if local_only:
                    current["updated_at"] = int(time.time())
                transcripts = self._transcripts.snapshots(
                    bool(self.config.get("expose_transcript", False))
                )
                title_candidates = self._transcripts.completed_today(True)
                current["active_count"] = max(
                    _nonnegative_int(current.get("active_count")),
                    self._local_activity.active_count(),
                    len(transcripts),
                )
                current["transcripts"] = transcripts
                current["results"] = self._completion_results(
                    title_candidates,
                    bool(self.config.get("expose_transcript", False)),
                )
                self.on_state(current)
            self._wait(activity_refresh_seconds)
