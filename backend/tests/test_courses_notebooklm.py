"""Courses M4 — ``notebooklm`` materials cross-link to the sidecar catalog.

The course-detail endpoint joins each ``notebooklm`` material's ``notebook_id`` against the
sidecar catalog (read-only, best-effort) and merges a ``notebook`` ref the UI renders as a real
"Open notebook" card. These tests pin: the found join (title/topic_url/counts straight from the
sidecar), the not-found degrade, the no-id passthrough, that a missing/broken root never 500s
the course page, and the validator's non-string ``notebook_id`` warning.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import uid, write_notebook

SLUG = "nb-course"
NB_ID = uid("jlens")
UNKNOWN_ID = uid("ghost")


def _write_course(courses_dir: Path) -> None:
    """One lesson, three notebooklm materials: linked / unknown id / no id yet."""
    course_dir = courses_dir / SLUG
    course_dir.mkdir(parents=True)
    (course_dir / "course.json").write_text(
        json.dumps(
            {
                "title": "Notebook Course",
                "modules": [
                    {"id": "m1", "title": "M", "lessons": [
                        {"id": "l1", "title": "L", "materials": [
                            {"type": "notebooklm", "title": "Audio deep-dive",
                             "artifact": "audio", "notebook_id": NB_ID,
                             "note": "Six-episode season."},
                            {"type": "notebooklm", "title": "Moved elsewhere",
                             "notebook_id": UNKNOWN_ID, "note": "Not on this machine."},
                            {"type": "notebooklm", "title": "Not generated yet",
                             "note": "Optional enrichment — link a notebook later."},
                        ]},
                    ]},
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_sidecar(root: Path) -> None:
    write_notebook(
        root,
        "jlens-workspace",
        f"""---
notebook_id: {NB_ID}
alias: jlens-workspace
title: Jlens Workspace
template: learning-topic
tags: [learning]
---

# Jlens Workspace
**NotebookLM:** https://notebooklm.google.com/notebook/{NB_ID}

### Audio season
| Ep | Title | Format | Len | Status | Artifact ID |
|----|-------|--------|-----|--------|-------------|
| 1 | Ep 1 — Intro | deep_dive | default | done | {uid("jaud1")} |
| 2 | Ep 2 — Depth | deep_dive | long | done | {uid("jaud2")} |

### Study aids
| Ep | Topic | Study Guide ID | Quiz ID |
|----|-------|----------------|---------|
| 1 | intro | {uid("jguide")} | {uid("jquiz")} |
""",
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("COURSES_DIR", str(tmp_path / "hub" / "courses"))
    monkeypatch.setenv("NOTEBOOKLM_ROOT", str(tmp_path / "NotebookLMs"))
    _write_course(tmp_path / "hub" / "courses")
    _write_sidecar(tmp_path / "NotebookLMs")
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()


def _materials(client) -> list:
    r = client.get(f"/api/courses/{SLUG}")
    assert r.status_code == 200, r.text
    return r.json()["modules"][0]["lessons"][0]["materials"]


def test_linked_notebook_joins_title_link_and_counts(client):
    nb = _materials(client)[0]["notebook"]
    assert nb["found"] is True
    assert nb["notebook_id"] == NB_ID
    assert nb["title"] == "Jlens Workspace"
    assert nb["topic_url"] == f"/topics/{NB_ID}"
    assert nb["notebooklm_url"].endswith(NB_ID)
    assert nb["counts"]["audio"] == 2
    assert nb["counts"]["study_guides"] == 1
    assert nb["counts"]["quizzes"] == 1


def test_unknown_notebook_id_degrades_to_not_found(client):
    nb = _materials(client)[1]["notebook"]
    assert nb["found"] is False
    assert nb["notebook_id"] == UNKNOWN_ID
    assert nb["title"] is None


def test_material_without_id_gets_no_ref(client):
    assert _materials(client)[2]["notebook"] is None


def test_missing_sidecar_root_never_breaks_the_course_page(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("NOTEBOOKLM_ROOT", str(Path("/nonexistent") / "nowhere"))
    get_settings.cache_clear()
    try:
        mats = _materials(client)  # still 200
        assert mats[0]["notebook"]["found"] is False  # linked id can't resolve without the root
    finally:
        get_settings.cache_clear()


def test_other_course_surfaces_unaffected(client):
    # The join is detail-only; the list + next endpoints stay notebook-free and calm.
    assert client.get("/api/courses").status_code == 200
    assert client.get(f"/api/courses/{SLUG}/next").status_code == 200


# -- validator ------------------------------------------------------------------

def test_validate_warns_on_non_string_notebook_id(tmp_path):
    from app.courses import validate_dir

    course_dir = tmp_path / "bad-nb"
    course_dir.mkdir()
    (course_dir / "course.json").write_text(
        json.dumps(
            {
                "title": "Bad NB",
                "modules": [
                    {"id": "m1", "title": "M", "lessons": [
                        {"id": "l1", "title": "L", "materials": [
                            {"type": "notebooklm", "notebook_id": 123},
                        ]},
                    ]},
                ],
            }
        ),
        encoding="utf-8",
    )
    report = validate_dir(course_dir)
    assert report["ok"] is True  # a warning, not an error — the course still loads
    assert any("non-string notebook_id" in w for w in report["warnings"])


def test_validate_accepts_string_notebook_id(tmp_path):
    from app.courses import validate_dir

    course_dir = tmp_path / "good-nb"
    course_dir.mkdir()
    (course_dir / "course.json").write_text(
        json.dumps(
            {
                "title": "Good NB",
                "modules": [
                    {"id": "m1", "title": "M", "lessons": [
                        {"id": "l1", "title": "L", "materials": [
                            {"type": "notebooklm", "notebook_id": uid("fine"), "note": "n"},
                        ]},
                    ]},
                ],
            }
        ),
        encoding="utf-8",
    )
    report = validate_dir(course_dir)
    assert report["ok"] is True
    assert not any("notebook_id" in w for w in report["warnings"])
