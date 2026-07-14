#!/usr/bin/env bash
# Home Base — sweep runner (M0 grading loop + M1 brief-page ingest).
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
# Auth: plain `claude -p` uses your logged-in Claude subscription (the lane chosen at
# kickoff). If ANTHROPIC_API_KEY is exported, Claude Code may use API billing instead —
# `unset ANTHROPIC_API_KEY` to stay on the subscription.
set -euo pipefail

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

for topic in "${TOPICS[@]}"; do
  prompt_file="$PROMPTS_DIR/$topic.md"
  if [ ! -f "$prompt_file" ]; then
    echo "!! no prompt for topic '$topic' ($prompt_file) — skipping" >&2
    failures=$((failures + 1))
    continue
  fi
  echo "› sweeping ${topic}  (model: ${MODEL})"

  # Dynamic date preamble anchors the run; the static instructions live in the prompt file.
  preamble="Today is ${today_human}. Focus on developments from roughly the last 24 hours (since yesterday morning). Use web search; every item must carry a real source URL."
  full_prompt="${preamble}"$'\n\n'"$(cat "$prompt_file")"

  # Per-topic "as of" stamp — runs take minutes each, so stamp at this topic's start.
  now_stamp="$(date '+%Y-%m-%d %H:%M %Z')"
  raw_file="$(mktemp)"

  # Headless run: web tools only (no file/shell tools). Non-whitelisted tools are
  # auto-denied in -p mode, so nothing can hang on a permission prompt.
  if claude -p "$full_prompt" \
        --model "$MODEL" \
        --allowedTools "WebSearch" "WebFetch" \
        > "$raw_file"; then
    # Validate the JSON and write <topic>.json + gradeable <topic>.md (or .raw.txt on failure).
    if python3 "$RENDERER" --topic "$topic" --date "$DATE" --as-of "$now_stamp" \
          --raw "$raw_file" --out-dir "$OUT_DIR"; then
      echo "  → ${OUT_DIR}/${topic}.md + ${topic}.json"
    else
      failures=$((failures + 1))
    fi
  else
    cp "$raw_file" "$OUT_DIR/$topic.raw.txt" 2>/dev/null || true
    echo "!! sweep failed for ${topic} — see the error above; partial output in ${OUT_DIR}/${topic}.raw.txt" >&2
    failures=$((failures + 1))
  fi
  rm -f "$raw_file"
done

echo
echo "Briefs written to ${OUT_DIR}"
echo "Grade each A–F in docs/M0-sweep-grades.md (~2 min)."
[ "$failures" -eq 0 ] || { echo "(${failures} topic(s) failed.)" >&2; exit 1; }
