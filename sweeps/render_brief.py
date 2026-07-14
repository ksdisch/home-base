#!/usr/bin/env python3
"""Validate a sweep's JSON output and render the gradeable Markdown view.

sweep.sh pipes each topic's raw ``claude -p`` output through this script. On valid JSON it
writes BOTH artifacts into the day folder:

  <topic>.json — the machine-readable brief the hub ingests (GET /api/brief)
  <topic>.md   — the human-gradeable view for the M0/M1 grading loop, rendered in the exact
                 shape the prompts used to emit directly (dated header, bold top line,
                 optional context note, ### items)

On unparseable/invalid output it preserves the raw text at <topic>.raw.txt and exits 1 so the
runner counts a loud per-topic failure — a brief that can't be validated must never silently
reach the page. Stdlib only; runs with the system python3, no venv.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REQUIRED_ITEM_FIELDS = ("headline", "attribution", "digest", "why_it_matters")


def extract_json(text: str) -> dict:
    """Parse the model output as JSON, tolerating two common flubs.

    Ladder: exact parse → strip a ```/```json code fence → take the first-{ .. last-} span.
    Raises ValueError when nothing on the ladder yields a JSON object.
    """
    candidates = [text.strip()]

    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].lstrip().startswith("```") and lines[-1].strip().startswith("```"):
        candidates.append("\n".join(lines[1:-1]).strip())

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    last_err: Exception | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as e:  # try the next rung
            last_err = e
            continue
        if isinstance(parsed, dict):
            return parsed
        last_err = ValueError(f"top-level JSON is {type(parsed).__name__}, not an object")
    raise ValueError(f"no parseable JSON object in output ({last_err})")


def validate(brief: dict) -> list[str]:
    """Return every schema problem (empty list = valid).

    Enforces the M0 hard rule at write time: every item carries ≥1 real-looking source URL.
    """
    problems: list[str] = []

    top_line = brief.get("top_line")
    if not isinstance(top_line, str) or not top_line.strip():
        problems.append("top_line missing or empty")

    note = brief.get("context_note")
    if note is not None and not isinstance(note, str):
        problems.append("context_note must be a string or null")

    items = brief.get("items")
    if not isinstance(items, list):
        problems.append("items missing or not a list")
        return problems

    for i, item in enumerate(items):
        where = f"items[{i}]"
        if not isinstance(item, dict):
            problems.append(f"{where} is not an object")
            continue
        for field in REQUIRED_ITEM_FIELDS:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{where}.{field} missing or empty")
        sources = item.get("sources")
        if not isinstance(sources, list) or not sources:
            problems.append(f"{where}.sources missing or empty — every item needs ≥1 real URL")
            continue
        for j, src in enumerate(sources):
            swhere = f"{where}.sources[{j}]"
            if not isinstance(src, dict):
                problems.append(f"{swhere} is not an object")
                continue
            title, url = src.get("title"), src.get("url")
            if not isinstance(title, str) or not title.strip():
                problems.append(f"{swhere}.title missing or empty")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                problems.append(f"{swhere}.url missing or not an http(s) URL")
    return problems


def normalize(brief: dict, topic: str, date: str, as_of: str) -> dict:
    """Wrap the validated model JSON with run metadata, keeping only known keys."""
    note = brief.get("context_note")
    return {
        "topic": topic,
        "date": date,
        "as_of": as_of,
        "top_line": brief["top_line"].strip(),
        "context_note": note.strip() if isinstance(note, str) and note.strip() else None,
        "items": [
            {
                "headline": item["headline"].strip(),
                "attribution": item["attribution"].strip(),
                "digest": item["digest"].strip(),
                "why_it_matters": item["why_it_matters"].strip(),
                "sources": [
                    {"title": s["title"].strip(), "url": s["url"].strip()}
                    for s in item["sources"]
                ],
            }
            for item in brief["items"]
        ],
    }


def render_markdown(brief: dict) -> str:
    """Render the gradeable .md in the pre-JSON shape the grading routine expects."""
    parts = [f"# {brief['topic']} — as of {brief['as_of']}", "", f"**{brief['top_line']}**", ""]
    if brief["context_note"]:
        parts += [brief["context_note"], ""]
    for item in brief["items"]:
        sources = " · ".join(f"[{s['title']}]({s['url']})" for s in item["sources"])
        parts += [
            f"### {item['headline']} — {item['attribution']}",
            item["digest"],
            f"**Why it matters:** {item['why_it_matters']}",
            f"**Sources:** {sources}",
            "",
        ]
    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD of this sweep run")
    ap.add_argument("--as-of", required=True, dest="as_of", help="honest human 'as of' stamp")
    ap.add_argument("--raw", required=True, help="file holding the raw model output")
    ap.add_argument("--out-dir", required=True, dest="out_dir")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = Path(args.raw)
    text = raw_path.read_text(encoding="utf-8")

    try:
        parsed = extract_json(text)
        problems = validate(parsed)
    except ValueError as e:
        parsed, problems = None, [str(e)]

    if problems or parsed is None:
        keep = out_dir / f"{args.topic}.raw.txt"
        shutil.copyfile(raw_path, keep)
        print(f"!! {args.topic}: invalid sweep JSON — raw output kept at {keep}", file=sys.stderr)
        for p in problems:
            print(f"   - {p}", file=sys.stderr)
        return 1

    brief = normalize(parsed, args.topic, args.date, args.as_of)
    (out_dir / f"{args.topic}.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / f"{args.topic}.md").write_text(render_markdown(brief), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
