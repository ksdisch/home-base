"""M5 export + the ``editable`` flag.

Export is read-only: it zips whatever dir serves the slug (user course or bundled example),
skips hidden files, and never touches disk. ``editable`` tells the UI where edits can land —
true only when a user copy exists under COURSES_DIR.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

EXAMPLE_SLUG = "learning-how-to-learn"


@pytest.fixture
def env(tmp_path, monkeypatch):
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


def _write_course(base: Path, slug: str, manifest: dict, files: dict | None = None) -> Path:
    cdir = base / slug
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "course.json").write_text(json.dumps(manifest), encoding="utf-8")
    for rel, content in (files or {}).items():
        p = cdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return cdir


def _user_course(d: Path) -> Path:
    manifest = {
        "title": "C",
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
    return _write_course(d, "c", manifest, {"lessons/m1l1.md": "body\n"})


# -- export --------------------------------------------------------------------


def test_export_round_trips_the_course_dir_and_skips_hidden_files(env):
    client, d = env
    cdir = _user_course(d)
    (cdir / ".DS_Store").write_text("junk", encoding="utf-8")
    (cdir / "lessons" / ".hidden").write_text("junk", encoding="utf-8")
    r = client.get("/api/courses/c/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert 'filename="c-course.zip"' in r.headers["content-disposition"]
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = sorted(zf.namelist())
    assert names == ["c/course.json", "c/lessons/m1l1.md"]
    assert zf.read("c/lessons/m1l1.md").decode("utf-8") == "body\n"
    inner = json.loads(zf.read("c/course.json").decode("utf-8"))
    assert inner["title"] == "C"


def test_export_bundled_example_works_read_only(env):
    client, _ = env
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}/export")
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert f"{EXAMPLE_SLUG}/course.json" in zf.namelist()


def test_export_unknown_course_is_404(env):
    client, _ = env
    assert client.get("/api/courses/nope/export").status_code == 404


# -- editable flag -------------------------------------------------------------


def test_editable_true_only_for_user_courses(env):
    client, d = env
    _user_course(d)
    by_slug = {c["slug"]: c for c in client.get("/api/courses").json()["courses"]}
    assert by_slug["c"]["editable"] is True
    assert by_slug[EXAMPLE_SLUG]["editable"] is False

    assert client.get("/api/courses/c").json()["editable"] is True
    assert client.get(f"/api/courses/{EXAMPLE_SLUG}").json()["editable"] is False


def test_editable_true_for_a_user_shadow_of_the_bundled_slug(env):
    client, d = env
    _write_course(d, EXAMPLE_SLUG, {"title": "Shadowed", "modules": []})
    course = client.get(f"/api/courses/{EXAMPLE_SLUG}").json()
    assert course["title"] == "Shadowed" and course["editable"] is True
