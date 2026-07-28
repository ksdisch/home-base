#!/usr/bin/env python3
"""Free-Inference Rebuild bake-off (D8) — can a local model reshape the brief, ids-only?

Grades a local Ollama model on ONE question: given a day's sweep artifact and an
open-ended natural-language reshape request ("just the Chicago stuff", "brief me in 90
seconds"), can it return a correct SELECTION AND ORDERING of items — reliably enough,
for a full week, to earn a read-time surface?

The load-bearing contract is ids-only, never prose (recorded scope, decision D8): the
model's entire output is a JSON array of item ordinals, and this script maps them back
to real item ids in Python. There is no channel through which a new claim can enter, so
fabrication is structurally impossible rather than detected after the fact. Anything the
model says around the array is discarded — and counted as a defect, because a model that
cannot hold the output contract is not ready regardless of its taste.

Why ordinals and not ids: item ids are read-time-derived sha1 prefixes, so asking a small
model to transcribe 12 hex chars would measure transcription accuracy instead of selection
quality. Ordinals are 1..N, and any out-of-range or duplicate ordinal is dropped
mechanically — which makes the "no invented ids" check exact.

Zero user-facing surface by construction: this writes a verdict table to docs/ and touches
nothing the morning reads. Assumption 2 ("zero/minimal LLM at read time") stays uncrossed
until a graded week passes at the bar below and a SECOND decision ships a lens.

Stdlib only; runs with the system python3, no venv — the sweeps/ house rule. Like
actions_queue.py this re-derives the item id rather than importing the backend; the
formula is app.sweeps._structured_topic's, and the two must stay in lockstep.

  python3 sweeps/local_reader_bench.py --list-fixtures     # what would run, no model
  python3 sweeps/local_reader_bench.py --dry-run           # print prompts, call nothing
  python3 sweeps/local_reader_bench.py --model qwen2.5:7b  # grade one pass
  python3 sweeps/local_reader_bench.py --report            # append the verdict table

Env: OLLAMA_URL (default http://127.0.0.1:11434/api/generate).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_TIMEOUT = 120

# A runner takes one prompt and returns the model's raw text. Injected in tests so the
# suite never needs Ollama, mirroring backend/app/chat.py's Runner seam (that one carries
# subprocess argv because it shells out to `claude`; this one is HTTP, so it carries the
# prompt). Swapping in an MLX runner later is a new function, not a rewrite.
Runner = Callable[[str], str]

# Hard-gate defects: any one of these fails the fixture outright (see grade()). A model
# that emits prose around a valid array has still broken the output contract, but the
# report distinguishes it from pure garbage because the two mean different things.
HARD_DEFECTS = ("unparseable", "prose_wrapped", "non_integer", "out_of_range", "duplicate")

_JSON_ARRAY = re.compile(r"\[[^\[\]]*\]", re.S)


# --------------------------------------------------------------------------- corpus


def load_roster(roster_file: Path) -> list[dict]:
    """Ordered [{slug, title}] from sweeps/topics.json — tolerant like the backend's
    loader. Paused topics stay: the pause flag gates sweeping, never what's on disk."""
    try:
        data = json.loads(roster_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    roster = []
    for entry in data:
        if isinstance(entry, dict) and isinstance(entry.get("slug"), str) and entry["slug"].strip():
            title = entry.get("title")
            roster.append(
                {
                    "slug": entry["slug"].strip(),
                    "title": title.strip() if isinstance(title, str) and title.strip() else None,
                }
            )
    return roster


def item_id(day: str, slug: str, headline: str, seen: set[str]) -> str:
    """sha1(date|slug|headline)[:12], exactly app.sweeps._structured_topic's formula.

    Identical headlines inside one brief (rare) take a ``-2``/``-3`` suffix in item order.
    actions_queue.py can skip this because it only ever reads a brief's FIRST item; this
    script reads every item, so the suffix is load-bearing here.
    """
    base = hashlib.sha1(f"{day}|{slug}|{headline}".encode("utf-8")).hexdigest()[:12]
    out, n = base, 2
    while out in seen:
        out = f"{base}-{n}"
        n += 1
    seen.add(out)
    return out


def load_day(day_dir: Path, roster: list[dict]) -> list[dict]:
    """Every readable topic's every item, roster order first, as flat ordinal candidates.

    Returns [{ordinal, id, slug, topic, headline, attribution, digest}] with ordinal
    1-based — the number the model is shown and the only thing it may emit. Dotted stems
    (brief.chapters.json) are pipeline artifacts, never topics. A malformed topic file is
    skipped, not fatal: a bad day should grade on what actually rendered, the same way the
    page degrades.
    """
    try:
        present = {p.stem for p in day_dir.glob("*.json") if "." not in p.stem}
    except OSError:
        return []
    roster_slugs = [t["slug"] for t in roster]
    ordered = [s for s in roster_slugs if s in present]
    ordered += sorted(present - set(roster_slugs))
    titles = {t["slug"]: t["title"] for t in roster if t["title"]}
    day = day_dir.name

    out: list[dict] = []
    seen: set[str] = set()
    for slug in ordered:
        try:
            data = json.loads((day_dir / f"{slug}.json").read_text(encoding="utf-8"))
            items = data["items"]
        except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            headline = item.get("headline")
            if not isinstance(headline, str) or not headline.strip():
                continue
            headline = str(headline)
            out.append(
                {
                    "ordinal": len(out) + 1,
                    "id": item_id(day, slug, headline, seen),
                    "slug": slug,
                    "topic": titles.get(slug) or slug.replace("-", " ").title(),
                    "headline": headline,
                    "attribution": str(item.get("attribution", "")),
                    "digest": str(item.get("digest", "")),
                }
            )
    return out


def load_fixtures(path: Path) -> list[dict]:
    """The graded requests. Each fixture is Kyle's judgment about what a request should
    return, so this loader is strict on purpose: a typo in a gold set must not silently
    become a passing grade."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("fixture file must be a JSON array")
    for i, fx in enumerate(data):
        if not isinstance(fx, dict):
            raise ValueError(f"fixture {i} is not an object")
        for key in ("id", "date", "request"):
            if not isinstance(fx.get(key), str) or not fx[key].strip():
                raise ValueError(f"fixture {i} missing required string field {key!r}")
        for key in ("must_include", "must_exclude", "expect_order"):
            if key in fx and not isinstance(fx[key], list):
                raise ValueError(f"fixture {fx['id']}: {key!r} must be a list")
    return data


# --------------------------------------------------------------------------- prompt


def build_prompt(candidates: list[dict], request: str) -> str:
    """One self-contained prompt: the day as a numbered list, the request, the contract.

    Deliberately gives the model no way to be helpful in prose — the only useful thing it
    can emit is the array. Mirrors chat.py's build_prompt house style (rules first, data
    verbatim, question last).
    """
    lines = [
        "You are selecting which of today's news items to show, and in what order.",
        "",
        "RULES — these are absolute:",
        "1. Reply with a JSON array of item numbers and NOTHING else. No prose, no",
        "   explanation, no code fence, no keys — just the array, e.g. [3,1,7].",
        "2. Use ONLY numbers from the list below. Never invent a number.",
        "3. Never repeat a number.",
        "4. Order the array the way the items should be shown.",
        "5. If NOTHING in the list genuinely satisfies the request, reply with []. An",
        "   empty array is a correct and expected answer. Never pad with loosely",
        "   related items to look helpful.",
        "",
        "TODAY'S ITEMS:",
    ]
    for c in candidates:
        lines.append(f"[{c['ordinal']}] ({c['topic']}) {c['headline']}")
        if c["attribution"]:
            lines.append(f"     {c['attribution']}")
        if c["digest"]:
            lines.append(f"     {c['digest']}")
    lines += ["", f"REQUEST: {request}", "", "JSON array only:"]
    return "\n".join(lines)


# --------------------------------------------------------------------------- runner


def ollama_runner(model: str, url: str = "", timeout: int = DEFAULT_TIMEOUT) -> Runner:
    """A Runner that POSTs to a local Ollama. Temperature 0: the bake-off grades the
    model's judgment, not its dice."""
    endpoint = url or os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL)

    def run(prompt: str) -> str:
        body = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        out = payload.get("response")
        return out if isinstance(out, str) else ""

    return run


