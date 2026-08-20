from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


_TOKEN_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


def _path(value: Any, default: str) -> Path:
    return Path(str(value or default)).expanduser().resolve()


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def _usage_total(usage: Dict[str, Any]) -> int:
    return sum(_nonnegative_int(usage.get(field)) for field in _TOKEN_FIELDS)


def collect_local_claude_usage(
    projects_root: Path,
    now: Optional[datetime] = None,
    checkpoint_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Count Claude Code messages once, ignoring duplicated streaming rows."""
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    five_hour_start = current - timedelta(hours=5)
    week_start = current - timedelta(days=7)

    messages: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
    if projects_root.is_dir():
        for path in projects_root.glob("*/*.jsonl"):
            try:
                source = path.open(encoding="utf-8")
            except OSError:
                continue
            with source:
                for line in source:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(row, dict) or row.get("type") != "assistant":
                        continue
                    message = row.get("message")
                    if not isinstance(message, dict):
                        continue
                    usage = message.get("usage")
                    if not isinstance(usage, dict):
                        continue
                    timestamp = _parse_timestamp(row.get("timestamp"))
                    if timestamp is None:
                        continue
                    message_id = message.get("id") or row.get("uuid")
                    if not isinstance(message_id, str) or not message_id:
                        continue
                    previous = messages.get(message_id)
                    if previous is None or timestamp >= previous[0]:
                        messages[message_id] = (timestamp, usage)

    totals = {
        "today_tokens": 0,
        "today_messages": 0,
        "five_hour_tokens": 0,
        "seven_day_tokens": 0,
        "lifetime_tokens": 0,
        "lifetime_messages": len(messages),
        "checkpoint_delta_tokens": 0,
    }
    for timestamp, usage in messages.values():
        tokens = _usage_total(usage)
        totals["lifetime_tokens"] += tokens
        if checkpoint_at is not None and timestamp > checkpoint_at:
            totals["checkpoint_delta_tokens"] += tokens
        if timestamp >= week_start:
            totals["seven_day_tokens"] += tokens
        if timestamp >= five_hour_start:
            totals["five_hour_tokens"] += tokens
        if timestamp >= day_start:
            totals["today_tokens"] += tokens
            totals["today_messages"] += 1
    return totals


def _mapped_limit(limits: Iterable[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    for item in limits:
        if item.get("kind") == kind:
            return {
                "used_pct": item.get("percent"),
                "resets_at": item.get("resets_at"),
            }
    return {}


def build_local_claude_payload(
    source: Dict[str, Any],
    now: Optional[datetime] = None,
    official_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    checkpoint_tokens = _nonnegative_int(source.get("account_lifetime_checkpoint_tokens"))
    checkpoint_at = _parse_timestamp(source.get("account_lifetime_checkpoint_at"))
    usage = collect_local_claude_usage(
        _path(source.get("projects_root"), "~/.claude/projects"),
        current,
        checkpoint_at,
    )
    lifetime_tokens = usage["lifetime_tokens"]
    if checkpoint_tokens > 0 and checkpoint_at is not None:
        # Quota percentages do not provide a lifetime token total. Continue from
        # the configured account-wide checkpoint, then add only newer local
        # messages. Checkpoint values belong in the untracked local config.
        lifetime_tokens = checkpoint_tokens + usage["checkpoint_delta_tokens"]
    official = official_payload if official_payload is not None else {}
    limits = official.get("limits") if isinstance(official.get("limits"), list) else []
    safe_limits = [item for item in limits if isinstance(item, dict)]
    return {
        "generated_at": current.isoformat(),
        "claude": {
            "today": {
                "total_tokens": usage["today_tokens"],
                "msg_count": usage["today_messages"],
            },
            "total": {
                "total_tokens": lifetime_tokens,
                "msg_count": usage["lifetime_messages"],
            },
            "windows": {
                "five_hours": {"used_tokens": usage["five_hour_tokens"]},
                "seven_days": {"used_tokens": usage["seven_day_tokens"]},
            },
            "official_usage": {
                "available": bool(safe_limits),
                "limits": safe_limits,
                "five_hour": _mapped_limit(safe_limits, "session"),
                "seven_day": _mapped_limit(safe_limits, "weekly_all"),
            },
        },
    }
