"""GET /api/topics/{nb}/study-guides/{art} — the in-hub study-guide reader contract.

Success resolves the sidecar artifact's title + the NotebookLM link alongside the downloaded
markdown; every failure mode (auth lapse, download error, empty file, unknown notebook) degrades
to the same calm shape the quiz player uses — never a 500. Sidecars are synthetic (built in a
tmp root via `write_notebook`); `nlm` is a fake runner that, like the real ≥0.5 CLI, writes the
artifact to the injected `-o` path.
"""

from __future__ import annotations

from pathlib import Path

from .conftest import uid, write_notebook

NB = uid("guidenb")
GUIDE = uid("guideart")
QUIZ = uid("quizart")
GUIDE_TITLE = "Ep 1 — Study Guide"
MARKDOWN = "# Photosynthesis\n\nChlorophyll absorbs light; ATP and NADPH come out.\n"

README = f"""---
notebook_id: {NB}
alias: guide-topic
title: Guide Topic
template: learning-topic
tags: [learning]
---

# Guide Topic
**NotebookLM:** https://notebooklm.google.com/notebook/{NB}
"""

ARTIFACT_MAP = f"""{{
  "notebook_id": "{NB}",
  "quizzes": {{ "1": {{"id": "{QUIZ}", "title": "Ep 1 — Quiz"}} }},
  "study_guides": {{ "1": {{"id": "{GUIDE}", "title": "{GUIDE_TITLE}"}} }}
}}"""


# -- fake runners ------------------------------------------------------------------


def _runner_writing(markdown: str):
    """A fake `nlm` ≥0.5: writes the guide to the `-o` path; stdout is only a ✓ line."""

    def run(args):
        from app.nlm import NlmResult

        out = Path(args[args.index("-o") + 1])
        out.write_text(markdown, encoding="utf-8")
        return NlmResult(args=list(args), stdout=f"✓ Downloaded report to: {out}\n",
                         stderr="", returncode=0)

    return run


def _runner_not_logged_in(args):
    from app.nlm import NlmResult

    return NlmResult(args=list(args), stdout="", stderr="Error: not logged in", returncode=1)


def _runner_boom(args):
    from app.nlm import NlmResult

    return NlmResult(args=list(args), stdout="", stderr="boom", returncode=2)


# -- harness -----------------------------------------------------------------------


def _make_client(tmp_path, runner):
    """TestClient over a one-notebook synthetic sidecar root + an injected nlm runner."""
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.deps import get_app_settings, get_nlm_client
    from app.main import app
    from app.nlm import NlmClient

    root = tmp_path / "NotebookLMs"
    root.mkdir(exist_ok=True)
    write_notebook(root, "guide-topic", README, artifact_map=ARTIFACT_MAP)

    settings = Settings()
    settings.notebooklm_root = root
    settings.ensure_dirs()

    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_nlm_client] = lambda: NlmClient(runner=runner)
    return TestClient(app)


# -- the contract ------------------------------------------------------------------


def test_success_resolves_sidecar_title_link_and_markdown(tmp_path):
    client = _make_client(tmp_path, _runner_writing(MARKDOWN))
    try:
        r = client.get(f"/api/topics/{NB}/study-guides/{GUIDE}")
        assert r.status_code == 200
        body = r.json()
        # Field names are the hand-synced frontend contract — pin them exactly.
        assert set(body) == {
            "notebook_id", "artifact_id", "ok", "auth",
            "title", "notebooklm_url", "markdown", "error",
        }
        assert body["ok"] is True
        assert body["notebook_id"] == NB and body["artifact_id"] == GUIDE
        assert body["markdown"] == MARKDOWN
        assert body["title"] == GUIDE_TITLE  # from the sidecar artifact, not the doc's H1
        assert body["notebooklm_url"] == f"https://notebooklm.google.com/notebook/{NB}"
        assert body["auth"] == {"ok": True, "message": None}
        assert body["error"] is None
    finally:
        client.app.dependency_overrides.clear()


def test_unknown_artifact_still_downloads_just_without_a_title(tmp_path):
    # Downloadability is proven by the fetch itself (like quiz prepare); an id the sidecar
    # doesn't know simply gets no title.
    client = _make_client(tmp_path, _runner_writing(MARKDOWN))
    try:
        body = client.get(f"/api/topics/{NB}/study-guides/{uid('ghost')}").json()
        assert body["ok"] is True
        assert body["title"] is None
        assert body["markdown"] == MARKDOWN
    finally:
        client.app.dependency_overrides.clear()


def test_known_quiz_artifact_is_refused_before_any_download(tmp_path):
    # The answer-key-free invariant, defended at this layer: a KNOWN non-study-guide id —
    # above all a quiz, whose keyed JSON must never reach a client verbatim — is refused
    # without ever invoking nlm, rather than trusting the CLI to reject a cross-typed --id.
    calls: list[list[str]] = []

    def runner(args):
        calls.append(list(args))
        return _runner_writing(MARKDOWN)(args)

    client = _make_client(tmp_path, runner)
    try:
        r = client.get(f"/api/topics/{NB}/study-guides/{QUIZ}")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["markdown"] is None
        assert "not a study guide" in (body["error"] or "")
        assert calls == []  # refused before the fetch, not after
    finally:
        client.app.dependency_overrides.clear()


def test_auth_failure_is_a_calm_banner_not_a_500(tmp_path):
    client = _make_client(tmp_path, _runner_not_logged_in)
    try:
        r = client.get(f"/api/topics/{NB}/study-guides/{GUIDE}")
        assert r.status_code == 200  # degraded, not a crash
        body = r.json()
        assert body["ok"] is False
        assert body["auth"]["ok"] is False
        assert "nlm login" in (body["auth"]["message"] or "").lower()
        assert body["markdown"] is None
        assert body["error"] is None  # auth lapse renders the banner, not the error string
    finally:
        client.app.dependency_overrides.clear()


def test_exec_failure_is_a_calm_error_not_a_500(tmp_path):
    client = _make_client(tmp_path, _runner_boom)
    try:
        r = client.get(f"/api/topics/{NB}/study-guides/{GUIDE}")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["error"].startswith("Couldn't load this study guide:")
        assert body["auth"]["ok"] is True  # a download failure is not an auth failure
        assert body["markdown"] is None
    finally:
        client.app.dependency_overrides.clear()


def test_empty_markdown_file_is_a_calm_error(tmp_path):
    client = _make_client(tmp_path, _runner_writing("   \n\t\n"))
    try:
        body = client.get(f"/api/topics/{NB}/study-guides/{GUIDE}").json()
        assert body["ok"] is False
        assert "empty" in (body["error"] or "").lower()
        assert body["markdown"] is None
    finally:
        client.app.dependency_overrides.clear()


def test_unknown_notebook_is_404(tmp_path):
    client = _make_client(tmp_path, _runner_writing(MARKDOWN))
    try:
        r = client.get(f"/api/topics/{uid('nosuchnb')}/study-guides/{GUIDE}")
        assert r.status_code == 404
    finally:
        client.app.dependency_overrides.clear()