# --------------------------------------------------------------------------- decode


def decode(raw: str, n: int) -> tuple[list[int], list[str]]:
    """Raw model text -> (ordinals, defects). THE ids-only enforcement point.

    Pure Python, no model involvement: whatever survives here is by construction a list of
    valid ordinals, which the caller maps to stored items. Defect names are the report's
    vocabulary, so they are stable strings.
    """
    defects: list[str] = []
    text = (raw or "").strip()

    parsed: object = None
    try:
        parsed = json.loads(text)
    except ValueError:
        # Recover the first bracketed array so the report can tell "wrapped a good answer
        # in chatter" apart from "emitted garbage" — both fail the gate, for different
        # reasons and with different fixes.
        m = _JSON_ARRAY.search(text)
        if m:
            try:
                parsed = json.loads(m.group(0))
                defects.append("prose_wrapped")
            except ValueError:
                return [], ["unparseable"]
        else:
            return [], ["unparseable"]

    if not isinstance(parsed, list):
        return [], ["unparseable"]

    out: list[int] = []
    seen: set[int] = set()
    for entry in parsed:
        # bool is an int subclass; True would otherwise sail through as ordinal 1.
        if isinstance(entry, bool) or not isinstance(entry, int):
            if "non_integer" not in defects:
                defects.append("non_integer")
            continue
        if entry < 1 or entry > n:
            if "out_of_range" not in defects:
                defects.append("out_of_range")
            continue
        if entry in seen:
            if "duplicate" not in defects:
                defects.append("duplicate")
            continue
        seen.add(entry)
        out.append(entry)
    return out, defects


