#!/usr/bin/env bash
# Home Base — the dead-man's switch (PR12, docs/ideas/heartbeat-outside-the-app.md).
#
# The cost ledger (data/sweeps/.runs.jsonl) records every successful sweep and nothing
# ever reads it for ABSENCE — so the whole Mac-local stack can die silently and the first
# signal is an empty morning brief. This script runs on its own LaunchAgent, reads the
# newest ledger timestamp, and past the staleness threshold alerts OUTSIDE the app:
# a flag file on the Desktop (survives an asleep Mac) + a macOS notification.
#
# Deliberately dependency-free — plain bash + system tools, no venv, no node, no claude —
# so it structurally cannot die the same way the sweep pipeline does (the PR1 path-rot,
# PR8 in-app-banner, and PR9 tailnet failure modes this antibody folds in).
#
# Env overrides (tests use all of them; the LaunchAgent uses none):
#   HEARTBEAT_LEDGER · HEARTBEAT_FLAG · HEARTBEAT_THRESHOLD_HOURS · HEARTBEAT_NOTIFIER
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LEDGER="${HEARTBEAT_LEDGER:-$ROOT/data/sweeps/.runs.jsonl}"
FLAG="${HEARTBEAT_FLAG:-$HOME/Desktop/HOMEBASE-STACK-SILENT.txt}"
THRESHOLD_HOURS="${HEARTBEAT_THRESHOLD_HOURS:-36}"
NOTIFIER="${HEARTBEAT_NOTIFIER:-osascript}"

# BSD (macOS) first, GNU fallback so the test suite also runs in cloud sessions.
epoch_from_ts() {
  date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%s 2>/dev/null \
    || date -u -d "$1" +%s 2>/dev/null \
    || true
}

file_mtime() {
  # BSD (macOS) and GNU (Linux CI) stat take different flags. Chaining them with `||` is a
  # trap: GNU treats `stat -f %m FILE` as "-f (filesystem mode) on files '%m' and FILE", and
  # while it exits non-zero it still prints FILE's status ("  File: ...") to stdout — which
  # would flow into the caller's arithmetic and crash it under `set -u`. So capture each
  # form separately and only ever hand back an all-digit epoch (or empty).
  local m
  m="$(stat -f %m "$1" 2>/dev/null || true)"
  case "$m" in ''|*[!0-9]*) m="$(stat -c %Y "$1" 2>/dev/null || true)" ;; esac
  case "$m" in ''|*[!0-9]*) m="" ;; esac
  printf '%s' "$m"
}

now_epoch="$(date +%s)"
last_epoch=""
if [ -f "$LEDGER" ]; then
  # Rows are append-only, so the last line holds the newest "ts" (UTC, Z-suffixed).
  last_ts="$(tail -n 1 "$LEDGER" | sed -n 's/.*"ts"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  [ -n "$last_ts" ] && last_epoch="$(epoch_from_ts "$last_ts")"
  # A mangled row must not fake a death — the file's mtime is still evidence of life.
  [ -n "$last_epoch" ] || last_epoch="$(file_mtime "$LEDGER")"
fi

if [ -n "$last_epoch" ]; then
  age_hours=$(( (now_epoch - last_epoch) / 3600 ))
  if [ "$age_hours" -le "$THRESHOLD_HOURS" ]; then
    # Alive — and a flag left by an earlier death must not keep lying on the Desktop.
    rm -f "$FLAG"
    echo "heartbeat ok — newest ledger row ${age_hours}h old (threshold ${THRESHOLD_HOURS}h)"
    exit 0
  fi
  reason="newest sweep ledger row is ${age_hours}h old (threshold ${THRESHOLD_HOURS}h)"
else
  reason="no sweep ledger at $LEDGER — the stack may never have run here (or the data dir was wiped)"
fi

# The flag file is written FIRST — it's the channel that survives an asleep Mac and a
# dead notification daemon; the banner notification is best-effort on top.
{
  echo "HOME BASE STACK IS SILENT"
  echo "detected: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "$reason"
  echo ""
  echo "check:   launchctl print gui/$(id -u)/com.homebase.sweep"
  echo "         launchctl print gui/$(id -u)/com.homebase.server"
  echo "         tail -20 $ROOT/data/sweeps/logs/launchd.log"
  echo "run now: launchctl kickstart -k gui/$(id -u)/com.homebase.sweep"
  echo ""
  echo "(this file is planted by sweeps/schedule/heartbeat.sh and auto-removed"
  echo " on the first healthy check after the stack recovers)"
} > "$FLAG"

"$NOTIFIER" -e "display notification \"$reason\" with title \"Home Base stack is silent\" sound name \"Basso\"" || true

echo "heartbeat ALERT — $reason (flag: $FLAG)" >&2
exit 1
