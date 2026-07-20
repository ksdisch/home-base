#!/usr/bin/env bash
# Home Base — sweep runner (M0 grading loop + M1 brief-page ingest; M3 automation guards).
#
# Runs each active roster topic's sweep prompt through `claude -p` (your Claude
# subscription) with web search. Since M1, prompts emit strict JSON; sweeps/render_brief.py
# validates it and writes BOTH data/sweeps/<date>/<topic>.json (what GET /api/brief serves)
# and the gradeable <topic>.md (same shape as the M0 era — the grading routine is
# unchanged). Invalid JSON → <topic>.raw.txt + a loud per-topic failure. See
# sweeps/README.md.
#
#   ./sweep.sh                       # run every active topic in sweeps/topics.json
#   TOPIC=ai-llms ./sweep.sh         # run a single topic (works even if paused)
#   SWEEP_MODEL=sonnet ./sweep.sh    # try a cheaper/faster model
#
# M3 automation env (used by sweeps/schedule/run-scheduled.sh):
#   SWEEP_SKIP_DONE=1                # skip a topic whose <topic>.json already exists today —
#                                    #   idempotent, so launchd's on-wake re-fire can't double-run
#   SWEEP_MAX_TOPICS=N               # stop after N topics have run this invocation (rate cap)
#   SWEEP_ALLOW_API=1                # allow running with ANTHROPIC_API_KEY set (see Auth below)
#   SWEEP_FORCE=1                    # re-sweep a topic already written today even when notes
#                                    #   are attached (the guard warns; non-tty refuses without it)
#   SWEEP_NOTES_DB=<path>            # store the note-count guard reads (tests only;
#                                    #   default backend/data/learning-hub.sqlite)
#
# Every run appends a per-topic cost/usage row to data/sweeps/.runs.jsonl (gitignored) via
# sweeps/envelope.py — the durable record of what the sweeps actually cost.
#
# Auth: plain `claude -p` uses your logged-in Claude subscription (the lane chosen at
# kickoff). If ANTHROPIC_API_KEY is exported, Claude Code may use API billing instead, so this
# runner refuses to start with it set — `unset ANTHROPIC_API_KEY` to stay on the subscription,
# or SWEEP_ALLOW_API=1 to run on the API deliberately.
set -euo pipefail

# Cost guardrail: never *silently* fall off the subscription onto metered API billing.
if [ -n "${ANTHROPIC_API_KEY:-}" ] && [ "${SWEEP_ALLOW_API:-}" != "1" ]; then
  echo "!! ANTHROPIC_API_KEY is set — sweeps are meant to run on your Claude subscription," >&2
  echo "   not metered API billing. 'unset ANTHROPIC_API_KEY' (recommended), or set" >&2
  echo "   SWEEP_ALLOW_API=1 to run on the API deliberately." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPTS_DIR="$ROOT/sweeps/prompts"
DATE="$(date +%Y-%m-%d)"
OUT_DIR="$ROOT/data/sweeps/$DATE"
MODEL="${SWEEP_MODEL:-opus}"

if ! command -v claude >/dev/null 2>&1; then
  echo "!! 'claude' CLI not found on PATH — install Claude Code first." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "!! 'python3' not found on PATH — needed to validate/render sweep JSON." >&2
  exit 1
fi
RENDERER="$ROOT/sweeps/render_brief.py"
ENVELOPE="$ROOT/sweeps/envelope.py"
RUNS_LOG="$ROOT/data/sweeps/.runs.jsonl"

# Topics come from the roster config (M2): sweeps/topics.json, an ordered
# [{slug, title, paused}] list. Pausing there stops the daily sweep for that topic;
# `TOPIC=<slug> ./sweep.sh` still runs any single topic, paused or not.
ROSTER="$ROOT/sweeps/topics.json"
if [ -n "${TOPIC:-}" ]; then
  TOPICS=("$TOPIC")
