from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


_WEATHER_LABELS = {
    0: "晴",
    1: "晴间多云",
    2: "多云",
    3: "阴",
    45: "有雾",
    48: "雾凇",
    51: "小毛雨",
    53: "毛毛雨",
    55: "较强毛雨",
    56: "冻毛雨",
    57: "强冻毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "米雪",
    80: "阵雨",
    81: "较强阵雨",
    82: "强阵雨",
    85: "阵雪",
    86: "强阵雪",
    95: "雷雨",
    96: "雷雨冰雹",
    99: "强雷雨冰雹",
}


def normalize_weather(
    payload: Dict[str, Any], city: str, now: Optional[int] = None
) -> Dict[str, Any]:
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    try:
        temperature = round(float(current["temperature_2m"]), 1)
        code = int(current["weather_code"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("weather response is missing current conditions") from exc
    return {
        "available": True,
        "city": city,
        "temperature_c": temperature,
        "weather_code": code,
        "label": _WEATHER_LABELS.get(code, "天气变化"),
        "updated_at": int(now if now is not None else time.time()),
        "error": "",
    }


def fetch_weather(config: Dict[str, Any]) -> Dict[str, Any]:
    city = str(config.get("city") or "苏州")
    params = urllib.parse.urlencode(
        {
            "latitude": float(config.get("latitude", 31.2989)),
            "longitude": float(config.get("longitude", 120.5853)),
            "current": "temperature_2m,weather_code",
            "timezone": str(config.get("timezone") or "Asia/Shanghai"),
        }
    )
    request = urllib.request.Request(
        "https://api.open-meteo.com/v1/forecast?" + params,
        headers={"User-Agent": "M5Dashboard/0.1"},
    )
    timeout = max(2, int(config.get("timeout_seconds", 8)))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("weather response must be an object")
    return normalize_weather(payload, city)


class WeatherMonitor(threading.Thread):
    daemon = True

    def __init__(self, config: Dict[str, Any], on_state: Any) -> None:
        super().__init__(name="weather-monitor")
        self.config = config
        self.on_state = on_state
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        refresh_seconds = max(3600, int(self.config.get("refresh_seconds", 3600)))
        last: Dict[str, Any] = {}
        while not self._stop_event.is_set():
            try:
                last = fetch_weather(self.config)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                failed = dict(last)
                failed.setdefault("available", False)
                failed.setdefault("city", str(self.config.get("city") or "苏州"))
                failed["error"] = str(exc)[:160]
                self.on_state(failed)
            else:
                self.on_state(last)
            self._stop_event.wait(refresh_seconds)
