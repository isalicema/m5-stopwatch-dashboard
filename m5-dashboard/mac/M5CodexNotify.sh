#!/bin/bash

# Feed Codex's product-level completed-turn notification into M5 Dashboard.
# This helper is intentionally silent and safe to append to an existing notify
# chain such as peon-ping.
set +e

PAYLOAD="${1:-}"
if [ -z "$PAYLOAD" ] && [ ! -t 0 ]; then
  PAYLOAD="$(/bin/cat)"
fi

M5_CODEX_HOOK="${M5_DASH_CODEX_HOOK:-$HOME/Library/Application Support/M5Dashboard/app/bridge/codex_hook.py}"

if [ -n "$PAYLOAD" ] && [ -f "$M5_CODEX_HOOK" ]; then
  printf '%s' "$PAYLOAD" | /usr/bin/python3 "$M5_CODEX_HOOK" >/dev/null 2>&1 || true
fi

exit 0
