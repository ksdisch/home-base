#!/usr/bin/env bash
# Home Base — install/uninstall the scheduled LaunchAgents: the daily sweep (M3) and the
# heartbeat dead-man's switch (PR12, fixed 09:00 — it checks that the 06:00 sweep left a
# fresh ledger row and alerts outside the app when the stack has gone silent).
#
#   sweeps/schedule/install-schedule.sh            # sweep at 06:00 local + heartbeat at 09:00
#   sweeps/schedule/install-schedule.sh 07:15      # sweep at a custom time (heartbeat stays 09:00)
#   sweeps/schedule/install-schedule.sh status     # show launchctl state for both
#   sweeps/schedule/install-schedule.sh uninstall  # remove both
#
# Fills the plist templates with this machine's repo root, the nvm bin dir holding `claude`
# (sweep only — the heartbeat is deliberately dependency-free), and the times; writes them to
# ~/Library/LaunchAgents; (re)bootstraps them into your GUI session.
# Idempotent — safe to re-run to change the time or after moving the repo.
set -euo pipefail

LABEL="com.homebase.sweep"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEMPLATE="$SCRIPT_DIR/com.homebase.sweep.plist.template"
WRAPPER="$SCRIPT_DIR/run-scheduled.sh"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$ROOT/data/sweeps/logs"
DOMAIN="gui/$(id -u)"

HB_LABEL="com.homebase.heartbeat"
HB_TEMPLATE="$SCRIPT_DIR/com.homebase.heartbeat.plist.template"
HB_SCRIPT="$SCRIPT_DIR/heartbeat.sh"
HB_PLIST_DEST="$HOME/Library/LaunchAgents/$HB_LABEL.plist"
HB_HOUR=9; HB_MINUTE=0

uninstall() {
  for l in "$LABEL" "$HB_LABEL"; do
    launchctl bootout "$DOMAIN/$l" 2>/dev/null && echo "booted out $l" || echo "$l was not loaded"
    p="$HOME/Library/LaunchAgents/$l.plist"
    if [ -f "$p" ]; then rm -f "$p" && echo "removed $p"; fi
  done
}

cmd="${1:-install}"
case "$cmd" in
  uninstall|remove) uninstall; exit 0 ;;
  status)
    echo "domain: $DOMAIN"
    for l in "$LABEL" "$HB_LABEL"; do
      p="$HOME/Library/LaunchAgents/$l.plist"
      echo "-- $l   plist: $p $( [ -f "$p" ] && echo '(present)' || echo '(absent)')"
      launchctl print "$DOMAIN/$l" 2>/dev/null | grep -iE 'state =|program =|runatload|nextfiredate' \
        || echo "   (not loaded — run install-schedule.sh)"
    done
    exit 0 ;;
  install) TIME="06:00" ;;
  *)
    if printf '%s' "$cmd" | grep -qE '^([01][0-9]|2[0-3]):[0-5][0-9]$'; then TIME="$cmd"
    else echo "usage: install-schedule.sh [HH:MM | status | uninstall]"; exit 2; fi ;;
esac

[ -f "$TEMPLATE" ] || { echo "!! template missing: $TEMPLATE" >&2; exit 1; }
[ -f "$WRAPPER" ]  || { echo "!! wrapper missing: $WRAPPER" >&2; exit 1; }
[ -f "$HB_TEMPLATE" ] || { echo "!! template missing: $HB_TEMPLATE" >&2; exit 1; }
[ -f "$HB_SCRIPT" ]   || { echo "!! heartbeat script missing: $HB_SCRIPT" >&2; exit 1; }

CLAUDE_BIN="$(command -v claude || true)"
[ -n "$CLAUDE_BIN" ] || { echo "!! 'claude' not on PATH — install Claude Code / load nvm first." >&2; exit 1; }
NODE_BIN="$(cd "$(dirname "$CLAUDE_BIN")" && pwd)"

HOUR=$((10#${TIME%%:*})); MINUTE=$((10#${TIME##*:}))

mkdir -p "$LOG_DIR" "$(dirname "$PLIST_DEST")"

sed -e "s#__WRAPPER__#$WRAPPER#g" \
    -e "s#__NODE_BIN__#$NODE_BIN#g" \
    -e "s#__LOG_DIR__#$LOG_DIR#g" \
    -e "s#__HOUR__#$HOUR#g" \
    -e "s#__MINUTE__#$MINUTE#g" \
    "$TEMPLATE" > "$PLIST_DEST"

# Reload cleanly (idempotent): bootout any existing instance, then bootstrap the fresh plist.
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST_DEST"
launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true

# The heartbeat agent (PR12): fixed 09:00, no nvm/claude paths baked in — see heartbeat.sh.
sed -e "s#__HEARTBEAT__#$HB_SCRIPT#g" \
    -e "s#__LOG_DIR__#$LOG_DIR#g" \
    -e "s#__HOUR__#$HB_HOUR#g" \
    -e "s#__MINUTE__#$HB_MINUTE#g" \
    "$HB_TEMPLATE" > "$HB_PLIST_DEST"

launchctl bootout "$DOMAIN/$HB_LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$HB_PLIST_DEST"
launchctl enable "$DOMAIN/$HB_LABEL" 2>/dev/null || true

printf 'installed %s → runs daily at %02d:%02d local\n' "$LABEL" "$HOUR" "$MINUTE"
echo "  wrapper: $WRAPPER"
echo "  nvm bin: $NODE_BIN"
echo "  logs:    $LOG_DIR/<date>.log  (launchd start-up: $LOG_DIR/launchd.log)"
printf 'installed %s → checks daily at %02d:%02d local (+ at login)\n' "$HB_LABEL" "$HB_HOUR" "$HB_MINUTE"
echo "  script:  $HB_SCRIPT  (alerts: Desktop flag + notification when the ledger goes >36h silent)"
echo "  log:     $LOG_DIR/heartbeat.log"
echo "  run now:   launchctl kickstart -k $DOMAIN/$LABEL   (sweep)"
echo "             launchctl kickstart -k $DOMAIN/$HB_LABEL   (heartbeat)"
echo "  uninstall: $SCRIPT_DIR/install-schedule.sh uninstall"
