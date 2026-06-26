"""Auth/exec failures become typed errors with friendly messages — never raw stack traces."""

from __future__ import annotations

import pytest

from app.nlm import NlmAuthError, NlmClient, NlmExecError, NlmNotFoundError, NlmResult


def _runner_returning(stdout="", stderr="", code=0):
    def run(args):
        return NlmResult(args=list(args), stdout=stdout, stderr=stderr, returncode=code)

    return run


def test_auth_failure_detected_from_stderr():
    client = NlmClient(runner=_runner_returning(stderr="Error: not logged in", code=1))
    with pytest.raises(NlmAuthError) as ei:
        client.studio_status("nb")
    assert "nlm login" in ei.value.user_message.lower()


def test_401_is_auth_error():
    client = NlmClient(runner=_runner_returning(stderr="request failed: 401 Unauthorized", code=1))
    with pytest.raises(NlmAuthError):
        client.studio_status("nb")


def test_not_found_maps_to_notfound():
    client = NlmClient(runner=_runner_returning(stderr="notebook not found", code=1))
    with pytest.raises(NlmNotFoundError):
        client.studio_status("nb")


def test_generic_failure_maps_to_exec_error():
    client = NlmClient(runner=_runner_returning(stderr="boom", code=2))
    with pytest.raises(NlmExecError):
        client.studio_status("nb")


def test_studio_status_parses_json_with_leading_log_line():
    payload = 'INFO starting\n[{"id":"x","type":"quiz","status":"completed"}]'
    client = NlmClient(runner=_runner_returning(stdout=payload, code=0))
    out = client.studio_status("nb")
    assert out == [{"id": "x", "type": "quiz", "status": "completed"}]


def test_studio_status_recovers_json_after_a_bracketed_log_line():
    """A log line that itself contains '[' (e.g. "[INFO] …") must not break recovery: find('[')
    grabs the log's bracket and fails on the whole remainder. The real array follows it."""
    payload = '[INFO] fetching studio status\n[{"id":"x","type":"quiz","status":"completed"}]'
    client = NlmClient(runner=_runner_returning(stdout=payload, code=0))
    out = client.studio_status("nb")
    assert out == [{"id": "x", "type": "quiz", "status": "completed"}]