else
  if [ ! -f "$ROSTER" ]; then
    echo "!! roster file missing: $ROSTER" >&2
    exit 1
  fi
  TOPICS=($(python3 -c '
import json, sys
for t in json.load(open(sys.argv[1], encoding="utf-8")):
    if isinstance(t, dict) and t.get("slug") and not t.get("paused"):
        print(t["slug"])
' "$ROSTER"))
  if [ "${#TOPICS[@]}" -eq 0 ]; then
    echo "!! no active topics in ${ROSTER} — all paused?" >&2
    exit 1
  fi
fi

mkdir -p "$OUT_DIR"
today_human="$(date '+%A, %B %-d, %Y')"
failures=0
processed=0

for topic in "${TOPICS[@]}"; do
  prompt_file="$PROMPTS_DIR/$topic.md"
  if [ ! -f "$prompt_file" ]; then
    echo "!! no prompt for topic '$topic' ($prompt_file) — skipping" >&2
    failures=$((failures + 1))
    continue
  fi

  # M3 idempotency: on an on-wake re-fire, don't re-sweep a topic already written today.
  if [ "${SWEEP_SKIP_DONE:-}" = "1" ] && [ -f "$OUT_DIR/$topic.json" ]; then
    echo "· ${topic} already swept for ${DATE} — skipping (SWEEP_SKIP_DONE)"
    continue
  fi

  # M3 rate cap: stop once SWEEP_MAX_TOPICS topics have actually run this invocation.
  if [ -n "${SWEEP_MAX_TOPICS:-}" ] && [ "$processed" -ge "$SWEEP_MAX_TOPICS" ]; then
    echo "· reached SWEEP_MAX_TOPICS=${SWEEP_MAX_TOPICS} — stopping (rest left for the next run)"
    break
  fi

  # HA2 re-sweep guard (docs/ideas/resweep-note-detach-guard.md): a same-day re-sweep
  # rewrites headlines, which shifts every item's read-time sha1(date|slug|headline) id —
  # notes already attached to today's items silently detach from the Today view (they stay
  # in /notes). Warn loudly + require confirmation before overwriting a topic that has
  # attached notes. Stdlib-sqlite read, dependency-free like heartbeat.sh; the scheduled
  # lane never gets here (SWEEP_SKIP_DONE skips existing topics first).
  if [ -f "$OUT_DIR/$topic.json" ]; then
    notes_db="${SWEEP_NOTES_DB:-$ROOT/backend/data/learning-hub.sqlite}"
    note_count="$(python3 - "$notes_db" "$topic" "$DATE" <<'PY' 2>/dev/null || echo 0
import sqlite3, sys
db, slug, date = sys.argv[1:4]
try:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    n = conn.execute(
        "SELECT COUNT(*) FROM brief_notes WHERE topic_slug = ? AND brief_date = ?",
        (slug, date),
    ).fetchone()[0]
except sqlite3.Error:
    n = 0
print(n)
PY
)"
    if [ "${note_count:-0}" -gt 0 ] 2>/dev/null; then
      echo "!! ${topic}: re-sweeping ${DATE} rewrites item ids — ${note_count} note(s) attached to today's items will detach from the Today view (they stay in /notes)." >&2
      if [ "${SWEEP_FORCE:-}" = "1" ]; then
        echo "   SWEEP_FORCE=1 — overwriting deliberately." >&2
      elif [ -t 0 ]; then
        read -r -p "   Re-sweep ${topic} anyway? [y/N] " answer || answer=""
        case "$answer" in
          y|Y|yes|YES) ;;
          *) echo "   skipping ${topic} (notes preserved)"; continue ;;
        esac
      else
        echo "   non-interactive run — skipping ${topic}; set SWEEP_FORCE=1 to overwrite anyway." >&2
        continue
      fi
    fi
  fi

  echo "› sweeping ${topic}  (model: ${MODEL})"

  # Dynamic date preamble anchors the run; the static instructions live in the prompt file.
  preamble="Today is ${today_human}. Focus on developments from roughly the last 24 hours (since yesterday morning). Use web search; every item must carry a real source URL."
  full_prompt="${preamble}"$'\n\n'"$(cat "$prompt_file")"

  # Per-topic "as of" stamp — runs take minutes each, so stamp at this topic's start.
  now_stamp="$(date '+%Y-%m-%d %H:%M %Z')"
  envelope_file="$(mktemp)"
  raw_file="$(mktemp)"

  # Headless run: web tools only (no file/shell tools). Non-whitelisted tools are auto-denied
  # in -p mode, so nothing can hang on a permission prompt. --output-format json wraps the
  # model's brief JSON in a result envelope (carrying cost/usage for the ledger); </dev/null
  # keeps it from stalling on stdin under launchd.
  if claude -p "$full_prompt" \
        --model "$MODEL" \
        --allowedTools "WebSearch" "WebFetch" \
        --output-format json \
        < /dev/null > "$envelope_file"; then
    # Unwrap .result → raw_file (what the frozen renderer expects) + append the cost ledger row.
    if python3 "$ENVELOPE" --topic "$topic" --date "$DATE" --model "$MODEL" \
          --envelope "$envelope_file" --out-raw "$raw_file" --runs-log "$RUNS_LOG"; then
      # Validate the JSON and write <topic>.json + gradeable <topic>.md (or .raw.txt on failure).
      # Bug #22: the always-on server reads $OUT_DIR/<topic>.json per request, and the frozen
      # renderer write_text-truncates its target — so it renders into a stage dir inside
      # $OUT_DIR (same filesystem → mv is an atomic rename; the server ignores subdirs) and
      # the artifacts land whole, .md first so the fallback exists before the .json it backs.
      stage_dir="$(mktemp -d "$OUT_DIR/.stage.$topic.XXXXXX")"
      if python3 "$RENDERER" --topic "$topic" --date "$DATE" --as-of "$now_stamp" \
            --raw "$raw_file" --out-dir "$stage_dir"; then
        mv -f "$stage_dir/$topic.md" "$OUT_DIR/$topic.md"
        mv -f "$stage_dir/$topic.json" "$OUT_DIR/$topic.json"
        echo "  → ${OUT_DIR}/${topic}.md + ${topic}.json"
      else
        if [ -f "$stage_dir/$topic.raw.txt" ]; then
          mv -f "$stage_dir/$topic.raw.txt" "$OUT_DIR/$topic.raw.txt"
        fi
        failures=$((failures + 1))
      fi
      rm -rf "$stage_dir"
    else
      cp "$envelope_file" "$OUT_DIR/$topic.raw.txt" 2>/dev/null || true
      echo "!! sweep envelope error for ${topic} — raw envelope in ${OUT_DIR}/${topic}.raw.txt" >&2
      failures=$((failures + 1))
    fi
  else
    cp "$envelope_file" "$OUT_DIR/$topic.raw.txt" 2>/dev/null || true
    echo "!! sweep failed for ${topic} — see the error above; partial output in ${OUT_DIR}/${topic}.raw.txt" >&2
    failures=$((failures + 1))
  fi
  processed=$((processed + 1))
  rm -f "$envelope_file" "$raw_file"
