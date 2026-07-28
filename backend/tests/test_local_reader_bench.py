"""sweeps/local_reader_bench.py — the ids-only enforcement point for the D8 bake-off.

Loaded via importlib straight from sweeps/ (the test_render_brief.py pattern): the script
is stdlib-only and lives outside the backend package so the bench never needs the venv, but
the decoder IS the guarantee that crossing assumption 2 stays safe, so it gets tested with
the backend suite. No Ollama is ever contacted — every test injects a fake runner or calls
the pure functions directly.

The contract under test: whatever a local model emits, what survives decode() is a list of
valid, in-range, non-repeating ordinals — so no claim the model invented can reach a render
path. Plus the lockstep the script's docstring promises: its item id must equal the id the
backend derives, or every gold set in the suite silently grades the wrong items.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "sweeps" / "local_reader_bench.py"
_spec = importlib.util.spec_from_file_location("local_reader_bench", MODULE_PATH)
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


ROSTER = [{"slug": "ai", "title": "AI"}, {"slug": "chicago", "title": "Chicago"}]


def _topic(*headlines: str) -> str:
    return json.dumps(
        {
            "top_line": "A line.",
            "items": [
                {
                    "headline": h,
                    "attribution": "Somewhere, July 20, 2026",
                    "digest": f"Digest for {h}.",
                    "why_it_matters": "It matters.",
                    "sources": [{"title": "S", "url": "https://example.com/s"}],
                }
                for h in headlines
            ],
        }
    )


def _day(tmp_path, date="2026-07-20", files=None):
    day = tmp_path / "sweeps" / date
    day.mkdir(parents=True)
    for name, body in (files or {"ai": _topic("Model ships"), "chicago": _topic("Ward map")}).items():
        (day / f"{name}.json").write_text(body, encoding="utf-8")
    return day


# ------------------------------------------------------------------ id lockstep


def test_item_id_matches_the_backend_formula_exactly():
    """The bench re-derives ids instead of importing the backend (sweeps/ stays stdlib).
    If the two ever drift, gold sets keep loading and silently grade the wrong items —
    so pin them against each other."""
    from app.sweeps import _structured_topic

    date, slug = "2026-07-20", "ai"
    data = json.loads(_topic("Model ships", "Chips tighten"))
    backend_ids = [i["id"] for i in _structured_topic(slug, data, {}, date)["items"]]

    seen: set[str] = set()
    bench_ids = [
        bench.item_id(date, slug, i["headline"], seen) for i in data["items"]
    ]
    assert bench_ids == backend_ids


def test_duplicate_headlines_take_the_suffix_like_the_backend():
    """actions_queue.py can skip the -2 suffix because it only reads a brief's first item.
    This script reads every item, so a repeated headline must not collapse two rows onto
    one id — that would make a gold set unsatisfiable."""
    from app.sweeps import _structured_topic

    date, slug = "2026-07-20", "ai"
    data = json.loads(_topic("Same", "Same", "Same"))
    backend_ids = [i["id"] for i in _structured_topic(slug, data, {}, date)["items"]]

    seen: set[str] = set()
    bench_ids = [bench.item_id(date, slug, i["headline"], seen) for i in data["items"]]
    assert bench_ids == backend_ids
    assert len(set(bench_ids)) == 3
    assert bench_ids[1].endswith("-2") and bench_ids[2].endswith("-3")


# ------------------------------------------------------------------ corpus


def test_load_day_orders_roster_first_then_strangers(tmp_path):
    day = _day(
        tmp_path,
        files={"chicago": _topic("Ward map"), "ai": _topic("Model ships"), "zzz": _topic("Odd")},
    )
    got = bench.load_day(day, ROSTER)
    assert [c["slug"] for c in got] == ["ai", "chicago", "zzz"]
    assert [c["ordinal"] for c in got] == [1, 2, 3]


def test_load_day_skips_pipeline_artifacts_and_malformed_topics(tmp_path):
    """Dotted stems are pipeline output, never topics (the brief.chapters lesson from
    PR #154). A corrupt topic file degrades to 'grade what rendered', like the page."""
    day = _day(tmp_path, files={"ai": _topic("Model ships")})
    (day / "brief.chapters.json").write_text('{"items": []}', encoding="utf-8")
    (day / "chicago.json").write_text("{not json", encoding="utf-8")
    (day / "empty.json").write_text(json.dumps({"top_line": "x", "items": []}), encoding="utf-8")

    got = bench.load_day(day, ROSTER)
    assert [c["headline"] for c in got] == ["Model ships"]


def test_load_day_drops_items_with_no_headline(tmp_path):
    body = json.dumps({"top_line": "x", "items": [{"headline": "  "}, {"headline": "Real"}]})
    day = _day(tmp_path, files={"ai": body})
    assert [c["headline"] for c in bench.load_day(day, ROSTER)] == ["Real"]


def test_load_day_missing_dir_is_empty_not_an_error(tmp_path):
    assert bench.load_day(tmp_path / "nope" / "2026-01-01", ROSTER) == []


# ------------------------------------------------------------------ decode: the gate


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("[3,1,2]", [3, 1, 2]),
        ("  [2]  ", [2]),
        ("[]", []),
    ],
)
def test_decode_accepts_clean_arrays(raw, expected):
    got, defects = bench.decode(raw, 3)
    assert got == expected
    assert defects == []


