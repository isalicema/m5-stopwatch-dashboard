from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict


class DashboardState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._started_at = int(time.time())
        self._ticktick: Dict[str, Any] = {
            "connected": False,
            "stopwatch": {"state": "idle", "elapsed_seconds": 0},
            "countdown": {
                "state": "idle",
                "duration_seconds": 1500,
                "remaining_seconds": 1500,
            },
            "updated_at": 0,
            "error": "TickTick control is owned by the primary bridge",
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

    def set_ticktick(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._ticktick = copy.deepcopy(value)

    def set_codex(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._codex = copy.deepcopy(value)

    def set_claude(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._claude = copy.deepcopy(value)

    def set_weather(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._weather = copy.deepcopy(value)

    def snapshot(self) -> Dict[str, Any]:
        now = int(time.time())
        with self._lock:
            return {
                "ok": True,
                "server_time": now,
                "uptime_sec": now - self._started_at,
                "ticktick": copy.deepcopy(self._ticktick),
                "codex": copy.deepcopy(self._codex),
                "claude": copy.deepcopy(self._claude),
                "weather": copy.deepcopy(self._weather),
            }
