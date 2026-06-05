"""The read-only invariant as an enforced boundary: only studio-status/download/version run."""

from __future__ import annotations

import pytest

from app.nlm import DisallowedCommandError, NlmClient, NlmResult


def _record_runner(calls):
    def run(args):
        calls.append(list(args))
        return NlmResult(args=list(args), stdout="[]", stderr="", returncode=0)

    return run


@pytest.mark.parametrize(
    "args",
    [
        ["notebook", "create", "x"],
        ["notebook", "delete", "x"],
        ["source", "add", "x"],
        ["note", "create", "x"],
        ["studio", "create", "audio"],
        ["studio", "delete", "x"],
        ["studio", "revise", "x"],
        ["share", "public", "x"],
        ["export", "x"],
        ["chat", "hi"],
        [],
    ],
)
def test_mutating_or_unknown_commands_are_blocked_before_exec(args):
    calls: list = []
    client = NlmClient(runner=_record_runner(calls))
    with pytest.raises(DisallowedCommandError):
        client._run(args)
    assert calls == []  # nothing was ever executed


def test_only_studio_status_is_allowed_under_studio():
    calls: list = []
    client = NlmClient(runner=_record_runner(calls))
    client._run(["studio", "status", "nb"])  # ok
    assert calls == [["studio", "status", "nb"]]
    with pytest.raises(DisallowedCommandError):
        client._run(["studio", "list"])


def test_download_and_version_are_allowed():
    calls: list = []
    client = NlmClient(runner=_record_runner(calls))
    client._run(["download", "quiz", "nb", "--id", "a", "-f", "json"])
    client._run(["--version"])
    assert ["download", "quiz", "nb", "--id", "a", "-f", "json"] in calls
    assert ["--version"] in calls


def test_public_helpers_only_expose_read_only_ops():
    # The client exposes no method that could mutate a notebook.
    for name in dir(NlmClient):
        assert not any(
            verb in name for verb in ("create", "delete", "revise", "add", "remove", "share")
        )
