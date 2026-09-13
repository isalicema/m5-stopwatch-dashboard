from __future__ import annotations

import copy
from datetime import datetime
import json
import os
from pathlib import Path
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, Optional


ACTIONS = {
    "stopwatch-click",
    "stopwatch-end",
    "countdown-click",
    "countdown-end",
}


class DailyFocusLedger:
    """Persist today's observed TickTick timer progress without double counting polls."""

    def __init__(self, state_path: str = "") -> None:
        self.path = Path(state_path).expanduser() if state_path else None
        self._lock = threading.RLock()
        self._last_save_monotonic = 0.0
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path is None:
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
        self._last_save_monotonic = time.monotonic()

    @staticmethod
    def _progress(stopwatch: Dict[str, Any], countdown: Dict[str, Any]) -> tuple[int, int]:
        stopwatch_seconds = max(0, int(stopwatch.get("elapsed_seconds") or 0))
        duration = max(1, int(countdown.get("duration_seconds") or 1500))
        remaining = max(0, min(duration, int(countdown.get("remaining_seconds") or 0)))
        return stopwatch_seconds, duration - remaining

    def update(
        self,
        stopwatch: Dict[str, Any],
        countdown: Dict[str, Any],
        date: Optional[str] = None,
    ) -> int:
        current_date = date or datetime.now().astimezone().date().isoformat()
        stopwatch_progress, countdown_progress = self._progress(stopwatch, countdown)
        with self._lock:
            stored_date = str(self._data.get("date") or "")
            force_save = False
            if stored_date != current_date:
                # Seed still-visible sessions on first installation. At a real
                # midnight rollover, begin a clean day from current baselines.
                first_observation = not stored_date
                self._data = {
                    "version": 1,
                    "date": current_date,
                    "total_seconds": (
                        stopwatch_progress + countdown_progress if first_observation else 0
                    ),
                    "stopwatch_progress": stopwatch_progress,
                    "countdown_progress": countdown_progress,
                }
                force_save = True
            else:
                total = max(0, int(self._data.get("total_seconds") or 0))
                for key, current in (
                    ("stopwatch_progress", stopwatch_progress),
                    ("countdown_progress", countdown_progress),
                ):
                    previous = max(0, int(self._data.get(key) or 0))
                    if current >= previous:
                        total += current - previous
                    else:
                        # A lower value marks a new timer session. Count any
                        # progress already made before this poll.
                        total += current
                        force_save = True
                    self._data[key] = current
                self._data["total_seconds"] = total
            total_seconds = max(0, int(self._data.get("total_seconds") or 0))
            if force_save or time.monotonic() - self._last_save_monotonic >= 15:
                self._save()
            return total_seconds

    def total(self, date: Optional[str] = None) -> int:
        current_date = date or datetime.now().astimezone().date().isoformat()
        with self._lock:
            if str(self._data.get("date") or "") != current_date:
                return 0
            return max(0, int(self._data.get("total_seconds") or 0))

    def flush(self) -> None:
        with self._lock:
            self._save()


def _timer(payload: Dict[str, Any], countdown: bool = False) -> Dict[str, Any]:
    result = {
        "state": str(payload.get("state") or "idle"),
        "last_action": str(payload.get("last_action") or ""),
        "last_error": str(payload.get("last_error") or ""),
    }
    if countdown:
        result.update(
            {
                "duration_seconds": max(1, int(payload.get("duration_seconds") or 1500)),
                "remaining_seconds": max(0, int(payload.get("remaining_seconds") or 0)),
            }
        )
    else:
        result["elapsed_seconds"] = max(0, int(payload.get("elapsed_seconds") or 0))
    return result


