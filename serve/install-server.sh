#!/usr/bin/env bash
# Home Base — install/uninstall the always-on server LaunchAgent (M6).
#
#   serve/install-server.sh            # install/refresh
#   serve/install-server.sh status     # show launchctl state
#   serve/install-server.sh uninstall  # remove it
#
# Fills the plist template with this machine's paths, writes it to ~/Library/LaunchAgents,
# (re)bootstraps it into your GUI session. Idempotent — safe to re-run after moving the repo.
# Prints (never runs) the optional pmset wake schedule; sudo stays in your hands.
set -euo pipefail

LABEL="com.homebase.server"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$SCRIPT_DIR/com.homebase.server.plist.template"
WRAPPER="$SCRIPT_DIR/run-server.sh"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$ROOT/backend/data/logs"
DOMAIN="gui/$(id -u)"

uninstall() {
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null && echo "booted out $LABEL" || echo "$LABEL was not loaded"
  if [ -f "$PLIST_DEST" ]; then rm -f "$PLIST_DEST" && echo "removed $PLIST_DEST"; fi
}

case "${1:-install}" in
  uninstall|remove) uninstall; exit 0 ;;
  status)
    echo "domain: $DOMAIN   label: $LABEL"
    echo "plist:  $PLIST_DEST $( [ -f "$PLIST_DEST" ] && echo '(present)' || echo '(absent)')"
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -iE 'state =|program =|runatload|pid =' \
      || echo "(not loaded — run install-server.sh)"
    exit 0 ;;
  install) ;;
  *) echo "usage: install-server.sh [status | uninstall]"; exit 2 ;;
esac

[ -f "$TEMPLATE" ] || { echo "!! template missing: $TEMPLATE" >&2; exit 1; }
[ -f "$WRAPPER" ]  || { echo "!! wrapper missing: $WRAPPER" >&2; exit 1; }
[ -x "$ROOT/backend/.venv/bin/python" ] || echo "?? backend venv missing — run 'make setup' (the agent retries until it exists)"
[ -f "$ROOT/frontend/dist/index.html" ] || echo "?? frontend/dist missing — run 'make build' or the phone gets an API-only server"

mkdir -p "$LOG_DIR" "$(dirname "$PLIST_DEST")"

sed -e "s#__WRAPPER__#$WRAPPER#g" \
    -e "s#__LOG_DIR__#$LOG_DIR#g" \
    "$TEMPLATE" > "$PLIST_DEST"

# Reload cleanly (idempotent): bootout any existing instance, then bootstrap the fresh plist.
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST_DEST"
launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true

echo "installed $LABEL → hub on http://127.0.0.1:8000 whenever the Mac is up"
echo "  wrapper:   $WRAPPER"
echo "  logs:      $LOG_DIR/launchd.log"
echo "  status:    $SCRIPT_DIR/install-server.sh status"
echo "  uninstall: $SCRIPT_DIR/install-server.sh uninstall"
echo
echo "phone reach (one-time): tailscale serve --bg http://127.0.0.1:8000"
echo
echo "optional — wake the Mac before the 06:00 sweep (run the sudo yourself; this script never does):"
echo "  sudo pmset repeat wakeorpoweron MTWRFSU 05:55:00"
