from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo


TOKEN_CHANNELS = ("claude", "codex", "kimi", "deepseek", "openrouter", "grok")
QUOTA_CHANNELS = ("claude", "codex")


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _today(timezone_name: str) -> str:
    try:
        timezone = ZoneInfo(timezone_name)
    except (KeyError, ValueError):
        timezone = ZoneInfo("Asia/Shanghai")
    return datetime.now(timezone).date().isoformat()


def normalize_ai_usage(
    payload: Dict[str, Any],
    statuses: Optional[Dict[str, Any]] = None,
    expected_date: Optional[str] = None,
    now: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    today = payload.get("today") if isinstance(payload.get("today"), dict) else {}
    date = str(today.get("date") or "")
    if not date or date != (expected_date or datetime.now().astimezone().date().isoformat()):
        return None

    breakdown_source = (
        today.get("breakdown") if isinstance(today.get("breakdown"), dict) else {}
    )
    breakdown = {
        "input": _nonnegative_int(breakdown_source.get("input")),
        "output": _nonnegative_int(breakdown_source.get("output")),
        "cache_read": _nonnegative_int(breakdown_source.get("cacheRead")),
        "cache_write": _nonnegative_int(breakdown_source.get("cacheWrite")),
    }

    channels = []
    for raw in payload.get("channels") or []:
        if not isinstance(raw, dict):
            continue
        channel_id = str(raw.get("id") or "")
        if channel_id not in TOKEN_CHANNELS:
            continue
        daily = raw.get("daily") if isinstance(raw.get("daily"), list) else []
        channel_tokens = _nonnegative_int(daily[-1] if daily else 0)
        channels.append(
            {
                "id": channel_id,
                "name": str(raw.get("name") or channel_id),
                "tokens": channel_tokens,
                "lifetime_tokens": _nonnegative_int(raw.get("total")),
                "approximate": channel_id == "grok" and channel_tokens > 0,
            }
        )

    health = statuses.get("channels") if isinstance(statuses, dict) else []
    offline = sorted(
        str(item.get("id"))
        for item in health or []
        if isinstance(item, dict)
        and item.get("id") in TOKEN_CHANNELS
        and item.get("state") == "offline"
    )
    included = {item["id"] for item in channels}
    missing = sorted(set(TOKEN_CHANNELS) - included)
    incomplete = sorted(set(offline + missing))

    return {
        "connected": True,
        "complete": not incomplete,
        "date": date,
        "today_total_tokens": _nonnegative_int(today.get("total")),
        "today_authoritative_tokens": _nonnegative_int(today.get("auth")),
        "breakdown": breakdown,
        "channels": channels,
        "incomplete_channels": incomplete,
        "approximate": any(item["approximate"] for item in channels),
        "updated_at": int(now if now is not None else time.time()),
        "error": "" if not incomplete else "incomplete token sources: " + ", ".join(incomplete),
    }


def normalize_provider_quotas(
    payload: Dict[str, Any], now: Optional[int] = None
) -> Dict[str, Any]:
    current = int(now if now is not None else time.time())
    result: Dict[str, Any] = {}
    for raw in payload.get("channels") or []:
        if not isinstance(raw, dict):
            continue
        channel_id = str(raw.get("id") or "")
        if channel_id not in QUOTA_CHANNELS:
            continue
        windows = []
        for source in raw.get("windows") or []:
            if not isinstance(source, dict):
                continue
            try:
                used_percent = float(source.get("usedPct"))
            except (TypeError, ValueError):
                used_percent = -1.0
            try:
                window_seconds = max(0, int(source.get("windowSec") or 0))
            except (TypeError, ValueError):
                window_seconds = 0
            try:
                reset_seconds = int(source.get("resetInSec"))
            except (TypeError, ValueError):
                reset_seconds = -1
            windows.append(
                {
                    "label": str(source.get("label") or ""),
                    "window_seconds": window_seconds,
                    "used_percent": (
                        max(0, min(100, int(round(used_percent))))
                        if used_percent >= 0
                        else -1
                    ),
                    "resets_at": current + reset_seconds if reset_seconds >= 0 else 0,
                }
            )
        result[channel_id] = {
            "status": str(raw.get("status") or "offline"),
            "source": str(raw.get("source") or ""),
            "note": str(raw.get("note") or ""),
            "windows": windows,
        }
    return result


def _fetch_json(url: str, timeout: int) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "M5Dashboard/0.1"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("AI usage response must be an object")
    return payload


def fetch_ai_usage(config: Dict[str, Any]) -> Dict[str, Any]:
    base_url = str(config.get("base_url") or "http://127.0.0.1:8177").rstrip("/")
    api_base = base_url if base_url.endswith("/api") else base_url + "/api"
    timeout = max(2, int(config.get("timeout_seconds", 10)))
    history_days = max(1, min(380, int(config.get("history_days", 380))))
    query = urllib.parse.urlencode({"days": history_days, "metric": "total"})
    payload = _fetch_json(api_base + "/token-series?" + query, timeout)
    statuses = _fetch_json(api_base + "/status", timeout)
    normalized = normalize_ai_usage(
        payload,
        statuses,
        expected_date=_today(str(config.get("timezone") or "Asia/Shanghai")),
    )
    if normalized is None:
        raise ValueError("AI usage source is stale or missing today's totals")
    try:
        quota_payload = _fetch_json(
            api_base + "/quota",
            max(timeout, int(config.get("quota_timeout_seconds", 30))),
        )
    except (OSError, ValueError, json.JSONDecodeError):
        normalized["provider_quotas"] = {}
    else:
        normalized["provider_quotas"] = normalize_provider_quotas(quota_payload)
    return normalized


class AIUsageMonitor(threading.Thread):
    daemon = True

    def __init__(self, config: Dict[str, Any], on_state: Any) -> None:
        super().__init__(name="ai-usage-monitor")
        self.config = config
        self.on_state = on_state
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        refresh_seconds = max(15, int(self.config.get("refresh_seconds", 30)))
        last: Dict[str, Any] = {}
        while not self._stop_event.is_set():
            try:
                last = fetch_ai_usage(self.config)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                failed = dict(last)
                failed.update(
                    {
                        "connected": False,
                        "complete": False,
                        "error": str(exc)[:160],
                    }
                )
                self.on_state(failed)
            else:
                self.on_state(last)
            self._stop_event.wait(refresh_seconds)
