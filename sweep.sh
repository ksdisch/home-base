#!/usr/bin/env bash
# Home Base — Milestone 0 sweep runner.
#
# Runs each pilot topic's sweep prompt through `claude -p` (your Claude subscription)
# with web search, and writes one gradeable markdown brief per topic to
# data/sweeps/<date>/. No UI, no backend ingest — this exists purely to test sweep
# QUALITY for the M0 go/no-go. See sweeps/README.md.
#
#   ./sweep.sh                       # run all pilot topics
#   TOPIC=ai-llms ./sweep.sh         # run a single topic
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

# Pilot topics for M0 (fixed set from the kickoff brief).
TOPICS=(ai-llms fantasy-football market-tech-news)
# `TOPIC=<slug> ./sweep.sh` runs just one.
if [ -n "${TOPIC:-}" ]; then
  TOPICS=("$TOPIC")
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "!! 'claude' CLI not found on PATH — install Claude Code first." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
today_human="$(date '+%A, %B %-d, %Y')"
now_stamp="$(date '+%Y-%m-%d %H:%M %Z')"
failures=0

for topic in "${TOPICS[@]}"; do
  prompt_file="$PROMPTS_DIR/$topic.md"
  if [ ! -f "$prompt_file" ]; then
    echo "!! no prompt for topic '$topic' ($prompt_file) — skipping" >&2
    failures=$((failures + 1))
    continue
  fi
  out_file="$OUT_DIR/$topic.md"
  echo "› sweeping ${topic}  (model: ${MODEL})"

  # Dynamic date preamble anchors the run; the static instructions live in the prompt file.
  preamble="Today is ${today_human}. Focus on developments from roughly the last 24 hours (since yesterday morning). Use web search; every item must carry a real source URL."
  full_prompt="${preamble}"$'\n\n'"$(cat "$prompt_file")"

  # Runner writes an honest "as of" header; the model appends the brief body.
  { echo "# ${topic} — as of ${now_stamp}"; echo; } > "$out_file"

  # Headless run: web tools only (no file/shell tools). Non-whitelisted tools are
  # auto-denied in -p mode, so nothing can hang on a permission prompt.
  if claude -p "$full_prompt" \
        --model "$MODEL" \
        --allowedTools "WebSearch" "WebFetch" \
        >> "$out_file"; then
    echo "  → ${out_file} ($(wc -l <"$out_file" | tr -d ' ') lines)"
  else
    echo "!! sweep failed for ${topic} — see the error above; partial output in ${out_file}" >&2
    failures=$((failures + 1))
  fi
done

echo
echo "Briefs written to ${OUT_DIR}"
echo "Grade each A–F in docs/M0-sweep-grades.md (~2 min)."
[ "$failures" -eq 0 ] || { echo "(${failures} topic(s) failed.)" >&2; exit 1; }
