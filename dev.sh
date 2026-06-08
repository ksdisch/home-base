#!/usr/bin/env bash
# One command to boot the Learning Hub: FastAPI (:8000) + Vite (:5173) together.
# Bootstraps the backend venv (prefers python3.12) and frontend deps on first run.
#   ./dev.sh          # bootstrap (if needed) + run both
#   ./dev.sh setup    # bootstrap only, don't run
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

pick_python() {
  if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"; return; fi
  for c in python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1; then echo "$c"; return; fi
  done
  echo "python3"
}

bootstrap() {
  local py; py="$(pick_python)"
  if [ ! -d "$BACKEND/.venv" ]; then
    echo "› creating backend venv with $py"
    "$py" -m venv "$BACKEND/.venv"
  fi
  echo "› installing backend deps"
  "$BACKEND/.venv/bin/python" -m pip install -q --upgrade pip >/dev/null 2>&1 || true
  "$BACKEND/.venv/bin/python" -m pip install -q -r "$BACKEND/requirements.txt"

  # Reinstall frontend deps when node_modules is missing OR stale. We stamp a
  # marker after a successful install and compare the manifest/lockfile against
  # it — comparing against node_modules itself is unreliable because npm rewrites
  # package-lock.json a moment AFTER populating node_modules, which would force a
  # reinstall on every boot. Without this, a dep added to package.json after the
  # last install silently never installs and the dev server crashes (e.g.
  # vite.config.ts importing an uninstalled 'vitest').
  local stamp="$FRONTEND/node_modules/.deps-stamp"
  if [ ! -d "$FRONTEND/node_modules" ] \
     || [ ! -f "$stamp" ] \
     || [ "$FRONTEND/package.json" -nt "$stamp" ] \
     || [ "$FRONTEND/package-lock.json" -nt "$stamp" ]; then
    echo "› installing frontend deps"
    (cd "$FRONTEND" && npm install --no-fund --no-audit)
    touch "$stamp"
  fi
}

bootstrap

if [ "${1:-}" = "setup" ]; then
  echo "› setup complete. run ./dev.sh to start."
  exit 0
fi

pids=()
cleanup() {
  echo
  echo "› shutting down"
  for pid in "${pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

echo "› backend  → http://localhost:8000   (API under /api)"
( cd "$BACKEND" && exec ./.venv/bin/python -m uvicorn app.main:app --reload --port 8000 ) &
pids+=($!)

echo "› frontend → http://localhost:5173   ← open this"
( cd "$FRONTEND" && exec npm run dev -- --host ) &
pids+=($!)

wait
