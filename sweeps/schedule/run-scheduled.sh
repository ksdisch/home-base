#!/usr/bin/env bash
# Home Base — scheduled-sweep wrapper (M3). launchd runs THIS via the com.homebase.sweep
# LaunchAgent; install-schedule.sh sets the job's PATH (with the nvm bin that holds claude +
# node) in the generated plist, so this script stays machine-agnostic.
#
#   - Hard unset of every lane-switching env var (API key, auth token, Bedrock/Vertex
#     switches, base-URL override) → always the Claude subscription lane, never API billing.
#   - SWEEP_SKIP_DONE=1 → sweep.sh no-ops topics already written today, so launchd's on-wake
#     re-fire of a completed morning does nothing (and a half-finished one finishes the rest).
#   - A network preflight (see wait_for_network) before the sweep is allowed to start.
#   - All output is appended to data/sweeps/logs/<date>.log (gitignored with the briefs).
#
# Runs fine by hand too: `sweeps/schedule/run-scheduled.sh` (uses your shell's PATH).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$ROOT/data/sweeps/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d).log"

# Bug #10: the claude CLI reads more than the API key to pick a billing lane — scrub
# the auth token, Bedrock/Vertex switches, and any base-URL override too.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX
export SWEEP_SKIP_DONE=1

# docs/ideas/sweep-network-preflight.md — the wake-before-network race. The 06:00 pmset wake
# starts this script in the seconds before Wi-Fi re-associates; every topic's claude call then
# fails, and because the scheduled fire technically HAPPENED, launchd's missed-time on-wake
# re-fire never triggers. The brief stays empty until Kyle sweeps by hand — on exactly the
# sleep-wake mornings the unattended pipeline exists for.
#
# The probe is HTTPS on purpose: a captive portal can answer a plain http:// GET with its own
# 200 and look like the internet, but it cannot complete someone else's TLS handshake. Any
# reply from the real host counts (no --fail) — a 4xx still proves we are online.
NET_PROBE_URL="${SWEEP_NET_PROBE_URL:-https://news.google.com/}"
NET_WAIT_SECONDS="${SWEEP_NET_WAIT_SECONDS:-90}"
NET_PROBE_INTERVAL="${SWEEP_NET_PROBE_INTERVAL:-5}"

wait_for_network() {
  local waited=0
  while true; do
    if curl -s -m 3 -o /dev/null "$NET_PROBE_URL"; then
      [ "$waited" -gt 0 ] && echo "network came up after ${waited}s"
      return 0
    fi
    [ "$waited" -ge "$NET_WAIT_SECONDS" ] && return 1
    echo "waiting for network… (${waited}s of ${NET_WAIT_SECONDS}s, probing $NET_PROBE_URL)"
    sleep "$NET_PROBE_INTERVAL"
    waited=$((waited + NET_PROBE_INTERVAL))
  done
}

{
  echo "===================================================================="
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] scheduled sweep waking up (pid $$)"
  echo "PATH=$PATH"
  if ! command -v claude >/dev/null 2>&1; then
    echo "!! claude not found on PATH — is the LaunchAgent's PATH set to the nvm bin? aborting."
    exit 127
  fi
  cd "$ROOT" || { echo "!! cannot cd to repo root $ROOT"; exit 1; }
  if ! wait_for_network; then
    # Abort BEFORE sweep.sh so no topic state is written: SWEEP_SKIP_DONE=1 then lets the
    # next wake — or a sweep triggered from the phone — finish the day's missing topics.
    echo "!! network never came up within ${NET_WAIT_SECONDS}s — aborting before the sweep."
    exit 69
  fi
  ./sweep.sh
  rc=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] sweep finished (rc=$rc)"
  exit "$rc"
} >>"$LOG" 2>&1
