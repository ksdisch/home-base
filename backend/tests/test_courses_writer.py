"""M5 writer library — the ONE write path over user course dirs.

House rules under test: writes land only under COURSES_DIR (bundled-only slugs and escaping
paths are refused); every write is transactional (a validation failure restores the prior
manifest/material byte-identical — a failed write never leaves a course worse than it was);
and ``pin_ids`` materializes exactly the ids the loader would derive, so a later reorder can
never silently re-key ``course_lesson_progress`` rows.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.courses import CourseError, load_manifest
from app.courses.writer import (
    edit_manifest,
    pin_ids,
    user_course_dir,
    write_manifest,
    write_material,
)

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


def _deck(n: int) -> str:
    return json.dumps([{"front": f"Q{i}", "back": f"A{i}"} for i in range(n)])


def _course_with_deck(courses_dir: Path, count_field: int = 2, cards: int = 2) -> Path:
    manifest = {
        "title": "T",
        "modules": [
            {
                "id": "m1",
                "title": "M",
                "lessons": [
                    {
                        "id": "m1l1",
                        "title": "L",
                        "objectives": ["Explain x"],
                        "materials": [
                            {
                                "type": "flashcards",
                                "title": "Deck",
                                "path": "flashcards/m1l1.json",
                                "count": count_field,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    return _write_course(courses_dir, "c", manifest, {"flashcards/m1l1.json": _deck(cards)})


# -- write_manifest ------------------------------------------------------------


def test_write_manifest_writes_validates_and_forces_slug(courses_dir):
    report = write_manifest("fresh", {"title": "Fresh", "slug": "wrong", "modules": []})
    assert report["ok"] is True and report["rolled_back"] is False
    on_disk = json.loads((courses_dir / "fresh" / "course.json").read_text(encoding="utf-8"))
    assert on_disk["slug"] == "fresh"


def test_write_manifest_restores_prior_manifest_byte_identical_on_failure(courses_dir):
    _write_course(courses_dir, "c", {"title": "Good", "modules": []})
    before = (courses_dir / "c" / "course.json").read_bytes()
    report = write_manifest("c", {"modules": []})  # no title -> the manifest can't load
    assert report["ok"] is False and report["rolled_back"] is True
    assert (courses_dir / "c" / "course.json").read_bytes() == before


def test_write_manifest_failed_first_write_leaves_no_manifest(courses_dir):
    report = write_manifest("new", {"modules": []})
    assert report["rolled_back"] is True
    assert not (courses_dir / "new" / "course.json").exists()


def test_write_manifest_rejects_a_slug_escaping_courses_dir(courses_dir):
    with pytest.raises(CourseError):
        write_manifest("..", {"title": "X", "modules": []})


# -- user_course_dir (the editable guard) --------------------------------------


def test_user_course_dir_only_for_existing_user_copies(courses_dir):
    assert user_course_dir("nope") is None
    assert user_course_dir(EXAMPLE_SLUG) is None  # bundled-only: read-only
    _write_course(courses_dir, "mine", {"title": "Mine", "modules": []})
    assert user_course_dir("mine") == courses_dir / "mine"


def test_user_course_dir_rejects_escapes(courses_dir):
    # A course.json planted just OUTSIDE courses_dir must not be reachable via '..'.
    (courses_dir.parent / "course.json").write_text("{}", encoding="utf-8")
    assert user_course_dir("..") is None


# -- edit_manifest -------------------------------------------------------------


def test_edit_manifest_refuses_bundled_only_slug(courses_dir):
    with pytest.raises(CourseError):
        edit_manifest(EXAMPLE_SLUG, lambda raw: None)


def test_edit_manifest_round_trip_preserves_fields_the_loader_ignores(courses_dir):
    manifest = {
        "title": "T",
        "authoring_notes": "keep me",
        "modules": [{"id": "m1", "title": "M", "custom": {"a": 1}, "lessons": []}],
    }
    _write_course(courses_dir, "c", manifest)

    def bump(raw):
        raw["modules"][0]["title"] = "M2"

    report = edit_manifest("c", bump)
    assert report["ok"] is True
    on_disk = json.loads((courses_dir / "c" / "course.json").read_text(encoding="utf-8"))
    assert on_disk["authoring_notes"] == "keep me"
    assert on_disk["modules"][0]["custom"] == {"a": 1}
    assert on_disk["modules"][0]["title"] == "M2"


def test_edit_manifest_error_in_mutate_touches_nothing(courses_dir):
    _write_course(courses_dir, "c", {"title": "T", "modules": []})
    before = (courses_dir / "c" / "course.json").read_bytes()

    def boom(raw):
        raise CourseError("nope")

    with pytest.raises(CourseError):
        edit_manifest("c", boom)
    assert (courses_dir / "c" / "course.json").read_bytes() == before


# -- write_material ------------------------------------------------------------


def test_write_material_replaces_content_and_syncs_declared_count(courses_dir):
    _course_with_deck(courses_dir, count_field=2, cards=2)
    report = write_material("c", "flashcards/m1l1.json", _deck(3) + "\n", count=3)
    assert report["ok"] is True and report["rolled_back"] is False
    data = json.loads(
        (courses_dir / "c" / "flashcards" / "m1l1.json").read_text(encoding="utf-8")
    )
    assert len(data) == 3
    manifest = json.loads((courses_dir / "c" / "course.json").read_text(encoding="utf-8"))
    assert manifest["modules"][0]["lessons"][0]["materials"][0]["count"] == 3


def test_write_material_rolls_back_file_and_manifest_on_invalid_content(courses_dir):
    cdir = _course_with_deck(courses_dir, count_field=2, cards=2)
    file_before = (cdir / "flashcards" / "m1l1.json").read_bytes()
    manifest_before = (cdir / "course.json").read_bytes()
    report = write_material("c", "flashcards/m1l1.json", "[]", count=0)  # empty deck: invalid
    assert report["ok"] is False and report["rolled_back"] is True
    assert (cdir / "flashcards" / "m1l1.json").read_bytes() == file_before
    assert (cdir / "course.json").read_bytes() == manifest_before


def test_write_material_leaves_count_free_entries_alone(courses_dir):
    manifest = {
        "title": "T",
        "modules": [
            {
                "id": "m1",
                "title": "M",
                "lessons": [
                    {
                        "id": "m1l1",
                        "title": "L",
                        "objectives": ["Explain x"],
                        "materials": [
                            {"type": "lesson", "title": "Body", "path": "lessons/m1l1.md"}
                        ],
                    }
                ],
            }
        ],
    }
    _write_course(courses_dir, "c", manifest, {"lessons/m1l1.md": "old body\n"})
    report = write_material("c", "lessons/m1l1.md", "new body\n")
    assert report["ok"] is True
    on_disk = json.loads((courses_dir / "c" / "course.json").read_text(encoding="utf-8"))
    assert "count" not in on_disk["modules"][0]["lessons"][0]["materials"][0]
    text = (courses_dir / "c" / "lessons" / "m1l1.md").read_text(encoding="utf-8")
    assert text == "new body\n"


def test_write_material_refuses_traversal_missing_files_and_bundled(courses_dir):
    _course_with_deck(courses_dir)
    with pytest.raises(CourseError):
        write_material("c", "../evil.md", "x")
    with pytest.raises(CourseError):
        write_material("c", "lessons/ghost.md", "x")  # can't create, only replace
    with pytest.raises(CourseError):
        write_material(EXAMPLE_SLUG, "lessons/m1l1.md", "x")


# -- pin_ids -------------------------------------------------------------------


def test_pin_ids_materializes_exactly_the_loaders_fallback_ids(courses_dir):
    manifest = {
        "title": "T",
        "modules": [
            {"title": "A", "lessons": [{"title": "a1"}, {"id": "keep", "title": "a2"}]},
            {"id": "custom", "title": "B", "lessons": [{"title": "b1"}]},
        ],
    }
    cdir = _write_course(courses_dir, "c", manifest)
    effective = load_manifest(cdir)  # what progress rows key on today
    raw = json.loads((cdir / "course.json").read_text(encoding="utf-8"))
    pin_ids(raw)
    pinned = [(m["id"], [lsn["id"] for lsn in m.get("lessons", [])]) for m in raw["modules"]]
    loaded = [(m["id"], [lsn["id"] for lsn in m["lessons"]]) for m in effective["modules"]]
    assert pinned == loaded
    assert pinned == [("m1", ["m1l1", "keep"]), ("custom", ["customl1"])]
