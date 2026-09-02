from __future__ import annotations

import http.cookiejar
import json
import os
import queue
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .local_activity import LocalCodexActivity
from .transcript import LocalCodexTranscripts


class AppServerClient:
    def __init__(self, binary: str) -> None:
        self.binary = binary
        self.process: Optional[subprocess.Popen[str]] = None
        self._next_id = 1
        self._pending: Dict[int, queue.Queue[Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._reader: Optional[threading.Thread] = None

    def start(self) -> None:
        self.process = subprocess.Popen(
            [self.binary, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_loop, name="codex-app-server-reader", daemon=True)
        self._reader.start()
        self.request(
            "initialize",
            {
                "clientInfo": {"name": "m5_dashboard", "title": "M5 Dashboard", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            },
        )
        self.notify("initialized", {})

    def close(self) -> None:
        process = self.process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

    def _read_loop(self) -> None:
        process = self.process
        if not process or not process.stdout:
            return
        for line in process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            request_id = message.get("id")
            if isinstance(request_id, int):
                with self._lock:
                    target = self._pending.get(request_id)
                if target:
                    target.put(message)

    def _write(self, message: Dict[str, Any]) -> None:
        process = self.process
        if not process or process.poll() is not None or not process.stdin:
            raise ConnectionError("Codex App Server is not running")
        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def notify(self, method: str, params: Dict[str, Any]) -> None:
        self._write({"method": method, "params": params})

    def request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Any:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            target: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
            self._pending[request_id] = target
        message: Dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            message["params"] = params
        try:
            self._write(message)
            response = target.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("Codex request timed out: %s" % method) from exc
        finally:
            with self._lock:
                self._pending.pop(request_id, None)
        if response.get("error"):
            raise RuntimeError("Codex %s failed: %s" % (method, response["error"]))
        return response.get("result")


def load_hook_sessions(path: str) -> Dict[str, Dict[str, Any]]:
    expanded = Path(os.path.expanduser(path))
    try:
        value = json.loads(expanded.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    sessions = value.get("sessions") if isinstance(value, dict) else None
    return sessions if isinstance(sessions, dict) else {}


def hook_completion_results(
    hooks: Dict[str, Dict[str, Any]],
    threads: List[Dict[str, Any]],
    expose_titles: bool,
    limit: int = 6,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Expose only product-level Codex notify completions, never JSONL guesses."""
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    day_start = datetime.combine(current.date(), datetime_time.min, tzinfo=current.tzinfo).timestamp()
    by_id: Dict[str, Dict[str, Any]] = {}
    for thread in threads:
        for key in (thread.get("id"), thread.get("sessionId")):
            if key:
                by_id[str(key)] = thread
    output = []
    for index, (session_id, session) in enumerate(hooks.items(), 1):
        completed_at = int(session.get("completed_at") or 0)
        if completed_at < day_start:
            continue
        thread = by_id.get(session_id, {})
        output.append(
            {
                "id": str(session.get("completion_id") or session_id)[-32:],
                "title": _safe_title(thread, expose_titles, index),
                "completed_at": completed_at,
            }
        )
    output.sort(key=lambda item: int(item["completed_at"]), reverse=True)
    return output[: max(0, int(limit))]


_USAGE_FIELDS = (
    "total_tokens",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
)


def collect_local_daily_usage(
    session_root: str = "~/.codex/sessions", now: Optional[datetime] = None
) -> Dict[str, int]:
    """Sum this Mac's token deltas since local midnight without double-counting snapshots."""
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    day_start = datetime.combine(current.date(), datetime_time.min, tzinfo=current.tzinfo)
    day_end = day_start + timedelta(days=1)
    totals = {field: 0 for field in _USAGE_FIELDS}
    session_count = 0
    root = Path(os.path.expanduser(session_root))
    if not root.is_dir():
        return {"today_" + field: value for field, value in totals.items()} | {
            "today_sessions": 0
        }

    for path in root.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime < day_start.timestamp():
                continue
        except OSError:
            continue
        baseline = {field: 0 for field in _USAGE_FIELDS}
        latest: Optional[Dict[str, int]] = None
        try:
            with path.open(encoding="utf-8") as source:
                for line in source:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = row.get("payload") if isinstance(row, dict) else None
                    if row.get("type") != "event_msg" or not isinstance(payload, dict):
                        continue
                    if payload.get("type") != "token_count":
                        continue
                    info = payload.get("info")
                    usage = info.get("total_token_usage") if isinstance(info, dict) else None
                    stamp = row.get("timestamp")
                    if not isinstance(usage, dict) or not isinstance(stamp, str):
                        continue
                    try:
                        occurred_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if occurred_at.tzinfo is None:
                        occurred_at = occurred_at.replace(tzinfo=current.tzinfo)
                    values = {field: int(usage.get(field) or 0) for field in _USAGE_FIELDS}
                    if occurred_at < day_start:
                        baseline = values
                    elif occurred_at < day_end:
                        latest = values
        except (OSError, UnicodeError):
            continue
        if latest is None:
            continue
        session_count += 1
        for field in _USAGE_FIELDS:
            totals[field] += max(0, latest[field] - baseline[field])

    return {"today_" + field: value for field, value in totals.items()} | {
        "today_sessions": session_count
    }


def normalize_peer_daily_usage(
    payload: Dict[str, Any], now: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """Normalize a peer usage-dashboard response only when it belongs to today."""
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    generated_at = payload.get("generated_at")
    today = payload.get("today")
    if not isinstance(generated_at, str) or not isinstance(today, dict):
        return None
    try:
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=current.tzinfo)
    if generated.astimezone(current.tzinfo).date() != current.date():
        return None

    def number(name: str, fallback: Optional[str] = None) -> int:
        value = today.get(name)
        if value is None and fallback:
            value = today.get(fallback)
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    return {
        "today_total_tokens": number("raw_total_tokens", "total_tokens"),
        "today_input_tokens": number("input_tokens"),
        "today_cached_input_tokens": number("cached_input_tokens"),
        "today_output_tokens": number("output_tokens"),
        "today_sessions": number("thread_count"),
        "generated_at": generated.timestamp(),
        "local_date": current.date().isoformat(),
    }


def fetch_peer_stats(source: Dict[str, Any]) -> Dict[str, Any]:
    base_url = str(source.get("base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("peer usage source requires base_url")
    timeout = max(1, int(source.get("timeout_seconds", 5)))
    jar = http.cookiejar.CookieJar()
    # Peer dashboards are LAN services. Never send their password or traffic
    # through the Mac's configured HTTP proxy.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(jar),
    )
    password = source.get("password")
    if password is not None:
        login_path = str(source.get("login_path") or "/")
        parameter = str(source.get("password_parameter") or "p")
        query = urllib.parse.urlencode({parameter: str(password)})
        opener.open(base_url + login_path + "?" + query, timeout=timeout).read()
    stats_path = str(source.get("stats_path") or "/api/stats")
    with opener.open(base_url + stats_path, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("peer usage response must be an object")
    return payload


def fetch_peer_daily_usage(
    source: Dict[str, Any], now: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    return normalize_peer_daily_usage(fetch_peer_stats(source), now)


def merge_daily_usage(
    local_usage: Dict[str, Any], peer_usage: List[Dict[str, Any]]
) -> Dict[str, int]:
    merged = {
        "today_" + field: max(0, int(local_usage.get("today_" + field) or 0))
        for field in _USAGE_FIELDS
    }
    merged["today_sessions"] = max(0, int(local_usage.get("today_sessions") or 0))
    for peer in peer_usage:
        for field in _USAGE_FIELDS:
            key = "today_" + field
            merged[key] += max(0, int(peer.get(key) or 0))
        merged["today_sessions"] += max(0, int(peer.get("today_sessions") or 0))
    merged["today_local_tokens"] = max(0, int(local_usage.get("today_total_tokens") or 0))
    merged["today_peer_tokens"] = sum(
        max(0, int(peer.get("today_total_tokens") or 0)) for peer in peer_usage
    )
    merged["today_peer_count"] = len(peer_usage)
    return merged


def _safe_title(thread: Dict[str, Any], expose: bool, fallback_index: int) -> str:
    if expose and thread.get("name"):
        return str(thread["name"])[:36]
    return "Codex %d" % fallback_index


def _thread_status_type(thread: Dict[str, Any]) -> str:
    status = thread.get("status")
    if isinstance(status, dict):
        return str(status.get("type") or "")
    return str(status or "")


def apply_thread_titles(
    transcripts: List[Dict[str, Any]], threads: List[Dict[str, Any]], expose: bool
) -> List[Dict[str, Any]]:
    """Prefer Codex's user-facing task title over the first prompt preview."""
    if not expose:
        return transcripts
    titles: Dict[str, str] = {}
    child_ids: set[str] = set()
    for thread in threads:
        is_child = bool(thread.get("parentThreadId"))
        title = str(thread.get("name") or "").strip()
        for key in (thread.get("id"), thread.get("sessionId")):
            if key:
                normalized = str(key)
                if is_child:
                    child_ids.update({normalized, normalized[-8:]})
                elif title:
                    titles[normalized] = title
                    titles[normalized[-8:]] = title
    output = []
    for transcript in transcripts:
        item = dict(transcript)
        task_id = str(item.get("id") or "")
        if task_id in child_ids or task_id[-8:] in child_ids:
            continue
        title = titles.get(task_id) or titles.get(task_id[-8:])
        if title:
            item["title"] = title[:36]
        output.append(item)
    return output


def merge_sessions(
    hooks: Dict[str, Dict[str, Any]],
    threads: List[Dict[str, Any]],
    expose_titles: bool,
    stale_seconds: int,
    waiting_stale_seconds: Optional[int] = None,
) -> List[Dict[str, Any]]:
    now = int(time.time())
    waiting_ttl = max(
        60,
        int(stale_seconds if waiting_stale_seconds is None else waiting_stale_seconds),
    )
    by_id: Dict[str, Dict[str, Any]] = {}
    for thread in threads:
        for key in (thread.get("id"), thread.get("sessionId")):
            if key:
                by_id[str(key)] = thread
    output = []
    for index, (session_id, session) in enumerate(
        sorted(hooks.items(), key=lambda item: int(item[1].get("last_event_at", 0)), reverse=True), 1
    ):
        status = str(session.get("status") or "idle")
        last_event_at = int(session.get("last_event_at") or 0)
        if status in ("working", "waiting_approval") and now - last_event_at > stale_seconds:
            status = "stale"
        thread = by_id.get(session_id, {})
        if thread.get("parentThreadId"):
            continue
        if status == "waiting_input":
            # A question-like final response is only actionable while the task
            # is still loaded by Codex and the receipt is recent. Persisted
            # hook files otherwise resurrect old prompts after Bridge restarts.
            runtime_status = _thread_status_type(thread)
            expired = last_event_at <= 0 or now - last_event_at > waiting_ttl
            inactive = not thread or runtime_status in {"notLoaded", "systemError"}
            if expired or inactive:
                status = "idle"
        output.append(
            {
                "id": session_id[-8:],
                "title": _safe_title(thread, expose_titles, index),
                "status": status,
                "model": str(session.get("model") or ""),
                "started_at": int(session.get("turn_started_at") or 0),
                "updated_at": last_event_at,
            }
        )
    priority = {
        "waiting_approval": 0,
        "working": 1,
        "waiting_input": 2,
        "error": 3,
        "stale": 4,
        "idle": 5,
        "closed": 6,
    }
    output.sort(key=lambda row: (priority.get(str(row["status"]), 5), -int(row["updated_at"])))
    return output[:12]


def format_rate_limits(raw_limits: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten Codex primary/secondary quota windows without changing primary IDs."""
    output: List[Dict[str, Any]] = []
    for limit_id, value in raw_limits.items():
        if not isinstance(value, dict):
            continue
        for slot in ("primary", "secondary"):
            window = value.get(slot)
            if not isinstance(window, dict) or not window:
                continue
            output.append(
                {
                    "id": str(limit_id) if slot == "primary" else "%s:%s" % (limit_id, slot),
                    "name": value.get("limitName") or str(limit_id),
                    "slot": slot,
                    "used_percent": window.get("usedPercent"),
                    "window_minutes": window.get("windowDurationMins"),
                    "resets_at": window.get("resetsAt"),
                }
            )
    return output


class CodexMonitor(threading.Thread):
    daemon = True

    def __init__(self, config: Dict[str, Any], on_state: Any) -> None:
        super().__init__(name="codex-monitor")
        self.config = config
        self.on_state = on_state
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._client: Optional[AppServerClient] = None
        self._local_activity = LocalCodexActivity(
            str(config.get("session_root") or "~/.codex/sessions"),
            int(config.get("local_activity_stale_seconds", 1800)),
        )
        self._transcripts = LocalCodexTranscripts(
            str(config.get("session_root") or "~/.codex/sessions"),
            int(config.get("local_activity_stale_seconds", 1800)),
        )

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._client:
            self._client.close()

    def wake(self) -> Dict[str, Any]:
        """Interrupt the normal polling delay after a product completion hook."""
        self._wake_event.set()
        return {"provider": "codex", "woken": True}

    def _wait(self, seconds: float) -> None:
        self._wake_event.wait(seconds)
        self._wake_event.clear()

    def _binary(self) -> str:
        configured = str(self.config.get("codex_binary") or "codex")
        if os.path.isfile(configured) and os.access(configured, os.X_OK):
            return configured
        return "codex"

    def _collect(self) -> None:
        client = AppServerClient(self._binary())
        self._client = client
        client.start()
        usage_refresh = max(15, int(self.config.get("usage_refresh_seconds", 60)))
        thread_refresh = max(2, int(self.config.get("threads_refresh_seconds", 5)))
        if self.config.get("expose_transcript", False):
            thread_refresh = max(
                1,
                min(thread_refresh, int(self.config.get("transcript_refresh_seconds", 1))),
            )
        next_usage = 0.0
        limits: Dict[str, Any] = {}
        usage: Dict[str, Any] = {}
        threads: List[Dict[str, Any]] = []
        peer_usage_cache: Dict[str, Dict[str, Any]] = {}
        usage_error = ""
        while not self._stop_event.is_set():
            now_mono = time.monotonic()
            if now_mono >= next_usage:
                try:
                    fresh_limits = client.request("account/rateLimits/read") or {}
                    if fresh_limits:
                        limits = fresh_limits
                    usage_error = ""
                except (OSError, ConnectionError, TimeoutError, RuntimeError) as exc:
                    usage_error = str(exc)[:160]
                try:
                    raw_usage = client.request("account/usage/read") or {}
                except (OSError, ConnectionError, TimeoutError, RuntimeError) as exc:
                    raw_usage = {}
                    usage_error = str(exc)[:160]
                local_usage = collect_local_daily_usage(
                    str(self.config.get("session_root") or "~/.codex/sessions")
                )
                current = datetime.now().astimezone()
                for index, source in enumerate(self.config.get("peer_usage_sources") or []):
                    if not isinstance(source, dict) or source.get("enabled") is False:
                        continue
                    source_id = str(source.get("id") or source.get("base_url") or index)
                    try:
                        peer = fetch_peer_daily_usage(source, current)
                    except (OSError, ValueError, json.JSONDecodeError):
                        continue
                    if peer is not None:
                        peer_usage_cache[source_id] = peer
                today_key = current.date().isoformat()
                peers = [
                    peer
                    for peer in peer_usage_cache.values()
                    if peer.get("local_date") == today_key
                ]
                daily_usage = merge_daily_usage(local_usage, peers)
                summary = raw_usage.get("summary") or {}
                usage = {
                    "today_tokens": daily_usage["today_total_tokens"],
                    "today_input_tokens": daily_usage["today_input_tokens"],
                    "today_cached_input_tokens": daily_usage["today_cached_input_tokens"],
                    "today_output_tokens": daily_usage["today_output_tokens"],
                    "today_sessions": daily_usage["today_sessions"],
                    "today_local_tokens": daily_usage["today_local_tokens"],
                    "today_peer_tokens": daily_usage["today_peer_tokens"],
                    "today_peer_count": daily_usage["today_peer_count"],
                    "lifetime_tokens": summary.get("lifetimeTokens"),
                    "peak_daily_tokens": summary.get("peakDailyTokens"),
                    "longest_turn_sec": summary.get("longestRunningTurnSec"),
                    "current_streak_days": summary.get("currentStreakDays"),
                }
                next_usage = now_mono + usage_refresh
            result = client.request("thread/list", {"limit": 100}) or {}
            threads = result.get("data") or []
            hook_sessions = load_hook_sessions(str(self.config["hook_state_path"]))
            sessions = merge_sessions(
                hook_sessions,
                threads,
                bool(
                    self.config.get("expose_titles", False)
                    or self.config.get("expose_transcript", False)
                ),
                int(self.config.get("working_stale_seconds", 21600)),
                int(self.config.get("waiting_input_stale_seconds", 21600)),
            )
            # Desktop Codex writes task_started/task_complete into its local
            # JSONL even when lifecycle hooks do not fire. Keep using that
            # source to fill the live working count; completion feedback is
            # deliberately handled only by the product-level notify receipt.
            hook_working = sum(s["status"] == "working" for s in sessions)
            for index in range(max(0, self._local_activity.active_count() - hook_working)):
                sessions.append(
                    {
                        "id": "local-%d" % (index + 1),
                        "title": "当前 Codex",
                        "status": "working",
                        "model": "",
                        "started_at": 0,
                        "updated_at": int(time.time()),
                    }
                )
            raw_limits = limits.get("rateLimitsByLimitId") or {}
            if not raw_limits and limits.get("rateLimits"):
                raw_limits = {str(limits["rateLimits"].get("limitId") or "codex"): limits["rateLimits"]}
            formatted_limits = format_rate_limits(raw_limits)
            expose_transcript = bool(self.config.get("expose_transcript", False))
            transcripts = apply_thread_titles(
                self._transcripts.snapshots(expose_transcript),
                threads,
                expose_transcript,
            )
            results = hook_completion_results(
                hook_sessions,
                threads,
                bool(self.config.get("expose_titles", False)),
            )
            active = {"working"}
            waiting = {"waiting_approval", "waiting_input"}
            self.on_state(
                {
                    "connected": True,
                    "active_count": sum(s["status"] in active for s in sessions),
                    "waiting_count": sum(s["status"] in waiting for s in sessions),
                    "error_count": sum(s["status"] in {"error", "stale"} for s in sessions),
                    "sessions": sessions,
                    "transcripts": transcripts,
                    "results": results,
                    "limits": formatted_limits,
                    "usage": usage,
                    "updated_at": int(time.time()),
                    "error": usage_error,
                }
            )
            self._wait(thread_refresh)

    def run(self) -> None:
        delay = 2
        while not self._stop_event.is_set():
            try:
                self._collect()
                delay = 2
            except (OSError, ConnectionError, TimeoutError, RuntimeError, KeyError) as exc:
                self.on_state(
                    {
                        "connected": False,
                        "active_count": 0,
                        "waiting_count": 0,
                        "error_count": 1,
                        "sessions": [],
                        "transcripts": self._transcripts.snapshots(
                            bool(self.config.get("expose_transcript", False))
                        ),
                        "results": hook_completion_results(
                            load_hook_sessions(str(self.config.get("hook_state_path") or "")),
                            [],
                            False,
                        ),
                        "limits": [],
                        "usage": {},
                        "updated_at": int(time.time()),
                        "error": str(exc)[:160],
                    }
                )
                if self._client:
                    self._client.close()
                    self._client = None
                self._wait(delay)
                delay = min(delay * 2, 30)
