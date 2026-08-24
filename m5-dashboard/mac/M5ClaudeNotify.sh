#!/bin/bash

# Feed Claude Code's product-level Stop hook into M5 Dashboard. This handler
# runs beside peon-ping and intentionally emits no output or sound of its own.
set +e

PAYLOAD="${1:-}"
PAYLOAD_SOURCE="argument"
if [ -z "$PAYLOAD" ] && [ ! -t 0 ]; then
  PAYLOAD="$(/bin/cat)"
  PAYLOAD_SOURCE="stdin"
elif [ -z "$PAYLOAD" ]; then
  PAYLOAD_SOURCE="none"
fi

M5_CLAUDE_HOOK="${M5_DASH_CLAUDE_HOOK:-$HOME/Library/Application Support/M5Dashboard/app/bridge/claude_hook.py}"
M5_CLAUDE_DIAGNOSTIC_LOG="${M5_DASH_CLAUDE_DIAGNOSTIC_LOG:-$HOME/Library/Application Support/M5Dashboard/logs/claude-hook-diagnostic.log}"

# Content-free receipt: never write the payload, prompt, transcript, or title.
# This distinguishes "Claude never invoked the hook" from downstream failures.
/bin/mkdir -p "$(/usr/bin/dirname "$M5_CLAUDE_DIAGNOSTIC_LOG")" 2>/dev/null || true
printf '%s invoked source=%s chars=%s\n' \
  "$(/bin/date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  "$PAYLOAD_SOURCE" "${#PAYLOAD}" >> "$M5_CLAUDE_DIAGNOSTIC_LOG" 2>/dev/null || true

if [ -n "$PAYLOAD" ] && [ -f "$M5_CLAUDE_HOOK" ]; then
  printf '%s' "$PAYLOAD" | /usr/bin/python3 "$M5_CLAUDE_HOOK" >/dev/null 2>&1 || true
fi

exit 0
