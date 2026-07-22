"""app.studycal.parse — the deterministic free-text preference parser (v1).

Kyle's call (2026-07-22, after the claude -p lane proved unreachable from the always-on server): the
"describe it" box should work locally with **no** LLM dependency for the common patterns — days,
time-of-day windows, session length, max blocks — refining whatever the controls currently show. The
claude lane stays only as a fallback for phrasings the parser doesn't recognize. Pure + deterministic,
so every rule is asserted directly.
"""

from __future__ import annotations

from app.studycal.parse import parse_preference


# -- Kyle's exact sentence (the bug report) ------------------------------------

def test_kyles_exact_sentence() -> None:
    text = (
        "Sixty-minute blocks every weekday, and the blocks need to begin no earlier than 2:00 p.m. "
        "And no later than 5 p.m."
    )
    out = parse_preference(text, current_days=None)
    assert out == {
        "session_minutes": 60,
        "days_of_week": [0, 1, 2, 3, 4],
        "day_start_hour": 14,
        "day_end_hour": 17,
    }


# -- days ----------------------------------------------------------------------

def test_weekdays_and_weekends() -> None:
    assert parse_preference("weekdays only", None)["days_of_week"] == [0, 1, 2, 3, 4]
    assert parse_preference("no weekends please", None)["days_of_week"] == [0, 1, 2, 3, 4]
    assert parse_preference("weekends", None)["days_of_week"] == [5, 6]
    assert parse_preference("every day", None)["days_of_week"] == [0, 1, 2, 3, 4, 5, 6]


def test_specific_days() -> None:
    assert parse_preference("Tuesdays and Thursdays", None)["days_of_week"] == [1, 3]
    assert parse_preference("only mon, wed, fri", None)["days_of_week"] == [0, 2, 4]


def test_exclusions_refine_current_days() -> None:
    # "not Mondays" drops Monday from whatever is currently selected.
    assert parse_preference("not Mondays", current_days=[0, 1, 2, 3, 4])["days_of_week"] == [1, 2, 3, 4]
    # With no current restriction (all days), it removes Monday from the full week.
    assert parse_preference("no mondays", current_days=None)["days_of_week"] == [1, 2, 3, 4, 5, 6]
    assert parse_preference("except Friday", current_days=[0, 1, 2, 3, 4])["days_of_week"] == [0, 1, 2, 3]


# -- time-of-day window --------------------------------------------------------

def test_before_and_after() -> None:
    assert parse_preference("weekdays before 2pm", None) == {"days_of_week": [0, 1, 2, 3, 4], "day_end_hour": 14}
    assert parse_preference("after 9am", None) == {"day_start_hour": 9}
    assert parse_preference("no later than 5 p.m.", None) == {"day_end_hour": 17}
    assert parse_preference("no earlier than 2:00 p.m.", None) == {"day_start_hour": 14}


def test_ranges() -> None:
    assert parse_preference("between 2 and 5pm", None) == {"day_start_hour": 14, "day_end_hour": 17}
    assert parse_preference("2-5pm", None) == {"day_start_hour": 14, "day_end_hour": 17}
    assert parse_preference("9am to 11am", None) == {"day_start_hour": 9, "day_end_hour": 11}


def test_named_windows() -> None:
    assert parse_preference("mornings", None) == {"day_start_hour": 8, "day_end_hour": 12}
    assert parse_preference("weekday afternoons", None) == {
        "days_of_week": [0, 1, 2, 3, 4],
        "day_start_hour": 12,
        "day_end_hour": 17,
    }
    assert parse_preference("evenings", None) == {"day_start_hour": 17, "day_end_hour": 21}


# -- session length ------------------------------------------------------------

def test_session_length() -> None:
    assert parse_preference("45 minute sessions", None) == {"session_minutes": 45}
    assert parse_preference("make them 30 min", None) == {"session_minutes": 30}
    assert parse_preference("one hour blocks", None) == {"session_minutes": 60}
    assert parse_preference("half hour", None) == {"session_minutes": 30}
    assert parse_preference("90-minute sessions", None) == {"session_minutes": 90}


# -- max blocks ----------------------------------------------------------------

def test_max_blocks() -> None:
    assert parse_preference("at most 3 blocks", None) == {"max_blocks": 3}
    assert parse_preference("no more than 2 blocks", None) == {"max_blocks": 2}
    assert parse_preference("up to 4 blocks", None) == {"max_blocks": 4}
    # "sixty-minute blocks" must NOT be read as 60 max blocks (the number belongs to the session).
    assert "max_blocks" not in parse_preference("sixty-minute blocks", None)


# -- nothing recognized (→ the API falls back to claude) -----------------------

def test_unrecognized_returns_empty() -> None:
    assert parse_preference("surprise me", None) == {}
    assert parse_preference("", None) == {}


# -- combined refinement -------------------------------------------------------

def test_combined() -> None:
    out = parse_preference("weekday mornings, 45 min, at most 3 blocks", None)
    assert out == {
        "days_of_week": [0, 1, 2, 3, 4],
        "day_start_hour": 8,
        "day_end_hour": 12,
        "session_minutes": 45,
        "max_blocks": 3,
    }
