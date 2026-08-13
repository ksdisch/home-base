"""app.studycal.parse — the deterministic free-text preference parser (v1).

Turns a plain-English scheduling note ("sixty-minute blocks every weekday, no earlier than 2pm, no
later than 5pm") into a dict of planner-knob overrides that **refine the current controls**. Pure +
deterministic: no clock, no network, no LLM — so the "describe it" box works instantly and always,
even when the ``claude -p`` fallback lane is unreachable (the always-on server can't see the CLI). The
API applies these overrides on top of the controls the user already has; the claude lane is only a
fallback for phrasings this parser doesn't recognize (an empty return).

Weekday ints are Python ``weekday()`` — Mon=0 … Sun=6. Only keys the text actually specifies appear.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

# -- number words (for session length, mostly) --------------------------------
_WORDNUM = {
    "ten": 10, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30,
    "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "seventy-five": 75,
    "ninety": 90, "one": 1, "two": 2, "three": 3,
}
_WORDNUM_ALT = "|".join(sorted((re.escape(w) for w in _WORDNUM), key=len, reverse=True))

# -- day tokens ---------------------------------------------------------------
# (regex fragment, weekday int) — ordered so longer names are tried before abbreviations.
_DAY_PATTERNS = [
    (r"mondays?", 0), (r"tuesdays?", 1), (r"wednesdays?", 2), (r"thursdays?", 3),
    (r"fridays?", 4), (r"saturdays?", 5), (r"sundays?", 6),
    (r"mon", 0), (r"tues?", 1), (r"weds?", 2), (r"thurs?|thu", 3),
    (r"fri", 4), (r"sat", 5), (r"sun", 6),
]
_WEEKDAYS = {0, 1, 2, 3, 4}
_WEEKEND = {5, 6}
_ALL_DAYS = {0, 1, 2, 3, 4, 5, 6}

# A single token usable after an exclusion word (not/except/skip …).
_DAY_TOKEN = (
    r"weekends?|weekdays?|mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?|"
    r"mon|tues?|weds?|thurs?|thu|fri|sat|sun"
)
# Connectors joining days in one exclusion ("not Mondays or Fridays", "skip Tue/Thu", "no mon, wed,
# and fri"). Word-boundaried on the alphabetic ones so "Friday orientation" doesn't read "or".
# The word connectors come FIRST so ", or " is consumed whole — a bare-comma branch tried first
# would eat only ", " and strand the "or", which matters when splitting the captured list.
_DAY_CONN = r"(?:\s*,?\s+(?:and|or|nor)\s+|\s*,\s*|\s*[/&]\s*)"
# The capture is the WHOLE day list after the trigger, not just the first token — matching only one
# left the rest of the list in the text, where the positive pass then read it as a day to *select*.
# Every alternation is wrapped in (?:...) so the repetition binds to the group, not the last branch.
_EXCLUDE_RE = re.compile(
    r"\b(?:not|no|except|excluding|skip(?:ping)?|without|minus)\s+(?:on\s+)?"
    r"((?:" + _DAY_TOKEN + r")(?:" + _DAY_CONN + r"(?:" + _DAY_TOKEN + r"))*)\b",
    re.I,
)
_DAY_SPLIT_RE = re.compile(_DAY_CONN, re.I)

# -- times --------------------------------------------------------------------
_MER = r"[ap]\.?\s*m\.?"
_TIME = r"(\d{1,2})(?::(\d{2}))?\s*(" + _MER + r")"  # meridiem required (avoids ambiguous bare hours)

_START_TRIG = r"(?:no earlier than|starting at|start at|beginning at|begin at|after|from)"
_END_TRIG = r"(?:no later than|ending at|end at|before|by|until|til|till)"

# A negated bound names the hours to AVOID, so it sets the OPPOSITE edge: "nothing after 3pm"
# closes the day at 3, "not before 2pm" opens it at 2. The negation and the trigger it flips are
# often separated by a noun ("no sessions after 3pm"), which a lookbehind can't express — Python's
# `re` requires them fixed-width, and the two literal ones this replaces ((?<!not )(?<!no )) saw
# only the word immediately before `after`, so every other negation read as a start.
_NEG = r"\b(?:nothing|never|none|not|no)\b"
_NEG_GAP = r"(?:\s+\w+){0,2}\s+"
_NEG_END_TRIG = _NEG + _NEG_GAP + r"after"
_NEG_START_TRIG = _NEG + _NEG_GAP + r"(?:before|until|till|til)"

# Scan order. The negated forms go first because each one's own trigger word belongs to the OTHER
# direction — "nothing after 3pm" carries the start pattern's `after`, "not before 2pm" carries the
# end pattern's `before` — so whichever runs second would otherwise fire a second time inside the
# phrase the first already consumed.
_WINDOW_SCANS = (
    ("day_end_hour", _NEG_END_TRIG),
    ("day_start_hour", _NEG_START_TRIG),
    ("day_start_hour", _START_TRIG),
    ("day_end_hour", _END_TRIG),
)

_NAMED_WINDOWS = [
    (r"mornings?", (8, 12)),
    (r"afternoons?", (12, 17)),
    (r"evenings?", (17, 21)),
    (r"nights?", (18, 22)),
]

# range forms: "between 2 and 5pm" · "2-5pm" · "9am to 11am" (second time must carry a meridiem)
_RANGE_BETWEEN = re.compile(
    r"between\s+(\d{1,2})(?::\d{2})?\s*(" + _MER + r")?\s*(?:and|to|-|through|until)\s*(\d{1,2})(?::\d{2})?\s*(" + _MER + r")",
    re.I,
)
_RANGE_DASH = re.compile(
    r"(\d{1,2})(?::\d{2})?\s*(" + _MER + r")?\s*(?:-|–|—|to|through|until)\s*(\d{1,2})(?::\d{2})?\s*(" + _MER + r")",
    re.I,
)

_BLOCKS_RE = re.compile(
    r"(?:at most|no more than|up to|max(?:imum)?(?: of)?|only|just)\s*(\d+)\s*blocks?", re.I
)


def _hour(h: str, mer: Optional[str]) -> int:
    n = int(h)
    is_pm = bool(mer) and mer.strip().lower().startswith("p")
    is_am = bool(mer) and mer.strip().lower().startswith("a")
    if is_pm and n != 12:
        n += 12
    if is_am and n == 12:
        n = 0
    return max(0, min(24, n))


def _expand_day_token(tok: str) -> Set[int]:
    tok = tok.lower()
    if tok.startswith("weekend"):
        return set(_WEEKEND)
    if tok.startswith("weekday"):
        return set(_WEEKDAYS)
    for pat, idx in _DAY_PATTERNS:
        if re.fullmatch(pat, tok):
            return {idx}
    return set()


def _parse_session(t: str) -> Optional[int]:
    if re.search(r"\bhour and a half\b|\ban hour and a half\b|\b1\.5\s*h(?:ou)?rs?\b", t, re.I):
        return 90
    if re.search(r"\bhalf[ -](?:an )?hour\b|\bhalf hour\b", t, re.I):
        return 30
    m = re.search(r"\b(\d+)\s*[-]?\s*(?:minutes?|mins?)\b", t, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(" + _WORDNUM_ALT + r")\s*[-]?\s*(?:minutes?|mins?)\b", t, re.I)
    if m:
        return _WORDNUM.get(m.group(1).lower())
    m = re.search(r"\b(\d+)\s*(?:hours?|hrs?)\b", t, re.I)
    if m:
        return int(m.group(1)) * 60
    if re.search(r"\b(?:an|one|1|a)\s+hour\b|\bhour[- ]long\b", t, re.I):
        return 60
    return None


def _parse_days(t: str, current_days: Optional[Iterable[int]]) -> Optional[List[int]]:
    excluded: Set[int] = set()
    for m in _EXCLUDE_RE.finditer(t):
        for tok in _DAY_SPLIT_RE.split(m.group(1)):
            excluded |= _expand_day_token(tok.strip())
    positive = _EXCLUDE_RE.sub(" ", t)  # blank out exclusion spans so they aren't re-read as positive

    base: Set[int] = set()
    explicit = False
    if re.search(r"\bevery day\b|\ball days\b|\bany day\b|\bdaily\b|\beach day\b", positive, re.I):
        base |= _ALL_DAYS
        explicit = True
    if re.search(r"\bweekdays?\b", positive, re.I):
        base |= _WEEKDAYS
        explicit = True
    if re.search(r"\bweekends?\b", positive, re.I):
        base |= _WEEKEND
        explicit = True
    for pat, idx in _DAY_PATTERNS:
        if re.search(r"\b(?:" + pat + r")\b", positive, re.I):
            base.add(idx)
            explicit = True

    if not explicit and not excluded:
        return None
    if not explicit:  # exclusion-only ("not Mondays") refines the current selection
        base = set(current_days) if current_days else set(_ALL_DAYS)
    result = sorted(base - excluded)
    return result or None  # never zero out the week; drop the override instead


def _parse_window(t: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for pat, (s, e) in _NAMED_WINDOWS:
        if re.search(r"\b" + pat + r"\b", t, re.I):
            out["day_start_hour"], out["day_end_hour"] = s, e
            break

    rng = _RANGE_BETWEEN.search(t) or _RANGE_DASH.search(t)
    if rng:
        h1, mer1, h2, mer2 = rng.group(1), rng.group(2), rng.group(3), rng.group(4)
        end = _hour(h2, mer2)
        start = _hour(h1, mer1 or mer2)
        if mer1 is None and start >= end:
            # "9 to 5pm": borrowing the second time's meridiem inverts the window, so the bare
            # first number was meant as AM. Pick whichever reading gives a real same-day span.
            alt = _hour(h1, "am")
            if alt < end:
                start = alt
        out["day_start_hour"], out["day_end_hour"] = start, end

    # Each accepted match is blanked out of the working copy before the next search — the same
    # trick `_parse_days` uses for exclusion spans — so one phrase can never satisfy two triggers.
    # Blanking keeps the string length, so offsets stay comparable across scans: for a given edge,
    # the leftmost match in the note wins, which is what the single searches this replaces did.
    work = t
    seen: Dict[str, int] = {}
    for key, trig in _WINDOW_SCANS:
        m = re.search(trig + r"\s+" + _TIME, work, re.I)
        if m is None:
            continue
        if key not in seen or m.start() < seen[key]:
            seen[key] = m.start()
            out[key] = _hour(m.group(1), m.group(3))
        work = work[: m.start()] + " " * (m.end() - m.start()) + work[m.end() :]
    return out


def _parse_max_blocks(t: str) -> Optional[int]:
    m = _BLOCKS_RE.search(t)
    return int(m.group(1)) if m else None


def parse_preference(text: str, current_days: Optional[Iterable[int]]) -> Dict[str, Any]:
    """Free-text note -> planner-knob overrides (subset of ``session_minutes``, ``day_start_hour``,
    ``day_end_hour``, ``days_of_week`` [sorted list], ``max_blocks``). Refines ``current_days`` for
    exclusion phrases like "not Mondays". ``{}`` when nothing is recognized (the API then tries the
    claude fallback)."""
    if not text or not text.strip():
        return {}
    t = text.strip()
    out: Dict[str, Any] = {}

    session = _parse_session(t)
    if session is not None:
        out["session_minutes"] = max(10, min(180, session))

    days = _parse_days(t, current_days)
    if days is not None:
        out["days_of_week"] = days

    out.update(_parse_window(t))

    blocks = _parse_max_blocks(t)
    if blocks is not None:
        out["max_blocks"] = max(1, min(20, blocks))

    return out
