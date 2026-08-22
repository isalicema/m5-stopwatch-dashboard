#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a running M5 Dashboard bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()
    url = "http://%s:%d/api/state" % (args.host, args.port)
    request = urllib.request.Request(url, headers={"X-Dashboard-Token": args.token})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            state = json.load(response)
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        print("Bridge check failed: %s" % exc)
        return 1
    ticktick = state.get("ticktick") or {}
    stopwatch = ticktick.get("stopwatch") or {}
    countdown = ticktick.get("countdown") or {}
    codex = state.get("codex") or {}
    ai_usage = state.get("ai_usage") or {}
    print(
        "TickTick: connected=%s stopwatch=%s/%ss countdown=%s/%ss"
        % (
            ticktick.get("connected"),
            stopwatch.get("state"),
            stopwatch.get("elapsed_seconds"),
            countdown.get("state"),
            countdown.get("remaining_seconds"),
        )
    )
    print(
        "Codex: connected=%s active=%s waiting=%s errors=%s"
        % (
            codex.get("connected"),
            codex.get("active_count"),
            codex.get("waiting_count"),
            codex.get("error_count"),
        )
    )
    for limit in codex.get("limits") or []:
        print(
            "Limit %s: %s%% used, reset=%s"
            % (limit.get("id"), limit.get("used_percent"), limit.get("resets_at"))
        )
    print(
        "AI usage: connected=%s complete=%s today_total=%s today_auth=%s channels=%s"
        % (
            ai_usage.get("connected"),
            ai_usage.get("complete"),
            ai_usage.get("today_total_tokens"),
            ai_usage.get("today_authoritative_tokens"),
            ",".join(
                str(item.get("id"))
                for item in ai_usage.get("channels") or []
                if isinstance(item, dict)
            ),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
