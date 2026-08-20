from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_MAX_TRACKED_MESSAGES = 32
_MAX_PUBLIC_TASKS = 2
_MAX_PUBLIC_MESSAGES = 6
_MAX_PUBLIC_CHARS = 240
_MAX_PUBLIC_RESULTS = 6


def _epoch(value: Any, fallback: float) -> float:
    if not isinstance(value, str) or not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.timestamp()


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.replace("\x00", " ").replace("\r", "\n")
    text = re.sub(r"[\t\n ]+", " ", text)
    return text.strip()


def _public_text(text: str, role: str) -> str:
    if len(text) <= _MAX_PUBLIC_CHARS:
        return text
    if role == "assistant":
        return "…" + text[-(_MAX_PUBLIC_CHARS - 1) :]
    return text[: _MAX_PUBLIC_CHARS - 1] + "…"


def _content_text(content: Any, allowed_types: set[str]) -> str:
    if isinstance(content, str):
        return _clean_text(content)
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") not in allowed_types:
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text)
    return _clean_text("\n".join(parts))


class _TranscriptTracker:
    def __init__(self, root: str, stale_seconds: int = 1800, max_files: int = 12) -> None:
        self.root = Path(root).expanduser()
        self.stale_seconds = max(30, int(stale_seconds))
        self.max_files = max(1, int(max_files))
        self._offsets: Dict[Path, int] = {}
        self._states: Dict[Path, Dict[str, Any]] = {}

    def _recent_paths(self, now: float) -> List[Path]:
        if not self.root.is_dir():
            return []
        candidates = []
        try:
            for path in self.root.rglob("*.jsonl"):
                try:
                    modified = path.stat().st_mtime
                except OSError:
                    continue
                if modified >= now - self.stale_seconds:
                    candidates.append((modified, path))
        except OSError:
            return []
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [path for _, path in candidates[: self.max_files]]

    def _new_state(self, path: Path, modified: float) -> Dict[str, Any]:
        return {
            "path": path,
            "session_id": path.stem,
            "title": "",
            "status": "unknown",
            "last_event": modified,
            "modified": modified,
            "messages": [],
            "message_indexes": {},
        }

    def _advance(self, path: Path) -> None:
        try:
            size = path.stat().st_size
            modified = path.stat().st_mtime
        except OSError:
            return
        offset = self._offsets.get(path, 0)
        if size < offset:
            offset = 0
            self._states.pop(path, None)
        state = self._states.setdefault(path, self._new_state(path, modified))
        state["modified"] = modified
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(offset)
                while True:
                    line = handle.readline()
                    if not line:
                        break
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict):
                        self._consume(state, record, _epoch(record.get("timestamp"), modified))
                self._offsets[path] = handle.tell()
        except OSError:
            return

    def _upsert_message(
        self, state: Dict[str, Any], key: str, role: str, text: str, stamp: float
    ) -> None:
        cleaned = _clean_text(text)
        if not cleaned:
            return
        messages = state["messages"]
        indexes = state["message_indexes"]
        existing = indexes.get(key)
        value = {"id": key, "role": role, "text": cleaned, "updated_at": int(stamp)}
        if isinstance(existing, int) and 0 <= existing < len(messages):
            messages[existing] = value
        else:
            indexes[key] = len(messages)
            messages.append(value)
        if role == "user" and not state.get("title"):
            state["title"] = cleaned[:36]
        if len(messages) > _MAX_TRACKED_MESSAGES:
            state["messages"] = messages[-_MAX_TRACKED_MESSAGES:]
            state["message_indexes"] = {
                item["id"]: index for index, item in enumerate(state["messages"])
            }

    def _consume(self, state: Dict[str, Any], record: Dict[str, Any], stamp: float) -> None:
        raise NotImplementedError

    def _fallback_title(self, state: Dict[str, Any], index: int) -> str:
        raise NotImplementedError

    def snapshots(self, expose: bool = False) -> List[Dict[str, Any]]:
        if not expose:
            return []
        now = datetime.now().timestamp()
        for path in self._recent_paths(now):
            self._advance(path)
        active = [
            state
            for state in self._states.values()
            if state.get("status") == "working"
            and now
            - max(float(state.get("last_event") or 0), float(state.get("modified") or 0))
            <= self.stale_seconds
        ]
        active.sort(
            key=lambda state: max(
                float(state.get("last_event") or 0), float(state.get("modified") or 0)
            ),
            reverse=True,
        )
        output = []
        for index, state in enumerate(active[:_MAX_PUBLIC_TASKS], 1):
            messages = []
            for message in state.get("messages", [])[-_MAX_PUBLIC_MESSAGES:]:
                role = "user" if message.get("role") == "user" else "assistant"
                messages.append(
                    {
                        "role": role,
                        "text": _public_text(str(message.get("text") or ""), role),
                        "updated_at": int(message.get("updated_at") or 0),
                    }
                )
            title = _clean_text(state.get("title")) or self._fallback_title(state, index)
            output.append(
                {
                    "id": str(state.get("session_id") or "")[-8:],
                    "title": _public_text(title, "user")[:36],
                    "status": "working",
                    "updated_at": int(
                        max(
                            float(state.get("last_event") or 0),
                            float(state.get("modified") or 0),
                        )
                    ),
                    "messages": messages,
                }
            )
        return output

    def completed_today(
        self, expose: bool = False, limit: int = _MAX_PUBLIC_RESULTS,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent completed visible tasks from this Mac's local day."""
        if not expose:
            return []
        current = now or datetime.now().astimezone()
        if current.tzinfo is None:
            current = current.astimezone()
        day_start = current.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        for path in self._recent_paths(current.timestamp()):
            self._advance(path)
        completed = []
        for index, state in enumerate(self._states.values(), 1):
            stamp = max(
                float(state.get("last_event") or 0),
                float(state.get("modified") or 0),
            )
            if state.get("status") != "idle" or stamp < day_start:
                continue
            title = _clean_text(state.get("title")) or self._fallback_title(state, index)
            completed.append(
                {
                    "id": str(state.get("session_id") or "")[-8:],
                    "title": _public_text(title, "user")[:36],
                    "completed_at": int(stamp),
                }
            )
        completed.sort(key=lambda item: int(item["completed_at"]), reverse=True)
        return completed[: max(0, int(limit))]


class LocalCodexTranscripts(_TranscriptTracker):
    """Expose only visible user/assistant messages from active local Codex tasks."""

    def _consume(self, state: Dict[str, Any], record: Dict[str, Any], stamp: float) -> None:
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        if record.get("type") == "session_meta":
            session_id = payload.get("id")
            if isinstance(session_id, str) and session_id:
                state["session_id"] = session_id
            return
        if record.get("type") != "event_msg":
            return
        kind = payload.get("type")
        if kind == "task_started":
            state.update({"status": "working", "last_event": stamp})
        elif kind == "task_complete":
            state.update({"status": "idle", "last_event": stamp})
        elif kind == "user_message":
            state.update({"status": "working", "last_event": stamp})
            key = str(payload.get("client_id") or "user-%d" % int(stamp * 1000))
            self._upsert_message(state, key, "user", str(payload.get("message") or ""), stamp)
        elif kind == "agent_message":
            state.update({"status": "working", "last_event": stamp})
            key = "agent-%d-%d" % (int(stamp * 1000), len(state["messages"]))
            self._upsert_message(state, key, "assistant", str(payload.get("message") or ""), stamp)
        elif kind == "agent_reasoning":
            state.update({"status": "working", "last_event": stamp})

    def _fallback_title(self, state: Dict[str, Any], index: int) -> str:
        return "Codex %d" % index


class LocalClaudeTranscripts(_TranscriptTracker):
    """Expose Claude Code text blocks while excluding thinking and tool payloads."""

    @staticmethod
    def _user_text(content: Any) -> str:
        return _content_text(content, {"text", "input_text"})

    @staticmethod
    def _assistant_text(content: Any) -> str:
        return _content_text(content, {"text", "output_text"})

    def _consume(self, state: Dict[str, Any], record: Dict[str, Any], stamp: float) -> None:
        kind = record.get("type")
        if kind not in {"user", "assistant"}:
            return
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        if kind == "user":
            text = self._user_text(message.get("content"))
            if not text:
                return
            session_id = record.get("sessionId")
            if isinstance(session_id, str) and session_id:
                state["session_id"] = session_id
            state.update({"status": "working", "last_event": stamp})
            key = str(record.get("uuid") or record.get("promptId") or "user-%d" % int(stamp * 1000))
            self._upsert_message(state, key, "user", text, stamp)
            return

        text = self._assistant_text(message.get("content"))
        if text:
            key = str(message.get("id") or record.get("uuid") or "assistant-%d" % int(stamp * 1000))
            self._upsert_message(state, key, "assistant", text, stamp)
            state["last_event"] = stamp
        stop_reason = message.get("stop_reason")
        if stop_reason == "end_turn":
            state.update({"status": "idle", "last_event": stamp})
        elif stop_reason in {"tool_use", "pause_turn", "max_tokens"}:
            state.update({"status": "working", "last_event": stamp})

    def _fallback_title(self, state: Dict[str, Any], index: int) -> str:
        return "Claude %d" % index