def test_decode_rejects_out_of_range_at_both_ends():
    """0 and n+1 are the two off-by-one mistakes a model actually makes; both are
    invented ids and must never reach the caller."""
    got, defects = bench.decode("[0,1,4]", 3)
    assert got == [1]
    assert "out_of_range" in defects


def test_decode_drops_duplicates_keeping_first_position():
    got, defects = bench.decode("[2,1,2]", 3)
    assert got == [2, 1]
    assert "duplicate" in defects


def test_decode_rejects_booleans_not_just_non_numbers():
    """bool subclasses int in Python — True would otherwise sail through as ordinal 1,
    which is a fabricated selection wearing a valid costume."""
    got, defects = bench.decode("[true, 2]", 3)
    assert got == [2]
    assert "non_integer" in defects


def test_decode_rejects_strings_and_floats():
    got, defects = bench.decode('["1", 2.5, 3]', 3)
    assert got == [3]
    assert "non_integer" in defects


@pytest.mark.parametrize("raw", ["not json at all", "", "   ", "{}", '{"picks":[1]}', "[1,2"])
def test_decode_unparseable_yields_nothing(raw):
    got, defects = bench.decode(raw, 3)
    assert got == []
    assert defects == ["unparseable"]


def test_decode_recovers_prose_wrapped_array_but_flags_it():
    """Recovering the array still yields ids-only output, so nothing can be fabricated —
    but a model that cannot hold the output contract has failed the contract, and the
    report must be able to tell this apart from pure garbage."""
    got, defects = bench.decode("Sure! Here you go:\n[2,1]\nHope that helps.", 3)
    assert got == [2, 1]
    assert defects == ["prose_wrapped"]
    assert "prose_wrapped" in bench.HARD_DEFECTS


def test_decode_never_returns_an_ordinal_outside_the_day(tmp_path):
    """The property that makes ids-only safe, stated directly."""
    for raw in ["[9,9,9]", "[-1]", '[1,"2",3,3,7]', "[0]"]:
        got, _ = bench.decode(raw, 3)
        assert all(1 <= o <= 3 for o in got)
        assert len(got) == len(set(got))


# ------------------------------------------------------------------ grade


def _candidates(tmp_path):
    return bench.load_day(_day(tmp_path), ROSTER)


def test_grade_hard_fails_on_any_gate_defect(tmp_path):
    cands = _candidates(tmp_path)
    res = bench.grade({"id": "f", "date": "d", "request": "r"}, cands, [1], ["out_of_range"])
    assert res["hard_fail"] is True
    assert res["hard_defects"] == ["out_of_range"]


def test_grade_padded_refusal_is_a_hard_fail(tmp_path):
    """A model that never says 'nothing here' is a model that pads — the single most
    trust-corrosive failure for a reshape surface."""
    cands = _candidates(tmp_path)
    fx = {"id": "f", "date": "d", "request": "r", "expect_empty": True}
    res = bench.grade(fx, cands, [1], [])
    assert res["refusal_ok"] is False
    assert res["hard_fail"] is True


def test_grade_honest_refusal_passes(tmp_path):
    cands = _candidates(tmp_path)
    fx = {"id": "f", "date": "d", "request": "r", "expect_empty": True}
    res = bench.grade(fx, cands, [], [])
    assert res["refusal_ok"] is True
    assert res["hard_fail"] is False


def test_grade_recall_and_precision_against_gold(tmp_path):
    cands = _candidates(tmp_path)
    first, second = cands[0]["id"], cands[1]["id"]
    fx = {
        "id": "f",
        "date": "d",
        "request": "r",
        "must_include": [first, second],
        "must_exclude": [second],
    }
    res = bench.grade(fx, cands, [1], [])
    assert res["recall"] == 0.5
    assert res["precision"] == 1.0
    assert res["missed"] == [second]
    assert res["leaked"] == []


def test_grade_ordering_is_relative_not_absolute(tmp_path):
    """An unrelated item sitting between two expected ones is not an ordering error —
    only the relative sequence of the declared ids is scored."""
    day = _day(tmp_path, files={"ai": _topic("A", "B", "C")})
    cands = bench.load_day(day, ROSTER)
    a, b, c = (x["id"] for x in cands)
    fx = {"id": "f", "date": "d", "request": "r", "expect_order": [a, c]}
    assert bench.grade(fx, cands, [1, 2, 3], [])["order_ok"] is True
    assert bench.grade(fx, cands, [3, 2, 1], [])["order_ok"] is False


