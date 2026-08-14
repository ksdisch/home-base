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
    # "work" is ambiguous the same way and is deliberately NOT on the list (review F6's residual).
    assert parse_preference("I have no work after 3pm so schedule then", None) == {"day_start_hour": 15}
    # The scheduling nouns still flip it — that is the whole point of the negated form.
    assert parse_preference("no more sessions after 3pm", None) == {"day_end_hour": 15}
    assert parse_preference("no study after 3pm", None) == {"day_end_hour": 15}


def test_an_unspendable_negation_reads_any_noun() -> None:
    # Review F6. `nothing`/`never`/`none` are neither exclusion triggers nor availability phrasings,
    # so restricting THEM to the scheduling-noun allow-list (added for F2) re-opened the headline
    # bug for ordinary wording — and for the `before` form it was worse than either side of this
    # branch, because the end-only misread was then faithfully honored by F3's repair.
    assert parse_preference("nothing scheduled after 3pm", None) == {"day_end_hour": 15}
    assert parse_preference("nothing planned after 3pm", None) == {"day_end_hour": 15}
    assert parse_preference("nothing at all after 3pm", None) == {"day_end_hour": 15}
    assert parse_preference("nothing scheduled before 9am", None) == {"day_start_hour": 9}
    assert parse_preference("never any homework after 6pm", None) == {"day_end_hour": 18}
    # The split is on which negators `_EXCLUDE_RE` can ALSO spend as a day exclusion — `no`/`not`
    # can, so they keep the allow-list and F2/F5 stay closed on the very same nouns.
    assert parse_preference("no meetings after 3pm", None) == {"day_start_hour": 15}
    assert parse_preference("not Mondays after 3pm", None)["day_start_hour"] == 15


def test_an_exclusion_the_parser_cannot_read_yields_nothing_not_the_opposite() -> None:
    # Reviews F8/F10/F11 — the structural lesson from four rounds of retuning the gap: a gap MISS
    # never produced "no reading", it produced the BACKWARDS reading, confidently, and a non-empty
    # parse short-circuits the claude fallback that might have read it. `nothing`/`never`/`none`
    # have exactly one sense, so failing to read one now withholds the window entirely.
    #
    # A negated RANGE (F11): "nothing from 9am until 5pm" is a workday, the commonest exclusion
    # there is. Applying the range would schedule every block inside the band it rules out.
    for note in (
        "nothing from 9am until 5pm",
        "never from 9am until 5pm",
        "nothing 9am until 5pm",
        "nothing from 9am till 5pm",
        "nothing between 9am and 5pm",
        "nothing 9am-5pm",
    ):
        assert parse_preference(note, None) == {}, note
    # An ordinary preposition inside the noun phrase (F10) — the gap can't read it, so it says
    # nothing rather than inverting the bound.
    for note in (
        "nothing from work after 3pm",
        "nothing from home before 9am",
        "nothing between meetings before 9am",
        "nothing by phone before 9am",
    ):
        assert parse_preference(note, None) == {}, note
    # The withholding is scoped to the single-sense negators: `no`/`not` really can mean a day
    # exclusion or an availability statement, so a non-match there still reads as a plain bound.
    assert parse_preference("no meetings after 3pm", None) == {"day_start_hour": 15}
    assert parse_preference("no weekends after 3pm", None)["day_start_hour"] == 15


def test_a_negated_day_clause_does_not_veto_a_window_stated_beside_it() -> None:
    # Review F14. The withholding guard was note-level, so any `nothing` anywhere threw the WHOLE
    # window away — including one stated plainly in another clause. "nothing on Sundays" is a day
    # phrase, not a window exclusion, and the escape hatch didn't even fire: `_parse_days` still
    # returned days, so the note was non-empty and never reached the claude lane. The learner who
    # asked for evenings got a 09:00 block and no message.
    # Asserts the WINDOW only. The day list is a known wrong result on this phrasing and is not
    # what this test is about: `nothing`/`never`/`none` are not `_EXCLUDE_RE` triggers, so
    # `_parse_days` reads "Sundays" positively and SCHEDULES the day the note excludes. Untouched
    # by this branch, owned by no finding yet — see the review-F18 note in the PR (review F12's
    # precedent: an exact-dict pin must never freeze a defect silently).
    out = parse_preference("weekday evenings, nothing on Sundays", None)
    assert out["day_start_hour"] == 17 and out["day_end_hour"] == 21
    assert parse_preference("mornings only, nothing on Fridays", None)["day_start_hour"] == 8
    assert parse_preference("9am to 5pm, nothing on Fridays", None)["day_end_hour"] == 17
    assert parse_preference("start at 2pm, nothing on Tuesdays", None)["day_start_hour"] == 14
    assert parse_preference("1 hour blocks in the mornings, none on the weekend", None)["day_end_hour"] == 12


def test_a_readable_negation_does_not_vouch_for_an_unreadable_one() -> None:
    # Review F15. The guard was one boolean set by ANY negated match, so a readable clause
    # re-enabled the backwards reading of an unreadable one — the plan landed after 3pm, the band
    # the note excludes, and the stated 2pm start was dropped. The check is per occurrence now.
    assert parse_preference("nothing from work after 3pm, not before 2pm", None) == {}
    assert parse_preference("no more before 2pm, nothing between meetings after 6pm", None) == {}
    # Two readable negations in one note still read normally — being unread is what withholds.
    assert parse_preference("nothing before 9am and nothing after 3pm", None) == {
        "day_start_hour": 9,
        "day_end_hour": 15,
    }
    # Leftmost-per-edge keeps the 5pm, so Friday plans still run 15:00–17:00 — inside the band the
    # second clause rules out. Same known gap the test above pins; asserted here only to show that
    # BOTH negations were read, which is what stops the withholding guard from firing.
    assert parse_preference("no sessions after 5pm, nothing after 3pm on fridays", None) == {
        "days_of_week": [4],
        "day_end_hour": 17,
    }


