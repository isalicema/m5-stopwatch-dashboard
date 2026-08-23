#!/usr/bin/env python3
"""Persist content-free Claude Code completion receipts for M5 Dashboard."""

from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_STATE = Path.home() / "Library/Application Support/M5Dashboard/claude_hooks.json"
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
            "http://127.0.0.1:%d/api/internal/completion/claude" % port,
            data=json.dumps(completion, separators=(",", ":")).encode("utf-8"),
            headers={"X-Dashboard-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=0.35) as response:
            return 200 <= int(response.status) < 300
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def apply_event(state: Dict[str, Any], event: Dict[str, Any], now: int) -> Dict[str, Any]:
    """Record only Claude's authoritative top-level Stop hook."""
    if str(event.get("hook_event_name") or "") != "Stop":
        return state
    session_id = str(event.get("session_id") or "unknown")
    sessions = state.setdefault("sessions", {})
    session = sessions.setdefault(session_id, {"session_id": session_id})
    # Firmware currently deduplicates on completed_at. Preserve a strictly
    # increasing seconds watermark even for two unusually fast Stop callbacks.
    completed_at = max(now, int(session.get("completed_at") or 0) + 1)
    session.update(
        {
            "session_id": session_id,
            "status": "idle",
            "last_event": "Stop",
            "last_event_at": now,
            "completed_at": completed_at,
            "completion_id": "%s:%d" % (session_id, completed_at),
        }
    )
    state["updated_at"] = now
    return state


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_file(
    path: Path, event: Dict[str, Any], now: Optional[int] = None
) -> Dict[str, Any]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, json.JSONDecodeError):
            state = {}
        _atomic_write(path, apply_event(state, event, int(time.time()) if now is None else now))
        return dict(state.get("sessions", {}).get(str(event.get("session_id") or "unknown"), {}))


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return 0
        configured = os.environ.get("M5_DASH_CLAUDE_STATE")
        session = update_file(Path(configured).expanduser() if configured else DEFAULT_STATE, event)
        if event.get("hook_event_name") == "Stop":
            notify_bridge(
                {
                    "id": str(session.get("completion_id") or "")[-64:],
                    "title": "Claude",
                    "completed_at": int(session.get("completed_at") or 0),
                }
            )
    except Exception:
        # A monitoring hook must never interfere with Claude Code.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
