#!/usr/bin/env bash
# Home Base — always-on server wrapper (M6). launchd runs THIS via the com.homebase.server
# LaunchAgent (RunAtLoad + KeepAlive), so the hub is up on :8000 whenever the Mac is — no
# terminal. Serves the API and, once `make build` has emitted frontend/dist, the whole
# frontend on the same port (see backend/app/main.py).
#
# Runs fine by hand too: serve/run-server.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND="$ROOT/backend"
PORT="${HOMEBASE_PORT:-8000}"

if [ ! -x "$BACKEND/.venv/bin/python" ]; then
  echo "!! backend venv missing — run 'make setup' first (launchd will keep retrying)." >&2
  exit 1
fi

# Bind loopback only: the phone reaches the hub through `tailscale serve` (HTTPS on the
# tailnet), so nothing listens on LAN or public interfaces. No --reload — this is prod.
cd "$BACKEND"
exec ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
