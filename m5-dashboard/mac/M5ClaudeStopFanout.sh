#!/bin/bash

# Claude Desktop 2.1.237 has been observed invoking only the first command in
# a matching Stop handler list. Consume the product payload once, then deliver
# the exact same bytes to both the existing sound command and M5 Dashboard.
set +e

PEON_COMMAND="${1:-}"
M5_NOTIFY="${2:-}"
PAYLOAD="$(/bin/cat)"

if [ -n "$PEON_COMMAND" ]; then
  printf '%s' "$PAYLOAD" | /bin/bash -lc "$PEON_COMMAND" &
  PEON_PID=$!
else
  PEON_PID=""
fi

if [ -n "$M5_NOTIFY" ] && [ -x "$M5_NOTIFY" ]; then
  "$M5_NOTIFY" "$PAYLOAD" &
  M5_PID=$!
else
  M5_PID=""
fi

if [ -n "$M5_PID" ]; then
  wait "$M5_PID" 2>/dev/null || true
fi
if [ -n "$PEON_PID" ]; then
  wait "$PEON_PID" 2>/dev/null || true
fi

exit 0
