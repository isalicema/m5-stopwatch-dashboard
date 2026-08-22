from __future__ import annotations

import copy
import json
import threading
import urllib.request
from typing import Any, Dict, List


_MAX_SESSIONS = 12
_MAX_TRANSCRIPTS = 3
_MAX_RESULTS = 6


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _labeled_items(items: Any, label: str, time_key: str) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    output = []
    for value in items:
        if not isinstance(value, dict):
            continue
        item = copy.deepcopy(value)
        title = str(item.get("title") or "")
        item["source"] = label
        item["id"] = "%s:%s" % (label, str(item.get("id") or ""))
        item["title"] = ("%s · %s" % (label, title))[:36]
        item[time_key] = _count(item.get(time_key))
        output.append(item)
    return output


def normalize_peer_snapshot(payload: Dict[str, Any], label: str) -> Dict[str, Any]:
    if payload.get("ok") is not True:
        raise ValueError("peer state response is not healthy")
    output: Dict[str, Any] = {"label": str(label or payload.get("device_label") or "Peer")[:16]}
    for provider in ("codex", "claude"):
        value = payload.get(provider)
        if isinstance(value, dict):
            output[provider] = copy.deepcopy(value)
    return output


def resolve_peer_auth(
    sources: List[Dict[str, Any]], usage_sources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Resolve an existing usage password in memory without duplicating it in config."""
    passwords = {
        str(source.get("id") or ""): source.get("password")
        for source in usage_sources
        if isinstance(source, dict) and source.get("password") is not None
    }
    output = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        item = copy.deepcopy(source)
        auth_source = str(item.get("usage_auth_source") or "")
        if not item.get("api_token") and auth_source in passwords:
            item["api_token"] = passwords[auth_source]
        output.append(item)
    return output


def merge_provider_states(
    local: Dict[str, Any], peers: List[Dict[str, Any]], provider: str, local_label: str
) -> Dict[str, Any]:
    """Merge live activity while keeping local usage and quota fields authoritative."""
    merged = copy.deepcopy(local)
    sources = [(str(local_label or "Air")[:16], local)]
    for peer in peers:
        value = peer.get(provider)
        if isinstance(value, dict):
            sources.append((str(peer.get("label") or "Peer")[:16], value))

    merged["connected"] = any(bool(value.get("connected")) for _, value in sources)
    for key in ("active_count", "waiting_count", "error_count"):
        merged[key] = sum(_count(value.get(key)) for _, value in sources)
    merged["updated_at"] = max(_count(value.get("updated_at")) for _, value in sources)

    sessions = []
    transcripts = []
    results = []
    for label, value in sources:
        sessions.extend(_labeled_items(value.get("sessions"), label, "updated_at"))
        transcripts.extend(_labeled_items(value.get("transcripts"), label, "updated_at"))
        results.extend(_labeled_items(value.get("results"), label, "completed_at"))

    priority = {
        "waiting_approval": 0,
        "working": 1,
        "waiting_input": 2,
        "error": 3,
        "stale": 4,
        "idle": 5,
        "closed": 6,
    }
    sessions.sort(
        key=lambda item: (
            priority.get(str(item.get("status") or "idle"), 5),
            -_count(item.get("updated_at")),
        )
    )
    transcripts.sort(key=lambda item: -_count(item.get("updated_at")))
    results.sort(key=lambda item: -_count(item.get("completed_at")))
    merged["sessions"] = sessions[:_MAX_SESSIONS]
    merged["transcripts"] = transcripts[:_MAX_TRANSCRIPTS]
    merged["results"] = results[:_MAX_RESULTS]
    merged["peer_count"] = max(0, len(sources) - 1)
    return merged


def fetch_peer_state(source: Dict[str, Any], fallback_token: str) -> Dict[str, Any]:
    base_url = str(source.get("base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("peer state source requires base_url")
    token = str(source.get("api_token") or fallback_token)
    if not token:
        raise ValueError("peer state source requires api_token")
    timeout = max(1, int(source.get("timeout_seconds", 3)))
    request = urllib.request.Request(
        base_url + str(source.get("state_path") or "/api/state"),
        headers={"X-Dashboard-Token": token},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("peer state response must be an object")
    return normalize_peer_snapshot(payload, str(source.get("label") or ""))


class PeerStateMonitor(threading.Thread):
    daemon = True

    def __init__(
        self, sources: List[Dict[str, Any]], fallback_token: str, on_state: Any,
        refresh_seconds: int = 2,
    ) -> None:
        super().__init__(name="peer-state-monitor")
        self.sources = sources
        self.fallback_token = fallback_token
        self.on_state = on_state
        self.refresh_seconds = max(1, int(refresh_seconds))
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            current = []
            for source in self.sources:
                if not isinstance(source, dict) or source.get("enabled") is False:
                    continue
                try:
                    current.append(fetch_peer_state(source, self.fallback_token))
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
            # Failed peers are deliberately removed immediately so an old remote
            # task cannot leave the M5 animation running after that Mac disconnects.
            self.on_state(current)
            self._stop_event.wait(self.refresh_seconds)
