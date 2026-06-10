"""The `nlm download` transport contract after the ≥0.5 CLI change: artifacts land in a FILE at
the `-o` path the client injects (stdout carries only a "✓ Downloaded …" line), while older CLIs
printed the body to stdout. Pins `_download_to_text`'s file-first / stdout-fallback behavior for
quizzes and study guides, the calm typed error when neither yields parseable quiz JSON
(regression: this used to escape as json.JSONDecodeError and 500 the prepare endpoint), and the
exact read-only command each helper issues. No real `nlm` is ever run — runners are injected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.nlm import NlmClient, NlmExecError, NlmResult


# -- fake runners ------------------------------------------------------------------


def _out_path(args) -> Path:
    """The temp path `_download_to_text` injected via `-o`."""
    return Path(args[args.index("-o") + 1])


def _file_writer(body: str, calls: list | None = None):
    """A fake `nlm` ≥0.5: writes the artifact body to the `-o` path; stdout is only a ✓ line."""

    def run(args):
        if calls is not None:
            calls.append(list(args))
        out = _out_path(args)
        out.write_text(body, encoding="utf-8")
        return NlmResult(args=list(args), stdout=f"✓ Downloaded to: {out}\n",
                         stderr="", returncode=0)

    return run


def _stdout_only(body: str, calls: list | None = None):
    """A fake pre-0.5 `nlm` (and the style every older test runner uses): body on stdout,
    nothing written to disk."""

    def run(args):
        if calls is not None:
            calls.append(list(args))
        return NlmResult(args=list(args), stdout=body, stderr="", returncode=0)

    return run


# -- download_quiz: file-first, stdout fallback, calm failure -----------------------


def test_download_quiz_reads_the_file_the_new_cli_writes():
    quiz = {"questions": [{"question": "q?"}]}
    client = NlmClient(runner=_file_writer(json.dumps(quiz)))
    assert client.download_quiz("nb", "art") == quiz


def test_download_quiz_falls_back_to_stdout_for_the_old_cli():
    quiz = {"title": "t", "questions": []}
    client = NlmClient(runner=_stdout_only(json.dumps(quiz)))
    assert client.download_quiz("nb", "art") == quiz


def test_download_quiz_confirmation_line_only_raises_typed_error_not_jsondecode():
    # Regression: a ✓ line with no file used to bubble json.JSONDecodeError out of the client.
    # It now fails at the transport layer (the body never landed anywhere we can read), uniform
    # across quiz and study-guide downloads.
    client = NlmClient(runner=_stdout_only("✓ Downloaded quiz to: somewhere.json\n"))
    with pytest.raises(NlmExecError) as ei:
        client.download_quiz("nb", "art")
    assert "wrote nothing" in str(ei.value).lower()
    assert "somewhere.json" in ei.value.detail  # the raw text rides along for diagnosis


def test_download_quiz_command_keeps_json_format_and_appends_output_path():
    calls: list = []
    client = NlmClient(runner=_file_writer('{"questions": []}', calls))
    client.download_quiz("nb-1", "art-1")
    (args,) = calls
    assert args[:7] == ["download", "quiz", "nb-1", "--id", "art-1", "-f", "json"]
    assert args[7] == "-o" and args[8].endswith("artifact.json")


# -- download_study_guide: same transport, markdown body ----------------------------


def test_download_study_guide_reads_the_file_the_new_cli_writes():
    md = "# Guide\n\nSome **markdown** body.\n"
    client = NlmClient(runner=_file_writer(md))
    assert client.download_study_guide("nb", "art") == md


def test_download_study_guide_falls_back_to_stdout_for_the_old_cli():
    client = NlmClient(runner=_stdout_only("# Guide from stdout\n"))
    assert client.download_study_guide("nb", "art") == "# Guide from stdout\n"


def test_download_study_guide_issues_a_readonly_report_download():
    # Study guides ride `download report --id` (markdown is its only format, so no `-f`). The
    # recorded call proves the command passed `_assert_readonly`, which runs before any runner.
    calls: list = []
    client = NlmClient(runner=_file_writer("# g", calls))
    client.download_study_guide("nb-1", "art-1")
    (args,) = calls
    assert args[:5] == ["download", "report", "nb-1", "--id", "art-1"]
    assert "-f" not in args
    assert args[5] == "-o" and args[6].endswith("artifact.md")