def test_a_negated_named_window_is_never_read_as_the_window_to_schedule() -> None:
    # Review F16. The guard only withheld when a clock time (digits + meridiem) sat in the clause,
    # so a negation over a NAMED window slipped through and `_NAMED_WINDOWS` handed back exactly
    # the band the note rules out — "nothing in the afternoon" planned a 12:00 block and persisted
    # 12/17, with no message. A named window is a time for the guard's purposes.
    for note in (
        "nothing in the afternoon",
        "nothing in the mornings",
        "never in the evenings",
        "nothing at night",
        "nothing during the morning",
    ):
        assert parse_preference(note, None) == {}, note
    # Updated for review F21: the WHOLE note is dropped, not just the window. Returning the days
    # here would be the quiet failure — a non-empty result short-circuits the claude lane, so the
    # standing window (the one this note was narrowing) gets planned and persisted with no message.
    assert parse_preference("weekdays, nothing in the evening", None) == {}
    # An unnegated named window is untouched.
    assert parse_preference("mornings", None) == {"day_start_hour": 8, "day_end_hour": 12}


def test_a_day_exclusion_never_vetoes_the_window_whatever_joins_the_clauses() -> None:
    # Review F17. The clause rule ended only at `,` or `;`, so an `and`/`but` join let a day
    # negator's clause swallow the window's own time and veto it — the same silent drop as F14,
    # answering two notes that mean the same thing differently. A negator followed by a day phrase
    # is now skipped structurally, with no punctuation involved.
    assert parse_preference("nothing on Fridays and 9am to 5pm", None) == {
        "days_of_week": [4], "day_start_hour": 9, "day_end_hour": 17,
    }
    assert parse_preference("nothing on Fridays and no later than 5pm", None)["day_end_hour"] == 17
    assert parse_preference("nothing on Sundays but 9am to 5pm otherwise", None)["day_start_hour"] == 9


def test_an_exclusion_of_hours_on_named_days_is_not_mistaken_for_a_day_exclusion() -> None:
    # Review F20. The day-phrase skip ran BEFORE the time test and was unconditional, so a clause
    # that excludes hours *on* days was skipped, its `after` handed to the forward scan, and the
    # band it rules out planned and persisted. The single-day form was unaffected (it fits inside
    # the two-word gap), so the answer depended on how many days the learner named.
    for note in (
        "nothing on saturdays or sundays after 3pm",
        "nothing on Mondays or Fridays until 5pm",
        "nothing on the weekend after 3pm",
        "never on the weekends after 8pm",
        "nothing on tues/thurs after 4pm",
        "60 minute blocks every weekday, nothing on mon or fri after 4pm",
        # …and the same for a day-qualified NAMED window, which review F16 closed for the bare form.
        "nothing on Mondays or Wednesdays in the afternoon",
        "nothing Friday afternoons",
    ):
        assert parse_preference(note, None) == {}, note
    # A day exclusion that really does end at the day list is still skipped, whatever joins it on.
    assert parse_preference("nothing on Fridays and 9am to 5pm", None)["day_end_hour"] == 17
    assert parse_preference("weekday evenings, nothing on Sundays", None)["day_start_hour"] == 17


def test_an_unreadable_window_drops_the_whole_note_so_the_fallback_lane_runs() -> None:
    # Review F21. Withholding only the window was not the honest floor it claimed to be: the days
    # and the session length still parsed, so the note was non-empty, the claude lane was
    # short-circuited, and the STANDING window — the one the note was narrowing — got planned with
    # no message. Against a busy calendar that booked blocks inside the excluded band.
    assert parse_preference("45 minute blocks, nothing in the evening, 9am to 5pm", None) == {}
    assert parse_preference("nothing scheduled on Friday mornings, 9am to 5pm otherwise", None) == {}
    # Readable notes are untouched — this drops the note only when a stated exclusion went unread.
    assert parse_preference("45 minute blocks, nothing after 5pm, weekdays", None) == {
        "session_minutes": 45,
        "days_of_week": [0, 1, 2, 3, 4],
        "day_end_hour": 17,
    }
    # …and a `nothing` that governs no time at all is not an unread exclusion, so it withholds
    # nothing. Added because the mutation that drops the clause+time scoping killed ZERO tests:
    # every case then in the suite was covered by the day-phrase skip, leaving this shape unpinned.
    assert parse_preference("nothing fancy, 9am to 5pm", None) == {
        "day_start_hour": 9,
        "day_end_hour": 17,
    }
    # Without a comma the clause runs to the end of the note and does reach a time, so this one is
    # withheld. Over-cautious rather than wrong — the fallback lane sees it — and deliberately NOT
    # chased by adding `and`/`but` to `_CLAUSE_END`: enumerating one more separator is the move
    # that produced four straight rounds of leaks in this guard.
    assert parse_preference("nothing crazy and 45 minute blocks from 9am", None) == {}


def test_a_trigger_word_is_never_blanked_away_inside_a_negation_gap() -> None:
    # Review F8's other half: the gap must not consume a bound that the note actually states.
    # The second bound in each of these is dropped — that is #192-F1 (distributed negation), a
    # known open follow-up — so assert only the bound that must survive, not the whole dict.
    assert parse_preference("nothing before 9am after 5pm", None)["day_start_hour"] == 9
    assert parse_preference("nothing until 10am after 6pm", None)["day_start_hour"] == 10


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