class TickTickMonitor(threading.Thread):
    """Proxy the proven Stick S3 TickTick bridge into dashboard state."""

    daemon = True

    def __init__(self, config: Dict[str, Any], update: Callable[[Dict[str, Any]], None]) -> None:
        super().__init__(name="ticktick-monitor")
        self.config = config
        self.update = update
        self.base_url = str(config.get("base_url") or "http://127.0.0.1:8787").rstrip("/")
        self.token = str(config.get("token") or "")
        self.timeout = max(0.2, min(5.0, float(config.get("timeout_seconds", 2))))
        self.action_timeout = max(
            self.timeout,
            min(30.0, float(config.get("action_timeout_seconds", 12))),
        )
        self.refresh_seconds = max(0.25, float(config.get("refresh_seconds", 1)))
        self.duration_seconds = max(60, int(config.get("duration_seconds") or 1500))
        self._daily_focus = DailyFocusLedger(str(config.get("daily_state_path") or ""))
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._state = self._offline("starting")
        self._pending_action = ""
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _offline(self, error: str) -> Dict[str, Any]:
        return {
            "connected": False,
            "stopwatch": {"state": "idle", "elapsed_seconds": 0, "last_action": "", "last_error": ""},
            "countdown": {
                "state": "idle",
                "duration_seconds": self.duration_seconds,
                "remaining_seconds": self.duration_seconds,
                "last_action": "",
                "last_error": "",
            },
            "updated_at": 0,
            "today_focus_seconds": self._daily_focus.total(),
            "error": error,
        }

    def _request(
        self,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Focus-Token"] = self.token
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        with self._opener.open(
            request, timeout=self.timeout if timeout is None else timeout
        ) as response:
            value = json.load(response)
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise ValueError("TickTick bridge returned an unhealthy response")
        return value

    def refresh(self) -> Dict[str, Any]:
        pending_state: Optional[Dict[str, Any]] = None
        with self._lock:
            if self._pending_action:
                state = copy.deepcopy(self._state)
                timer_key = (
                    "stopwatch"
                    if self._pending_action == "stopwatch-end"
                    else "countdown"
                )
                timer = state.setdefault(timer_key, {})
                timer["state"] = "ending"
                timer["last_action"] = "ending"
                timer["last_error"] = ""
                state["connected"] = True
                state["updated_at"] = int(time.time())
                self._state = copy.deepcopy(state)
                pending_state = state
        if pending_state is not None:
            self.update(pending_state)
            return pending_state
        try:
            focus = self._request("/focus/state")
            countdown = self._request("/pomo/state")
            state = {
                "connected": True,
                "stopwatch": _timer(focus),
                "countdown": _timer(countdown, countdown=True),
                "updated_at": int(time.time()),
                "error": "",
            }
            state["today_focus_seconds"] = self._daily_focus.update(
                state["stopwatch"], state["countdown"]
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            with self._lock:
                state = copy.deepcopy(self._state)
            state["connected"] = False
            state["error"] = str(exc)
        with self._lock:
            self._state = copy.deepcopy(state)
        self.update(state)
        return state

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def _set_pending_action(self, action: str) -> None:
        with self._lock:
            self._pending_action = action
            state = copy.deepcopy(self._state)
            timer_key = "stopwatch" if action == "stopwatch-end" else "countdown"
            timer = state.setdefault(timer_key, {})
            timer["state"] = "ending"
            timer["last_action"] = "ending"
            timer["last_error"] = ""
            state["connected"] = True
            state["updated_at"] = int(time.time())
            self._state = copy.deepcopy(state)
        self.update(state)

    def _clear_pending_action(self) -> None:
        with self._lock:
            self._pending_action = ""

    def perform(self, action: str) -> Dict[str, Any]:
        if action not in ACTIONS:
            raise ValueError("unknown TickTick action: %s" % action)
        state = self.refresh()
        stopwatch_state = str((state.get("stopwatch") or {}).get("state") or "idle")
        countdown_state = str((state.get("countdown") or {}).get("state") or "idle")

        if action == "stopwatch-click":
            if stopwatch_state in ("idle", "done", "paused") and countdown_state == "running":
                self._request("/pomo/pause", {}, self.action_timeout)
            self._request("/focus/click", {}, self.action_timeout)
        elif action == "stopwatch-end":
            self._set_pending_action(action)
            try:
                self._request("/focus/double-click", {}, self.action_timeout)
            finally:
                self._clear_pending_action()
        elif action == "countdown-click":
            if countdown_state == "running":
                path, payload = "/pomo/pause", {}
            elif countdown_state == "paused":
                if stopwatch_state == "running":
                    self._request("/focus/click", {}, self.action_timeout)
                path, payload = "/pomo/resume", {}
            else:
                if stopwatch_state == "running":
                    self._request("/focus/click", {}, self.action_timeout)
                path, payload = "/pomo/start", {"duration_seconds": self.duration_seconds}
            self._request(path, payload, self.action_timeout)
        else:
            self._set_pending_action(action)
            try:
                self._request("/pomo/end", {}, self.action_timeout)
            finally:
                self._clear_pending_action()
        return self.refresh()

    def stop(self) -> None:
        self._stop_event.set()
        self._daily_focus.flush()

    def run(self) -> None:
        while not self._stop_event.is_set():
            self.refresh()
            self._stop_event.wait(self.refresh_seconds)
