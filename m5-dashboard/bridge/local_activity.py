from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


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


class _JsonlActivityTracker:
    """Incrementally tracks the latest state in recently written local session logs."""

    def __init__(self, root: str, stale_seconds: int = 1800, max_files: int = 24) -> None:
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
        state = self._states.setdefault(
            path, {"state": "unknown", "last_event": modified, "modified": modified}
        )
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

    def _consume(self, state: Dict[str, Any], record: Dict[str, Any], stamp: float) -> None:
        raise NotImplementedError

    def _refresh(self) -> Iterable[Dict[str, Any]]:
        now = datetime.now().timestamp()
        for path in self._recent_paths(now):
            self._advance(path)
        return self._states.values()


class LocalCodexActivity(_JsonlActivityTracker):
    """Use Codex's durable task lifecycle records when notification hooks are absent."""

    def _consume(self, state: Dict[str, Any], record: Dict[str, Any], stamp: float) -> None:
        if record.get("type") != "event_msg":
            return
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        kind = payload.get("type")
        if kind == "task_started":
            state.update({"state": "working", "last_event": stamp})
        elif kind == "task_complete":
            state.update({"state": "idle", "last_event": stamp})
        elif kind in {"agent_reasoning", "agent_message"}:
            # Some Codex desktop turns resume in the same session without a
            # fresh task_started event. Any later agent work re-opens the task;
            # a subsequent task_complete still wins immediately.
            state.update({"state": "working", "last_event": stamp})

    def active_count(self) -> int:
        now = datetime.now().timestamp()
        return sum(
            1
            for state in self._refresh()
            if state.get("state") == "working"
            and now - max(float(state.get("last_event") or 0), float(state.get("modified") or 0))
            <= self.stale_seconds
        )


class LocalClaudeActivity(_JsonlActivityTracker):
    """Infer Claude Code activity from prompt/tool-use/end-turn session records."""

    @staticmethod
    def _is_prompt(content: Any) -> bool:
        if isinstance(content, str):
            return bool(content.strip())
        if not isinstance(content, list):
            return False
        return any(
            isinstance(item, dict) and item.get("type") not in {"tool_result"}
            for item in content
        )

    @staticmethod
    def _has_visible_assistant_text(content: Any) -> bool:
        if isinstance(content, str):
            return bool(content.strip())
        if not isinstance(content, list):
            return False
        return any(
            isinstance(item, dict)
            and item.get("type") in {"text", "output_text"}
            and isinstance(item.get("text"), str)
            and bool(item["text"].strip())
            for item in content
        )

    def _consume(self, state: Dict[str, Any], record: Dict[str, Any], stamp: float) -> None:
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        if record.get("type") == "user" and self._is_prompt(message.get("content")):
            state.update({"state": "working", "last_event": stamp})
            return
        if record.get("type") != "assistant":
            return
        stop_reason = message.get("stop_reason")
        if stop_reason == "end_turn" and self._has_visible_assistant_text(
            message.get("content")
        ):
            state.update({"state": "idle", "last_event": stamp})
        elif stop_reason in {"tool_use", "pause_turn", "max_tokens"}:
            state.update({"state": "working", "last_event": stamp})

    def active_count(self) -> int:
        now = datetime.now().timestamp()
        return sum(
            1
            for state in self._refresh()
            if state.get("state") == "working"
            and now - max(float(state.get("last_event") or 0), float(state.get("modified") or 0))
            <= self.stale_seconds
        )
