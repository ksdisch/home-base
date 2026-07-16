#!/usr/bin/env bash
# Home Base — install/uninstall the daily-sweep LaunchAgent (M3).
#
#   sweeps/schedule/install-schedule.sh            # install/refresh at 06:00 local
#   sweeps/schedule/install-schedule.sh 07:15      # install/refresh at a custom time
#   sweeps/schedule/install-schedule.sh status     # show launchctl state
#   sweeps/schedule/install-schedule.sh uninstall  # remove it
#
# Fills the plist template with this machine's repo root, the nvm bin dir holding `claude`, and
# the chosen time; writes it to ~/Library/LaunchAgents; (re)bootstraps it into your GUI session.
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

uninstall() {
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null && echo "booted out $LABEL" || echo "$LABEL was not loaded"
  if [ -f "$PLIST_DEST" ]; then rm -f "$PLIST_DEST" && echo "removed $PLIST_DEST"; fi
}

cmd="${1:-install}"
case "$cmd" in
  uninstall|remove) uninstall; exit 0 ;;
  status)
    echo "domain: $DOMAIN   label: $LABEL"
    echo "plist:  $PLIST_DEST $( [ -f "$PLIST_DEST" ] && echo '(present)' || echo '(absent)')"
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -iE 'state =|program =|runatload|nextfiredate' \
      || echo "(not loaded — run install-schedule.sh)"
    exit 0 ;;
  install) TIME="06:00" ;;
  *)
    if printf '%s' "$cmd" | grep -qE '^([01][0-9]|2[0-3]):[0-5][0-9]$'; then TIME="$cmd"
    else echo "usage: install-schedule.sh [HH:MM | status | uninstall]"; exit 2; fi ;;
esac

[ -f "$TEMPLATE" ] || { echo "!! template missing: $TEMPLATE" >&2; exit 1; }
[ -f "$WRAPPER" ]  || { echo "!! wrapper missing: $WRAPPER" >&2; exit 1; }

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

printf 'installed %s → runs daily at %02d:%02d local\n' "$LABEL" "$HOUR" "$MINUTE"
echo "  wrapper: $WRAPPER"
echo "  nvm bin: $NODE_BIN"
echo "  logs:    $LOG_DIR/<date>.log  (launchd start-up: $LOG_DIR/launchd.log)"
echo "  run now:   launchctl kickstart -k $DOMAIN/$LABEL"
echo "  uninstall: $SCRIPT_DIR/install-schedule.sh uninstall"