# --------------------------------------------------------------------------- grade


def grade(fixture: dict, candidates: list[dict], ordinals: list[int], defects: list[str]) -> dict:
    """Score one fixture. Hard gates are absolute — the M0 zero-fabrication bar,
    transposed onto structured output: one broken contract fails the fixture outright,
    no partial credit for good taste inside a malformed answer."""
    by_ordinal = {c["ordinal"]: c for c in candidates}
    picked_ids = [by_ordinal[o]["id"] for o in ordinals if o in by_ordinal]

    must_include = [i for i in fixture.get("must_include", []) if isinstance(i, str)]
    must_exclude = [i for i in fixture.get("must_exclude", []) if isinstance(i, str)]
    expect_order = [i for i in fixture.get("expect_order", []) if isinstance(i, str)]
    expect_empty = bool(fixture.get("expect_empty"))

    hard = [d for d in defects if d in HARD_DEFECTS]

    # Refusal honesty: an impossible request must come back empty, not plausibly padded.
    refusal_ok = True
    if expect_empty and picked_ids:
        refusal_ok = False
        hard = hard + ["padded_refusal"]

    hit = [i for i in must_include if i in picked_ids]
    leaked = [i for i in must_exclude if i in picked_ids]
    recall = (len(hit) / len(must_include)) if must_include else None
    precision = (1 - len(leaked) / len(must_exclude)) if must_exclude else None

    # Ordering is scored only where the fixture declares one, and only on relative
    # position — an extra item between two expected ones is not an ordering error.
    order_ok: Optional[bool] = None
    if expect_order:
        seq = [i for i in picked_ids if i in expect_order]
        order_ok = seq == [i for i in expect_order if i in picked_ids]

    return {
        "fixture": fixture["id"],
        "date": fixture["date"],
        "request": fixture["request"],
        "n_candidates": len(candidates),
        "picked": picked_ids,
        "defects": defects,
        "hard_fail": bool(hard),
        "hard_defects": hard,
        "refusal_ok": refusal_ok,
        "missed": [i for i in must_include if i not in picked_ids],
        "leaked": leaked,
        "recall": recall,
        "precision": precision,
        "order_ok": order_ok,
    }


# --------------------------------------------------------------------------- report


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{round(v * 100)}%"


