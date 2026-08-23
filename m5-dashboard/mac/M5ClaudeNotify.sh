#!/bin/bash

# Feed Claude Code's product-level Stop hook into M5 Dashboard. This handler
# runs beside peon-ping and intentionally emits no output or sound of its own.
set +e

PAYLOAD="${1:-}"
if [ -z "$PAYLOAD" ] && [ ! -t 0 ]; then
  PAYLOAD="$(/bin/cat)"
fi

M5_CLAUDE_HOOK="${M5_DASH_CLAUDE_HOOK:-$HOME/Library/Application Support/M5Dashboard/app/bridge/claude_hook.py}"

if [ -n "$PAYLOAD" ] && [ -f "$M5_CLAUDE_HOOK" ]; then
  printf '%s' "$PAYLOAD" | /usr/bin/python3 "$M5_CLAUDE_HOOK" >/dev/null 2>&1 || true
fi

exit 0
