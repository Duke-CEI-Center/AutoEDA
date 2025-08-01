#!/usr/bin/env bash
## restart_servers.sh
## kill any existing MCP server processes, then (re)launch each one on *its own*
## high-range port to avoid conflicts across users / machines.

PORT_SYNTH=13333
PORT_PLACEMENT=13340
PORT_CTS=13338
PORT_ROUTE=13341

PYTHON=${PYTHON:-python3}      

_kill()   { pkill -f "$1" 2>/dev/null || true; }
_launch() { nohup "$PYTHON" "$1" --port "$2" >/dev/null 2>&1 & }

_kill unified_placement_server.py
_kill cts_server.py
_kill unified_route_save_server.py
_kill synth_server.py

_launch server/synth_server.py           "$PORT_SYNTH"
_launch server/unified_placement_server.py      "$PORT_PLACEMENT"
_launch server/cts_server.py            "$PORT_CTS"
_launch server/unified_route_save_server.py          "$PORT_ROUTE"

echo "MCP servers restarted on ports:"
printf "   synth=%s  place=%s  cts=%s  route=%s\n" \
       "$PORT_SYNTH" "$PORT_PLACEMENT" "$PORT_CTS" "$PORT_ROUTE"