def render_report(model: str, results: list[dict], day: str) -> str:
    """The verdict table, in docs/M0-sweep-grades.md's house style: dated heading, a row
    per fixture, and a verdict line that states the bar it was judged against."""
    hard_fails = [r for r in results if r["hard_fail"]]
    recalls = [r["recall"] for r in results if r["recall"] is not None]
    precisions = [r["precision"] for r in results if r["precision"] is not None]
    orders = [r["order_ok"] for r in results if r["order_ok"] is not None]

    verdict = "PASS (hard gates clean)" if not hard_fails else f"FAIL ({len(hard_fails)} hard)"
    lines = [
        f"## {day} — {model}",
        "",
        f"**Verdict: {verdict}** · {len(results)} fixtures · "
        f"mean recall {_pct(sum(recalls) / len(recalls) if recalls else None)} · "
        f"mean precision {_pct(sum(precisions) / len(precisions) if precisions else None)}"
        + (f" · ordering {sum(orders)}/{len(orders)}" if orders else ""),
        "",
        "Hard gates are absolute: any unparseable/prose-wrapped/invalid-ordinal response, or a"
        " non-empty answer to an impossible request, fails the fixture. A pass requires 7"
        " consecutive daily runs with every hard gate clean.",
        "",
        "| Fixture | Request | Items | Picked | Recall | Prec | Order | Defects |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        defects = ", ".join(r["defects"]) if r["defects"] else "—"
        order = "—" if r["order_ok"] is None else ("ok" if r["order_ok"] else "**wrong**")
        row = (
            f"| `{r['fixture']}` | {r['request']} | {r['n_candidates']} | {len(r['picked'])} "
            f"| {_pct(r['recall'])} | {_pct(r['precision'])} | {order} "
            f"| {'**' + defects + '**' if r['hard_fail'] else defects} |"
        )
        lines.append(row)
    lines.append("")
    for r in results:
        if r["missed"] or r["leaked"]:
            detail = []
            if r["missed"]:
                detail.append(f"missed {', '.join('`' + i + '`' for i in r['missed'])}")
            if r["leaked"]:
                detail.append(f"leaked {', '.join('`' + i + '`' for i in r['leaked'])}")
            lines.append(f"- `{r['fixture']}`: {'; '.join(detail)}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- main


def run_fixture(fixture: dict, sweeps_dir: Path, roster: list[dict], runner: Runner) -> dict:
    day_dir = sweeps_dir / fixture["date"]
    candidates = load_day(day_dir, roster)
    if not candidates:
        return {
            "fixture": fixture["id"],
            "date": fixture["date"],
            "request": fixture["request"],
            "n_candidates": 0,
            "picked": [],
            "defects": ["no_corpus"],
            "hard_fail": True,
            "hard_defects": ["no_corpus"],
            "refusal_ok": True,
            "missed": [],
            "leaked": [],
            "recall": None,
            "precision": None,
            "order_ok": None,
        }
    prompt = build_prompt(candidates, fixture["request"])
    try:
        raw = runner(prompt)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raw = ""
        sys.stderr.write(f"[{fixture['id']}] runner error: {e}\n")
    ordinals, defects = decode(raw, len(candidates))
    return grade(fixture, candidates, ordinals, defects)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="qwen2.5:7b", help="Ollama model tag")
    ap.add_argument("--sweeps-dir", default=str(ROOT / "data" / "sweeps"))
    ap.add_argument("--roster", default=str(ROOT / "sweeps" / "topics.json"))
    ap.add_argument("--fixtures", default=str(ROOT / "sweeps" / "fixtures" / "reshape_requests.json"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "local-reader-grades.md"))
    ap.add_argument("--list-fixtures", action="store_true", help="what would run; no model call")
    ap.add_argument("--dry-run", action="store_true", help="print prompts; no model call")
    ap.add_argument("--report", action="store_true", help="append the verdict table to --out")
    ap.add_argument(
        "--show-day",
        metavar="DATE",
        help="print a day's items with their ordinals and ids — the authoring aid for gold sets",
    )
    args = ap.parse_args(argv)

    # Authoring aid: gold sets are written in item ids, which are derived, so there is no
    # way to write a fixture without seeing them first.
    if args.show_day:
        roster = load_roster(Path(args.roster))
        candidates = load_day(Path(args.sweeps_dir) / args.show_day, roster)
        if not candidates:
            sys.stderr.write(f"no readable items under {args.sweeps_dir}/{args.show_day}\n")
            return 2
        for c in candidates:
            print(f"[{c['ordinal']:>3}] {c['id']}  ({c['topic']}) {c['headline']}")
        return 0

    try:
        fixtures = load_fixtures(Path(args.fixtures))
    except FileNotFoundError:
        sys.stderr.write(
            f"fixtures: {args.fixtures} not found.\n"
            "Gold sets encode Kyle's judgment and are authored by hand — copy\n"
            "sweeps/fixtures/reshape_requests.example.json and fill it in. Use\n"
            "  python3 sweeps/local_reader_bench.py --show-day <date>\n"
            "to list a day's items with the ids the gold sets reference.\n"
        )
        return 2
    except (OSError, ValueError) as e:
        sys.stderr.write(f"fixtures: {e}\n")
        return 2
    if not fixtures:
        sys.stderr.write("fixtures: none defined — nothing to grade\n")
        return 2

    roster = load_roster(Path(args.roster))
    sweeps_dir = Path(args.sweeps_dir)

    if args.list_fixtures:
        for fx in fixtures:
            n = len(load_day(sweeps_dir / fx["date"], roster))
            print(f"{fx['id']:<28} {fx['date']}  {n:>3} items  {fx['request']}")
        return 0

    if args.dry_run:
        for fx in fixtures:
            candidates = load_day(sweeps_dir / fx["date"], roster)
            print(f"\n===== {fx['id']} ({fx['date']}, {len(candidates)} items) =====")
            print(build_prompt(candidates, fx["request"]) if candidates else "(no corpus)")
        return 0

    runner = ollama_runner(args.model)
    results = [run_fixture(fx, sweeps_dir, roster, runner) for fx in fixtures]

    day = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    report = render_report(args.model, results, day)
    print(report)

    if args.report:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        prior = out.read_text(encoding="utf-8") if out.exists() else ""
        header = "# Local reader bake-off — graded runs\n\n_Newest first. Bar and method:\n`docs/LOCAL_READER_BAKEOFF_PLAN.md`._\n\n"
        if prior.startswith("# "):
            body = prior.split("\n\n", 2)[-1]
            out.write_text(header + report + "\n" + body, encoding="utf-8")
        else:
            out.write_text(header + report, encoding="utf-8")

    return 1 if any(r["hard_fail"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
