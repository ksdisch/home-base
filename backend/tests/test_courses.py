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
