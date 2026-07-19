"""M5 structural edits — objectives + reorder over the transactional writer.

House rules under test: edits land only on user courses (bundled examples 409), a reorder is a
strict bijection with ids pinned first (so ``course_lesson_progress`` survives every move —
including on a manifest that relied on positional fallback ids), and a course that fails
validation bounces with ``ok=False`` and its files byte-identical.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EXAMPLE_SLUG = "learning-how-to-learn"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Fresh SQLite store + a writable COURSES_DIR, so edits have a user course to land on."""
    d = tmp_path / "courses"
    d.mkdir()
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("COURSES_DIR", str(d))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    try:
        yield client, d
    finally:
        get_settings.cache_clear()


def _write_course(base: Path, slug: str, manifest: dict) -> Path:
    cdir = base / slug
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "course.json").write_text(json.dumps(manifest), encoding="utf-8")
    return cdir


def _two_module_course(base: Path, with_ids: bool = True) -> Path:
    """2 modules × 2 lessons. With ``with_ids=False`` the loader derives the SAME ids
    positionally (m1, m1l1, …), so both variants share assertions."""

    def lesson(mid: str, i: int, title: str) -> dict:
        d = {"title": title, "objectives": [f"Explain {title}"]}
        if with_ids:
            d["id"] = f"{mid}l{i}"
        return d

    modules = []
    for mi, (mname, titles) in enumerate([("Alpha", ["A1", "A2"]), ("Beta", ["B1", "B2"])], 1):
        m = {
            "title": mname,
            "lessons": [lesson(f"m{mi}", i, t) for i, t in enumerate(titles, 1)],
        }
        if with_ids:
            m["id"] = f"m{mi}"
        modules.append(m)
    return _write_course(base, "c", {"title": "C", "modules": modules})


# -- objectives ----------------------------------------------------------------


def test_edit_objectives_lands_and_drops_blanks(env):
    client, d = env
    _two_module_course(d)
    r = client.put(
        "/api/courses/c/lessons/m1l2/objectives",
        json={"objectives": ["  Apply X  ", "", "Compare Y", "   "]},
    )
    assert r.status_code == 200 and r.json()["ok"] is True
    course = client.get("/api/courses/c").json()
    assert course["modules"][0]["lessons"][1]["objectives"] == ["Apply X", "Compare Y"]


def test_edit_objectives_404s_for_unknown_course_or_lesson(env):
    client, d = env
    _two_module_course(d)
    r = client.put("/api/courses/nope/lessons/x/objectives", json={"objectives": []})
    assert r.status_code == 404
    r = client.put("/api/courses/c/lessons/ghost/objectives", json={"objectives": []})
    assert r.status_code == 404


def test_edit_objectives_bundled_example_is_409_read_only(env):
    client, _ = env
    r = client.put(
        f"/api/courses/{EXAMPLE_SLUG}/lessons/m1l1/objectives",
        json={"objectives": ["Explain the loop"]},
    )
    assert r.status_code == 409


def test_edit_on_a_course_with_a_preexisting_error_rolls_back(env):
    client, d = env
    cdir = _two_module_course(d)
    # Declare a material file that doesn't exist -> validate_dir errors -> edits must bounce.
    raw = json.loads((cdir / "course.json").read_text(encoding="utf-8"))
    raw["modules"][0]["lessons"][0]["materials"] = [
        {"type": "lesson", "title": "Ghost", "path": "lessons/ghost.md"}
    ]
    (cdir / "course.json").write_text(json.dumps(raw), encoding="utf-8")
    before = (cdir / "course.json").read_bytes()
    r = client.put("/api/courses/c/lessons/m1l1/objectives", json={"objectives": ["Apply X"]})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert any("ghost" in e for e in body["errors"])
    assert (cdir / "course.json").read_bytes() == before


# -- reorder -------------------------------------------------------------------


def _reorder(client, modules):
    return client.put("/api/courses/c/order", json={"modules": modules})


def test_reorder_preserves_completion_across_moves(env):
    client, d = env
    _two_module_course(d)
    r = client.post("/api/courses/c/lessons/m2l2/complete", json={"completed": True})
    assert r.status_code == 200
    r = _reorder(
        client,
        [
            {"id": "m2", "lessons": ["m2l2", "m2l1"]},
            {"id": "m1", "lessons": ["m1l1", "m1l2"]},
        ],
    )
    assert r.status_code == 200 and r.json()["ok"] is True
    course = client.get("/api/courses/c").json()
    assert [m["id"] for m in course["modules"]] == ["m2", "m1"]
    first = course["modules"][0]["lessons"][0]
    assert first["id"] == "m2l2" and first["completed"] is True
    assert course["progress_pct"] == 25  # still 1 of 4 — nothing re-keyed


def test_reorder_pins_fallback_ids_so_progress_survives(env):
    client, d = env
    cdir = _two_module_course(d, with_ids=False)  # ids exist only positionally today
    r = client.post("/api/courses/c/lessons/m1l2/complete", json={"completed": True})
    assert r.status_code == 200
    r = _reorder(
        client,
        [
            {"id": "m1", "lessons": ["m1l2", "m1l1"]},
            {"id": "m2", "lessons": ["m2l1", "m2l2"]},
        ],
    )
    assert r.status_code == 200 and r.json()["ok"] is True
    course = client.get("/api/courses/c").json()
    moved = course["modules"][0]["lessons"][0]
    # The lesson kept its id (and therefore its completion) while changing position.
    assert moved["id"] == "m1l2" and moved["title"] == "A2" and moved["completed"] is True
    raw = json.loads((cdir / "course.json").read_text(encoding="utf-8"))
    assert raw["modules"][0]["lessons"][0]["id"] == "m1l2"  # pinned explicitly on disk now


def test_reorder_rejects_non_bijections_with_nothing_written(env):
    client, d = env
    _two_module_course(d)
    before = (d / "c" / "course.json").read_bytes()
    bad_payloads = [
        # missing module m2
        [{"id": "m1", "lessons": ["m1l1", "m1l2"]}],
        # dropped lesson m1l2
        [
            {"id": "m1", "lessons": ["m1l1"]},
            {"id": "m2", "lessons": ["m2l1", "m2l2"]},
        ],
        # cross-module move (m2l1 offered to m1)
        [
            {"id": "m1", "lessons": ["m1l1", "m1l2", "m2l1"]},
            {"id": "m2", "lessons": ["m2l2"]},
        ],
        # duplicate module id
        [
            {"id": "m1", "lessons": ["m1l1", "m1l2"]},
            {"id": "m1", "lessons": ["m1l1", "m1l2"]},
        ],
        # unknown module id
        [
            {"id": "ghost", "lessons": []},
            {"id": "m2", "lessons": ["m2l1", "m2l2"]},
        ],
    ]
    for payload in bad_payloads:
        assert _reorder(client, payload).status_code == 422, payload
    assert (d / "c" / "course.json").read_bytes() == before


def test_reorder_bundled_is_409(env):
    client, _ = env
    r = client.put(f"/api/courses/{EXAMPLE_SLUG}/order", json={"modules": []})
    assert r.status_code == 409
