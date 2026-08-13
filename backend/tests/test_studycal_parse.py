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


def test_multi_day_exclusions_exclude_every_named_day() -> None:
    # An exclusion listing several days used to consume only the FIRST one; the leftover tail was
    # then re-read as a positive pick, so the plan landed exclusively on a day Kyle ruled out.
    assert parse_preference("not Mondays or Fridays", [0, 1, 2, 3, 4])["days_of_week"] == [1, 2, 3]
    assert parse_preference("except Saturdays and Sundays", None)["days_of_week"] == [0, 1, 2, 3, 4]
    assert parse_preference("not mon, wed, or fri", [0, 1, 2, 3, 4])["days_of_week"] == [1, 3]
    assert parse_preference("skip Tue/Thu", [0, 1, 2, 3, 4])["days_of_week"] == [0, 2, 4]
    assert parse_preference("no weekends nor mondays", None)["days_of_week"] == [1, 2, 3, 4]


def test_a_multi_day_exclusion_does_not_swallow_the_rest_of_the_note() -> None:
    # The exclusion span must end at the day list — "mornings" still has to reach the window pass.
    assert parse_preference("no saturday or sunday mornings", None) == {
        "days_of_week": [0, 1, 2, 3, 4],
        "day_start_hour": 8,
        "day_end_hour": 12,
    }
    # A trailing non-day word after a connector must not be eaten either.
    assert parse_preference("except Friday orientation", [0, 1, 2, 3, 4])["days_of_week"] == [0, 1, 2, 3]


def test_exclusion_trigger_words_do_not_misfire_on_time_phrases() -> None:
    # "no"/"not" also open the window triggers ("no earlier than", "not before") — widening the day
    # regex must not start eating those.
    assert parse_preference("no earlier than 2:00 p.m.", None) == {"day_start_hour": 14}
    assert parse_preference("no later than 5 p.m.", None) == {"day_end_hour": 17}
    assert parse_preference("no more than 2 blocks", None) == {"max_blocks": 2}
    # Tightened: this asserted only that no DAY override leaked out, which left the spurious
    # `day_end_hour` the end pass used to read back out of this very phrase unguarded.
    assert parse_preference("not before 2pm", None) == {"day_start_hour": 14}


# -- time-of-day window --------------------------------------------------------

def test_before_and_after() -> None:
    assert parse_preference("weekdays before 2pm", None) == {"days_of_week": [0, 1, 2, 3, 4], "day_end_hour": 14}
    assert parse_preference("after 9am", None) == {"day_start_hour": 9}
    assert parse_preference("no later than 5 p.m.", None) == {"day_end_hour": 17}
    assert parse_preference("no earlier than 2:00 p.m.", None) == {"day_start_hour": 14}


def test_a_negated_after_bounds_the_end_instead_of_starting_there() -> None:
    # A negated "after" names the hours to AVOID. The start trigger guarded it with two literal
    # lookbehinds — ``(?<!not )(?<!no )`` — which can only see the word immediately before it, so
    # every other negation read as a START and scheduled precisely the band the note ruled out.
    assert parse_preference("nothing after 3pm", None) == {"day_end_hour": 15}
    assert parse_preference("never after 3pm", None) == {"day_end_hour": 15}
    assert parse_preference("none after 3pm", None) == {"day_end_hour": 15}
    # …including the form with a noun between the negation and the trigger.
    assert parse_preference("no sessions after 3pm", None) == {"day_end_hour": 15}
    # The one spelling the old lookbehinds did catch keeps its meaning.
    assert parse_preference("not after 3pm", None) == {"day_end_hour": 15}
    # And an unnegated "after" is still a start bound — the guard must not swallow the plain form.
    assert parse_preference("after 3pm", None) == {"day_start_hour": 15}


def test_a_negated_start_phrase_is_not_re_read_as_an_end() -> None:
    # The end trigger carries a bare ``before``/``until`` and its search ran over the untouched
    # text, so it fired INSIDE the start phrase it had already been matched by — collapsing the
    # whole day to a single hour ("not before 2pm" -> 14:00–14:00).
    assert parse_preference("not before 2pm", None) == {"day_start_hour": 14}
    assert parse_preference("not until 3pm", None) == {"day_start_hour": 15}
    assert parse_preference("nothing before 2pm", None) == {"day_start_hour": 14}
    assert parse_preference("no blocks until 10am", None) == {"day_start_hour": 10}
    # A named window supplies the end; the negated start must refine it, not destroy it.
    assert parse_preference("evenings but not before 7pm", None) == {
        "day_start_hour": 19,
        "day_end_hour": 21,
    }


