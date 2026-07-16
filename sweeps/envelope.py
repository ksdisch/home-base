#!/usr/bin/env python3
"""Unwrap a ``claude -p --output-format json`` envelope + log the run's cost/usage (M3).

sweep.sh runs each topic with ``--output-format json``, so claude's stdout is the result
*envelope* — the model's brief JSON is the string under ``.result``. This script:

  1. reads the envelope and, on success, writes that ``.result`` text to --out-raw — exactly
     the raw model output the frozen sweeps/render_brief.py already expects (the trust-critical
     validate+render write path is unchanged);
  2. appends one line to the --runs-log JSONL ledger with the run's cost/tokens/duration
     (data/sweeps/.runs.jsonl — gitignored; the durable answer to "what do the sweeps cost").

Exit 0 when a usable result was unwrapped; exit 1 on an error envelope (is_error, or no
string result) so the runner keeps the envelope as <topic>.raw.txt and counts a loud failure —
the same trust gate an unparseable brief hits. Stdlib only; system python3, no venv.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _num(value: object) -> object:
    """Keep numbers, drop anything else (missing keys become null in the ledger)."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def ledger_row(env: dict, topic: str, date: str, model: str) -> dict:
    """One .runs.jsonl row from the result envelope — cost/usage a human can total up later."""
    usage = env.get("usage") if isinstance(env.get("usage"), dict) else {}
    stu = usage.get("server_tool_use") if isinstance(usage.get("server_tool_use"), dict) else {}
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": date,
        "topic": topic,
        "model": model,
        "is_error": bool(env.get("is_error")),
        "total_cost_usd": _num(env.get("total_cost_usd")),
        "duration_ms": _num(env.get("duration_ms")),
        "num_turns": _num(env.get("num_turns")),
        "input_tokens": _num(usage.get("input_tokens")),
        "output_tokens": _num(usage.get("output_tokens")),
        "cache_read_input_tokens": _num(usage.get("cache_read_input_tokens")),
        "cache_creation_input_tokens": _num(usage.get("cache_creation_input_tokens")),
        "web_search_requests": _num(stu.get("web_search_requests")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD of this sweep run")
    ap.add_argument("--model", default="", help="model slug the run used (for the ledger)")
    ap.add_argument("--envelope", required=True, help="file holding the --output-format json envelope")
    ap.add_argument("--out-raw", required=True, dest="out_raw", help="where to write the unwrapped .result text")
    ap.add_argument("--runs-log", required=True, dest="runs_log", help="JSONL cost/usage ledger to append to")
    args = ap.parse_args()

    text = Path(args.envelope).read_text(encoding="utf-8")
    try:
        env = json.loads(text)
        if not isinstance(env, dict):
            raise ValueError(f"envelope top-level is {type(env).__name__}, not an object")
    except (ValueError, json.JSONDecodeError) as e:
        print(f"!! {args.topic}: unreadable claude envelope ({e})", file=sys.stderr)
        return 1

    # Log the run regardless of success — an error run still consumed tokens and is worth recording.
    log = Path(args.runs_log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ledger_row(env, args.topic, args.date, args.model), ensure_ascii=False) + "\n")

    result = env.get("result")
    if env.get("is_error") or not isinstance(result, str) or not result.strip():
        rtype = "present" if isinstance(result, str) else type(result).__name__
        print(f"!! {args.topic}: error envelope (is_error={env.get('is_error')}, result={rtype})", file=sys.stderr)
        return 1

    Path(args.out_raw).write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
