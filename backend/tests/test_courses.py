"""Phase-6 course manifest loader + CLI bridge.

Courses are read-only sidecars on disk. These tests cover: the bundled example is well-formed,
discovery is the union of examples + COURSES_DIR (user wins), malformed dirs are skipped (not
fatal), material reads are path-confined, and the CLI bridge scaffolds + validates.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.courses import (
    CourseError,
    get_course,
    list_courses,
    load_manifest,
    read_material,
    validate_dir,
)
from app.courses.manifest import EXAMPLES_DIR

EXAMPLE_SLUG = "learning-how-to-learn"


@pytest.fixture
def courses_dir(tmp_path, monkeypatch) -> Path:
    """Point COURSES_DIR at a throwaway dir and reset the settings cache around the test."""
    d = tmp_path / "courses"
    d.mkdir()
    monkeypatch.setenv("COURSES_DIR", str(d))
    from app.config import get_settings

    get_settings.cache_clear()
    yield d
    get_settings.cache_clear()


def _write_course(base: Path, slug: str, manifest: dict, files: dict | None = None) -> Path:
    cdir = base / slug
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "course.json").write_text(json.dumps(manifest), encoding="utf-8")
    for rel, content in (files or {}).items():
        p = cdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return cdir


# -- the bundled example -------------------------------------------------------

def test_bundled_example_dir_exists():
    assert (EXAMPLES_DIR / EXAMPLE_SLUG / "course.json").is_file()


def test_bundled_example_validates_clean():
    report = validate_dir(EXAMPLES_DIR / EXAMPLE_SLUG)
    assert report["ok"], report["errors"]
    assert report["errors"] == []
    assert report["module_count"] == 2
    assert report["lesson_count"] == 4


def test_bundled_example_quiz_matches_hub_shape():
    # The course quiz must use the hub's quiz JSON shape so the existing grader can consume it.
    mat = read_material(EXAMPLE_SLUG, "quizzes/m2l2.json")
    quiz = mat["data"]
    assert "questions" in quiz and len(quiz["questions"]) == 5
    q0 = quiz["questions"][0]
    assert "answerOptions" in q0
    assert sum(1 for o in q0["answerOptions"] if o["isCorrect"]) == 1


def test_list_includes_bundled_example_even_with_empty_user_dir(courses_dir):
    slugs = [c["slug"] for c in list_courses()]
    assert EXAMPLE_SLUG in slugs


# -- discovery + robustness ----------------------------------------------------

def test_user_course_is_discovered(courses_dir):
    _write_course(courses_dir, "my-course", {"title": "Mine", "modules": []})
    slugs = [c["slug"] for c in list_courses()]
    assert "my-course" in slugs and EXAMPLE_SLUG in slugs


def test_malformed_dir_is_skipped_not_fatal(courses_dir):
    (courses_dir / "broken").mkdir()
    (courses_dir / "broken" / "course.json").write_text("{ not json", encoding="utf-8")
    _write_course(courses_dir, "good", {"title": "Good", "modules": []})
    slugs = [c["slug"] for c in list_courses()]
    assert "good" in slugs
    assert "broken" not in slugs  # skipped


def test_user_dir_overrides_example_slug(courses_dir):
    _write_course(courses_dir, EXAMPLE_SLUG, {"title": "Shadowed", "modules": []})
    course = get_course(EXAMPLE_SLUG)
    assert course["title"] == "Shadowed"  # user dir wins on slug collision


def test_load_manifest_requires_title(tmp_path):
    cdir = _write_course(tmp_path, "x", {"modules": []})
    with pytest.raises(CourseError):
        load_manifest(cdir)


def test_load_manifest_rejects_duplicate_lesson_ids(tmp_path):
    cdir = _write_course(
        tmp_path,
        "dup",
        {
            "title": "Dup",
            "modules": [
                {"id": "m1", "title": "M", "lessons": [
                    {"id": "l1", "title": "A"}, {"id": "l1", "title": "B"},
                ]},
            ],
        },
    )
    with pytest.raises(CourseError):
        load_manifest(cdir)


def _course_with_quiz(base: Path, quiz_obj: dict) -> Path:
    return _write_course(
        base,
        "q",
        {
            "title": "Q",
            "modules": [
                {"id": "m1", "title": "M", "lessons": [
                    {"id": "l1", "title": "L", "objectives": ["o"], "materials": [
                        {"type": "quiz", "path": "quizzes/l1.json"},
                    ]},
                ]},
            ],
        },
        {"quizzes/l1.json": json.dumps(quiz_obj)},
    )


def _ok_quiz() -> dict:
    return {"title": "t", "questions": [
        {"question": "q?", "answerOptions": [
            {"text": "a", "isCorrect": True, "rationale": "r"},
            {"text": "b", "isCorrect": False, "rationale": "r"},
        ], "hint": "h"},
    ]}


def test_validate_passes_well_formed_quiz(tmp_path):
    report = validate_dir(_course_with_quiz(tmp_path, _ok_quiz()))
    assert report["ok"], report["errors"]


def test_validate_rejects_two_correct_options(tmp_path):
    q = _ok_quiz()
    q["questions"][0]["answerOptions"][1]["isCorrect"] = True  # now 2 correct
    report = validate_dir(_course_with_quiz(tmp_path, q))
    assert not report["ok"]
    assert any("exactly one option" in e for e in report["errors"])


def test_validate_rejects_zero_correct_options(tmp_path):
    q = _ok_quiz()
    q["questions"][0]["answerOptions"][0]["isCorrect"] = False  # now 0 correct
    report = validate_dir(_course_with_quiz(tmp_path, q))
    assert not report["ok"]
    assert any("exactly one option" in e for e in report["errors"])


def test_validate_rejects_option_missing_rationale(tmp_path):
    q = _ok_quiz()
    del q["questions"][0]["answerOptions"][1]["rationale"]
    report = validate_dir(_course_with_quiz(tmp_path, q))
    assert not report["ok"]
    assert any("rationale" in e for e in report["errors"])


def test_validate_rejects_malformed_flashcards(tmp_path):
    cdir = _write_course(
        tmp_path, "fc",
        {"title": "FC", "modules": [
            {"id": "m1", "title": "M", "lessons": [
                {"id": "l1", "title": "L", "objectives": ["o"], "materials": [
                    {"type": "flashcards", "path": "flashcards/l1.json"},
                ]},
            ]},
        ]},
        {"flashcards/l1.json": json.dumps([{"front": "f"}])},  # missing back
    )
    report = validate_dir(cdir)
    assert not report["ok"]
    assert any("front" in e and "back" in e for e in report["errors"])


def test_validate_warns_on_count_mismatch(tmp_path):
    cdir = _write_course(
        tmp_path, "cm",
        {"title": "CM", "modules": [
            {"id": "m1", "title": "M", "lessons": [
                {"id": "l1", "title": "L", "objectives": ["o"], "materials": [
                    {"type": "flashcards", "path": "flashcards/l1.json", "count": 9},
                ]},
            ]},
        ]},
        {"flashcards/l1.json": json.dumps([{"front": "f", "back": "b"}])},
    )
    report = validate_dir(cdir)
    assert report["ok"]  # count mismatch is advisory, not blocking
    assert any("count" in w for w in report["warnings"])


def test_exercise_is_a_file_backed_material(tmp_path):
    cdir = _write_course(
        tmp_path, "ex",
        {"title": "EX", "modules": [
            {"id": "m1", "title": "M", "lessons": [
                {"id": "l1", "title": "L", "objectives": ["o"], "materials": [
                    {"type": "exercise", "path": "exercises/l1.md"},
                ]},
            ]},
        ]},
        {"exercises/l1.md": "## Problem\nx\n## Solution\ny\n"},
    )
    assert validate_dir(cdir)["ok"]


def test_validate_rejects_duplicate_module_id(tmp_path):
    cdir = _write_course(tmp_path, "dm", {"title": "DM", "modules": [
        {"id": "m1", "title": "A", "lessons": []},
        {"id": "m1", "title": "B", "lessons": []},
    ]})
    report = validate_dir(cdir)
    assert not report["ok"]
    assert any("duplicate module id" in e for e in report["errors"])


def test_validate_rejects_non_list_lessons(tmp_path):
    cdir = _write_course(tmp_path, "nl", {"title": "NL", "modules": [
        {"id": "m1", "title": "M", "lessons": 5},
    ]})
    report = validate_dir(cdir)  # must not raise an uncaught TypeError
    assert not report["ok"]
    assert any("lessons must be a list" in e for e in report["errors"])


def test_validate_warns_on_unknown_material_type(tmp_path):
    cdir = _write_course(tmp_path, "ut", {"title": "UT", "modules": [
        {"id": "m1", "title": "M", "lessons": [
            {"id": "l1", "title": "L", "objectives": ["o"], "materials": [
                {"type": "lessons", "path": "lessons/l1.md"},  # typo'd type
            ]},
        ]},
    ]})
    report = validate_dir(cdir)
    assert report["ok"]  # advisory
    assert any("unknown material type" in w for w in report["warnings"])


def test_validate_warns_on_invalid_level(tmp_path):
    cdir = _write_course(tmp_path, "lv", {"title": "LV", "level": "expert", "modules": []})
    report = validate_dir(cdir)
    assert any("level 'expert'" in w for w in report["warnings"])


def test_cli_write_validates_and_forces_slug(courses_dir, capsys):
    from app.courses import cli

    manifest = {
        "slug": "WRONG", "title": "Written", "modules": [
            {"id": "m1", "title": "M", "lessons": [
                {"id": "l1", "title": "L", "objectives": ["Describe X"], "materials": []},
            ]},
        ],
    }
    mf = courses_dir / "m.json"
    mf.write_text(json.dumps(manifest), encoding="utf-8")
    rc = cli.main(["write", "--slug", "written-course", "--from-file", str(mf)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["slug"] == "written-course"  # forced to the dir slug, not "WRONG"
    assert (courses_dir / "written-course" / "course.json").is_file()


def test_cli_scaffold_rejects_uppercase_slug(courses_dir, capsys):
    from app.courses import cli

    assert cli.main(["scaffold", "--slug", "Bad_Slug", "--title", "X"]) == 2
    assert json.loads(capsys.readouterr().err)["kind"] == "ValueError"


def test_validate_reports_missing_material_file(tmp_path):
    cdir = _write_course(
        tmp_path,
        "missing",
        {
            "title": "Missing",
            "modules": [
                {"id": "m1", "title": "M", "lessons": [
                    {"id": "l1", "title": "L", "objectives": ["o"], "materials": [
                        {"type": "lesson", "path": "lessons/l1.md"},
                    ]},
                ]},
            ],
        },
    )
    report = validate_dir(cdir)
    assert not report["ok"]
    assert any("missing material file" in e for e in report["errors"])


# -- material reads ------------------------------------------------------------

def test_read_material_text_and_json():
    text = read_material(EXAMPLE_SLUG, "lessons/m1l1.md")
    assert text["kind"] == "text" and "forgetting" in text["text"].lower()
    cards = read_material(EXAMPLE_SLUG, "flashcards/m1l2.json")
    assert cards["kind"] == "json" and isinstance(cards["data"], list)


def test_read_material_rejects_traversal():
    with pytest.raises(CourseError):
        read_material(EXAMPLE_SLUG, "../../config.py")


def test_read_material_missing_file_raises():
    with pytest.raises(CourseError):
        read_material(EXAMPLE_SLUG, "lessons/nope.md")


# -- CLI bridge ----------------------------------------------------------------

def test_cli_scaffold_then_validate(courses_dir, capsys):
    from app.courses import cli

    rc = cli.main(["scaffold", "--slug", "test-course", "--title", "Test Course"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["slug"] == "test-course"
    assert (courses_dir / "test-course" / "course.json").is_file()
    for sub in ("lessons", "diagrams", "flashcards", "quizzes"):
        assert (courses_dir / "test-course" / sub).is_dir()

    rc = cli.main(["validate", "--path", str(courses_dir / "test-course")])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True


def test_cli_scaffold_rejects_bad_slug(courses_dir, capsys):
    from app.courses import cli

    rc = cli.main(["scaffold", "--slug", "../escape", "--title", "X"])
    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["kind"] == "ValueError"


def test_cli_list_speaks_json(courses_dir, capsys):
    from app.courses import cli

    assert cli.main(["list"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert any(c["slug"] == EXAMPLE_SLUG for c in data)