def test_a_repeated_negated_bound_does_not_leak_into_the_opposite_direction() -> None:
    # Review F1. Each scan consumed only its FIRST match, so a note stating the same edge twice
    # left the second phrase for the plain pass whose trigger word it happens to contain — and it
    # was read backwards. "no sessions after 5pm, nothing after 3pm" planned 15:00–17:00: inside
    # the band BOTH clauses rule out. Repeated bounds keep the first (the leftmost-per-edge rule).
    assert parse_preference("no sessions after 5pm, nothing after 3pm on fridays", None) == {
        "days_of_week": [4],
        "day_end_hour": 17,
    }
    assert parse_preference("nothing before 9am, nothing before 11am", None) == {"day_start_hour": 9}
    assert parse_preference("nothing after 3pm, nothing after 1pm", None) == {"day_end_hour": 15}


def test_a_negation_spent_on_a_day_exclusion_does_not_also_flip_a_time_bound() -> None:
    # Review F2. The gap between the negation and the trigger was any word, so a DAY exclusion's
    # "no"/"not" reached across the day token and flipped the following start bound into an end —
    # a regression the merge-base did not have. The gap words are an allow-list now.
    assert parse_preference("no weekends after 3pm", None) == {
        "days_of_week": [0, 1, 2, 3, 4],
        "day_start_hour": 15,
    }
    assert parse_preference("not Mondays after 3pm", None)["day_start_hour"] == 15
    assert parse_preference("no weekend sessions after 3pm", None)["day_start_hour"] == 15
    # …and the reading no longer depends on punctuation or on how many words the day list spends.
    assert parse_preference("no weekends, after 3pm", None)["day_start_hour"] == 15
    assert parse_preference("not Tuesdays or Thursdays after 3pm", None)["day_start_hour"] == 15


def test_an_availability_statement_is_not_read_as_an_exclusion() -> None:
    # Review F5, the same allow-list from the other side: "I have no meetings after 3pm" says the
    # hours are FREE. Only the nouns naming the thing being scheduled flip the bound.
    assert parse_preference("I have no meetings after 3pm so schedule then", None) == {"day_start_hour": 15}
    assert parse_preference("no classes after 3pm", None) == {"day_start_hour": 15}
    assert parse_preference("no lunch break until 1pm", None) == {"day_end_hour": 13}
    # The scheduling nouns still flip it — that is the whole point of the negated form.
    assert parse_preference("no more sessions after 3pm", None) == {"day_end_hour": 15}
    assert parse_preference("no study after 3pm", None) == {"day_end_hour": 15}


def test_both_bounds_can_be_stated_negatively_in_one_note() -> None:
    # The realistic phrasing: both edges named by what they exclude, in one sentence.
    assert parse_preference("weekdays, nothing before 9am and nothing after 3pm", None) == {
        "days_of_week": [0, 1, 2, 3, 4],
        "day_start_hour": 9,
        "day_end_hour": 15,
    }


def test_ranges() -> None:
    assert parse_preference("between 2 and 5pm", None) == {"day_start_hour": 14, "day_end_hour": 17}
    assert parse_preference("2-5pm", None) == {"day_start_hour": 14, "day_end_hour": 17}
    assert parse_preference("9am to 11am", None) == {"day_start_hour": 9, "day_end_hour": 11}


def test_a_shared_meridiem_range_reads_the_first_number_as_am() -> None:
    # "9 to 5pm" is the commonest English range there is. Borrowing the pm from the second time
    # gave 21:00-17:00, which the API then "repaired" into a single hour at 9 PM and persisted.
    assert parse_preference("9 to 5pm", None) == {"day_start_hour": 9, "day_end_hour": 17}
    assert parse_preference("11 to 2pm", None) == {"day_start_hour": 11, "day_end_hour": 14}
    assert parse_preference("between 9 and 5 pm", None) == {"day_start_hour": 9, "day_end_hour": 17}
    # Where borrowing the meridiem DOES yield a sane window, it still wins ("2 to 5pm" is 2 PM).
    assert parse_preference("2 to 5pm", None) == {"day_start_hour": 14, "day_end_hour": 17}


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
