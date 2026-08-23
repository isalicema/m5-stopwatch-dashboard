#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict


DEFAULT_STATE = Path.home() / "Library/Application Support/M5Dashboard/codex_hooks.json"
DEFAULT_CONFIG = Path.home() / "Library/Application Support/M5Dashboard/config.json"


def notify_bridge(completion: Dict[str, Any]) -> bool:
    """Publish one content-free completion and silently fall back to polling."""
    configured = os.environ.get("M5_DASH_CONFIG")
    path = Path(configured).expanduser() if configured else DEFAULT_CONFIG
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        server = config.get("server") if isinstance(config.get("server"), dict) else {}
        token = str(server.get("api_token") or "")
        port = int(server.get("port") or 8765)
        if not token:
            return False
        request = urllib.request.Request(
            "http://127.0.0.1:%d/api/internal/completion/codex" % port,
            data=json.dumps(completion, separators=(",", ":")).encode("utf-8"),
            headers={"X-Dashboard-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=0.35) as response:
            return 200 <= int(response.status) < 300
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _first_non_empty(event: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = event.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Translate Codex's legacy notify payload into the hook lifecycle shape."""
    if event.get("hook_event_name"):
        return event
    event_type = _first_non_empty(event, "type", "event").lower().replace("_", "-")
    if event_type != "agent-turn-complete":
        return event
    normalized = dict(event)
    normalized.update(
        {
            "hook_event_name": "TurnEnded",
            "session_id": _first_non_empty(
                event, "thread-id", "thread_id", "conversation_id", "session_id"
            )
            or "unknown",
            "turn_id": _first_non_empty(event, "turn-id", "turn_id"),
            "cwd": _first_non_empty(event, "cwd", "workspace_root"),
            "last_assistant_message": _first_non_empty(
                event, "last-assistant-message", "last_assistant_message"
            ),
        }
    )
    return normalized


def _looks_like_question(message: Any) -> bool:
    if not isinstance(message, str):
        return False
    text = message.strip().lower()
    if not text:
        return False
    if text.endswith(("?", "？")):
        return True
    hints = ("请告诉我", "请选择", "需要你确认", "你希望", "can you confirm", "which option")
    return any(hint in text[-240:] for hint in hints)


def apply_event(state: Dict[str, Any], event: Dict[str, Any], now: int) -> Dict[str, Any]:
    sessions = state.setdefault("sessions", {})
    session_id = str(event.get("session_id") or "unknown")
    name = str(event.get("hook_event_name") or "")
    session = sessions.setdefault(session_id, {"created_at": now})
    session.update(
        {
            "session_id": session_id,
            "cwd": str(event.get("cwd") or session.get("cwd") or ""),
            "model": str(event.get("model") or session.get("model") or ""),
            "last_event": name,
            "last_event_at": now,
        }
    )
    turn_id = event.get("turn_id")
    if turn_id:
        session["turn_id"] = str(turn_id)

    if name == "SessionStart":
        session["status"] = "idle"
    elif name == "UserPromptSubmit":
        session["status"] = "working"
        session["turn_started_at"] = now
    elif name == "PermissionRequest":
        session["status"] = "waiting_approval"
    elif name in ("PreToolUse", "PostToolUse", "PreCompact", "PostCompact"):
        session["status"] = "working"
    elif name in ("Stop", "TurnEnded"):
        session["status"] = (
            "waiting_input" if _looks_like_question(event.get("last_assistant_message")) else "idle"
        )
        session["turn_stopped_at"] = now
        if name == "TurnEnded":
            # This is Codex's product-level notify callback: the same anchor
            # used by peon-ping, and therefore authoritative for M5 feedback.
            completed_at = max(now, int(session.get("completed_at") or 0) + 1)
            session["completed_at"] = completed_at
            session["completion_id"] = str(
                event.get("turn_id") or "%s:%d" % (session_id, completed_at)
            )
    elif name == "SessionEnd":
        session["status"] = "closed"
        session["closed_at"] = now

    state["updated_at"] = now
    # Closed records are useful briefly for completion detection, then discarded.
    cutoff = now - 86400
    state["sessions"] = {
        key: value
        for key, value in sessions.items()
        if value.get("status") != "closed" or int(value.get("closed_at", now)) >= cutoff
    }
    return state


def update_file(path: Path, event: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, json.JSONDecodeError):
            state = {}
        apply_event(state, event, int(time.time()))
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(state, tmp, ensure_ascii=False, separators=(",", ":"))
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return dict(state.get("sessions", {}).get(str(event.get("session_id") or "unknown"), {}))


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return 0
        event = normalize_event(event)
        configured = os.environ.get("M5_DASH_CODEX_STATE")
        session = update_file(Path(configured).expanduser() if configured else DEFAULT_STATE, event)
        if event.get("hook_event_name") == "TurnEnded":
            notify_bridge(
                {
                    "id": str(session.get("completion_id") or "")[-64:],
                    "title": "Codex",
                    "completed_at": int(session.get("completed_at") or 0),
                }
            )
        if event.get("hook_event_name") in ("Stop", "SubagentStop"):
            print("{}")
    except Exception:
        # Monitoring must never interfere with Codex itself.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
