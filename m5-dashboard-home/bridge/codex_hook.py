#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict


DEFAULT_STATE = Path.home() / "Library/Application Support/M5Dashboard/codex_hooks.json"


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
    elif name == "Stop":
        session["status"] = (
            "waiting_input" if _looks_like_question(event.get("last_assistant_message")) else "idle"
        )
        session["turn_stopped_at"] = now
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


def update_file(path: Path, event: Dict[str, Any]) -> None:
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


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return 0
        configured = os.environ.get("M5_DASH_CODEX_STATE")
        update_file(Path(configured).expanduser() if configured else DEFAULT_STATE, event)
        if event.get("hook_event_name") in ("Stop", "SubagentStop"):
            print("{}")
    except Exception:
        # Monitoring must never interfere with Codex itself.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
