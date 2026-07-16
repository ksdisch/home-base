#!/usr/bin/env bash
# Home Base — scheduled-sweep wrapper (M3). launchd runs THIS via the com.homebase.sweep
# LaunchAgent; install-schedule.sh sets the job's PATH (with the nvm bin that holds claude +
# node) in the generated plist, so this script stays machine-agnostic.
#
#   - Hard `unset ANTHROPIC_API_KEY` → always the Claude subscription lane, never API billing.
#   - SWEEP_SKIP_DONE=1 → sweep.sh no-ops topics already written today, so launchd's on-wake
#     re-fire of a completed morning does nothing (and a half-finished one finishes the rest).
#   - All output is appended to data/sweeps/logs/<date>.log (gitignored with the briefs).
#
# Runs fine by hand too: `sweeps/schedule/run-scheduled.sh` (uses your shell's PATH).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$ROOT/data/sweeps/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d).log"

unset ANTHROPIC_API_KEY
export SWEEP_SKIP_DONE=1

{
  echo "===================================================================="
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] scheduled sweep waking up (pid $$)"
  echo "PATH=$PATH"
  if ! command -v claude >/dev/null 2>&1; then
    echo "!! claude not found on PATH — is the LaunchAgent's PATH set to the nvm bin? aborting."
    exit 127
  fi
  cd "$ROOT" || { echo "!! cannot cd to repo root $ROOT"; exit 1; }
  ./sweep.sh
  rc=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] sweep finished (rc=$rc)"
  exit "$rc"
} >>"$LOG" 2>&1
