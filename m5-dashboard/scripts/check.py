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
    printer = state.get("printer") or {}
    codex = state.get("codex") or {}
    print(
        "P2S: connected=%s state=%s progress=%s%% remaining=%sm"
        % (
            printer.get("connected"),
            printer.get("state_label"),
            printer.get("progress"),
            printer.get("remaining_min"),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
