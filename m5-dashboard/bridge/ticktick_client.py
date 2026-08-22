from __future__ import annotations

import copy
import json
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
        self.refresh_seconds = max(0.25, float(config.get("refresh_seconds", 1)))
        self.duration_seconds = max(60, int(config.get("duration_seconds") or 1500))
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._state = self._offline("starting")
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
            "error": error,
        }

    def _request(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Focus-Token"] = self.token
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        with self._opener.open(request, timeout=self.timeout) as response:
            value = json.load(response)
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise ValueError("TickTick bridge returned an unhealthy response")
        return value

    def refresh(self) -> Dict[str, Any]:
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

    def perform(self, action: str) -> Dict[str, Any]:
        if action not in ACTIONS:
            raise ValueError("unknown TickTick action: %s" % action)
        state = self.refresh()
        stopwatch_state = str((state.get("stopwatch") or {}).get("state") or "idle")
        countdown_state = str((state.get("countdown") or {}).get("state") or "idle")

        if action == "stopwatch-click":
            if stopwatch_state in ("idle", "done", "paused") and countdown_state == "running":
                self._request("/pomo/pause", {})
            self._request("/focus/click", {})
        elif action == "stopwatch-end":
            self._request("/focus/double-click", {})
        elif action == "countdown-click":
            if countdown_state == "running":
                path, payload = "/pomo/pause", {}
            elif countdown_state == "paused":
                if stopwatch_state == "running":
                    self._request("/focus/click", {})
                path, payload = "/pomo/resume", {}
            else:
                if stopwatch_state == "running":
                    self._request("/focus/click", {})
                path, payload = "/pomo/start", {"duration_seconds": self.duration_seconds}
            self._request(path, payload)
        else:
            self._request("/pomo/end", {})
        return self.refresh()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            self.refresh()
            self._stop_event.wait(self.refresh_seconds)
