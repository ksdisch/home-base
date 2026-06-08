#!/usr/bin/env bash
# PreToolUse guard — block any write to the read-only NotebookLM sidecar root.
#
# The hub treats sidecars under $NOTEBOOKLM_ROOT (default ~/Projects/NotebookLMs) as a
# read-only source of truth: it parses them but never writes them (enforced by
# backend/tests/test_no_sidecar_writes.py). This hook extends that guarantee to the agent
# itself, so an Edit/Write/MultiEdit/NotebookEdit can never mutate a sidecar mid-session.
#
# Contract (Claude Code hooks): read the tool-call JSON on stdin; exit 2 with a reason on
# stderr to BLOCK the call (the reason is fed back to Claude); exit 0 to allow. We never fail
# the call for parsing reasons — a guard that breaks every edit is worse than no guard.
set -uo pipefail

payload="$(cat)"

# Pull the target path out of the tool input. Edit/Write/MultiEdit use file_path;
# NotebookEdit uses notebook_path. The payload goes in via env (not stdin) so it can't
# collide with python reading its own program. python3 is guaranteed in this repo.
target="$(HOOK_PAYLOAD="$payload" python3 -c '
import json, os, sys
try:
    d = json.loads(os.environ.get("HOOK_PAYLOAD", "") or "{}")
except Exception:
    sys.exit(0)
ti = d.get("tool_input", {}) or {}
print(ti.get("file_path") or ti.get("notebook_path") or "")
' 2>/dev/null || true)"

[ -z "$target" ] && exit 0

root="${NOTEBOOKLM_ROOT:-$HOME/Projects/NotebookLMs}"

case "$target" in
  "$root" | "$root"/*)
    echo "Blocked write to $target — it is under the read-only NotebookLM sidecar root ($root)." >&2
    echo "The hub never writes sidecars (see backend/tests/test_no_sidecar_writes.py)." >&2
    echo "Write generated content to the hub data/courses dir instead. If this is genuinely" >&2
    echo "intentional, do it outside Claude or unset/point NOTEBOOKLM_ROOT elsewhere." >&2
    exit 2
    ;;
esac

exit 0