done

# M4: best-effort audio brief (local Kokoro TTS). A down/absent Kokoro must never fail the
# sweep — the text brief is the product, the MP3 is a bonus. The script skips itself when
# brief.mp3 is already newer than every <topic>.json, so on-wake re-fires stay no-ops.
if ! python3 "$ROOT/sweeps/audio_brief.py" --date "$DATE" --sweeps-dir "$ROOT/data/sweeps"; then
  echo "!! audio brief did not render (see above) — text briefs are unaffected" >&2
fi

# Overnight Chief of Staff v0: draft-only proposals from today's briefs into the backend
# queue (in-repo data only; sends/executes nothing — approve/discard happens on the page).
# Best-effort like the audio brief, and idempotent per day, so re-fires stay no-ops.
if ! python3 "$ROOT/sweeps/actions_queue.py" --date "$DATE" --sweeps-dir "$ROOT/data/sweeps" \
      --roster "$ROSTER" --out "$ROOT/backend/data/overnight.jsonl" --runs-log "$RUNS_LOG"; then
  echo "!! overnight proposals did not draft (see above) — the briefs are unaffected" >&2
fi

echo
echo "Briefs written to ${OUT_DIR}"
echo "Grade each A–F in docs/M0-sweep-grades.md (~2 min)."
[ "$failures" -eq 0 ] || { echo "(${failures} topic(s) failed.)" >&2; exit 1; }