def test_grade_leaves_unscored_dimensions_as_none(tmp_path):
    cands = _candidates(tmp_path)
    res = bench.grade({"id": "f", "date": "d", "request": "r"}, cands, [1], [])
    assert res["recall"] is None and res["precision"] is None and res["order_ok"] is None


# ------------------------------------------------------------------ fixtures + prompt


def test_load_fixtures_rejects_a_typo_rather_than_grading_it(tmp_path):
    """A malformed gold set must be loud: silently treating it as 'no requirements'
    would turn a broken fixture into a free pass."""
    p = tmp_path / "fx.json"
    p.write_text(json.dumps([{"id": "a", "date": "2026-07-20"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        bench.load_fixtures(p)

    p.write_text(json.dumps([{"id": "a", "date": "d", "request": "r", "must_include": "x"}]), "utf-8")
    with pytest.raises(ValueError):
        bench.load_fixtures(p)


def test_shipped_example_fixture_file_is_valid():
    """The example is the thing Kyle copies; if it doesn't load, the workflow starts broken."""
    example = MODULE_PATH.parent / "fixtures" / "reshape_requests.example.json"
    loaded = bench.load_fixtures(example)
    assert len(loaded) >= 5
    assert any(fx.get("expect_empty") for fx in loaded), "keep an impossible-request fixture"


def test_prompt_carries_every_item_and_demands_bare_json(tmp_path):
    cands = _candidates(tmp_path)
    prompt = bench.build_prompt(cands, "just the Chicago stuff")
    for c in cands:
        assert f"[{c['ordinal']}]" in prompt
        assert c["headline"] in prompt
    assert "just the Chicago stuff" in prompt
    assert "JSON array" in prompt
    # The refusal affordance has to be in the prompt or expect_empty fixtures are unfair.
    assert "[]" in prompt


def test_prompt_never_leaks_item_ids_to_the_model(tmp_path):
    """The model is shown ordinals only. If ids reached the prompt it could echo one back
    and we'd be grading hex transcription instead of selection."""
    cands = _candidates(tmp_path)
    prompt = bench.build_prompt(cands, "anything")
    for c in cands:
        assert c["id"] not in prompt


# ------------------------------------------------------------------ end to end


def test_run_fixture_with_a_fake_runner_grades_without_a_model(tmp_path):
    _day(tmp_path)
    roster_file = tmp_path / "topics.json"
    roster_file.write_text(json.dumps(ROSTER), encoding="utf-8")
    roster = bench.load_roster(roster_file)
    cands = bench.load_day(tmp_path / "sweeps" / "2026-07-20", roster)

    fx = {
        "id": "chicago",
        "date": "2026-07-20",
        "request": "just the Chicago stuff",
        "must_include": [cands[1]["id"]],
        "must_exclude": [cands[0]["id"]],
    }
    res = bench.run_fixture(fx, tmp_path / "sweeps", roster, lambda _p: "[2]")
    assert res["hard_fail"] is False
    assert res["recall"] == 1.0 and res["precision"] == 1.0


def test_run_fixture_survives_a_dead_runner(tmp_path):
    """Ollama being down must produce a graded FAIL row, not a traceback that loses the
    whole run — the audio_brief.py best-effort lesson."""
    _day(tmp_path)
    roster_file = tmp_path / "topics.json"
    roster_file.write_text(json.dumps(ROSTER), encoding="utf-8")

    def boom(_prompt):
        raise OSError("connection refused")

    fx = {"id": "f", "date": "2026-07-20", "request": "r"}
    res = bench.run_fixture(fx, tmp_path / "sweeps", bench.load_roster(roster_file), boom)
    assert res["hard_fail"] is True
    assert res["defects"] == ["unparseable"]


def test_run_fixture_reports_a_missing_day_instead_of_scoring_it(tmp_path):
    fx = {"id": "f", "date": "2026-01-01", "request": "r"}
    res = bench.run_fixture(fx, tmp_path / "sweeps", [], lambda _p: "[1]")
    assert res["hard_fail"] is True
    assert res["defects"] == ["no_corpus"]


def test_report_states_the_verdict_and_marks_hard_failures(tmp_path):
    cands = _candidates(tmp_path)
    passing = bench.grade({"id": "ok", "date": "d", "request": "r"}, cands, [1], [])
    failing = bench.grade({"id": "bad", "date": "d", "request": "r"}, cands, [1], ["duplicate"])

    assert "PASS (hard gates clean)" in bench.render_report("m", [passing], "2026-07-27")
    report = bench.render_report("m", [passing, failing], "2026-07-27")
    assert "FAIL (1 hard)" in report
    assert "**duplicate**" in report
    assert "7 consecutive daily runs" in report
