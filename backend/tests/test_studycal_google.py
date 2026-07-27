"""app.studycal.google — the real Google adapter's honest-degrade seam.

``google.py`` is the feature's one untested edge (real Google I/O), and that is exactly where the
7-day testing-mode token leash bites: a token minted on consent day N stops refreshing around N+7.
These tests stub ``_import_libs`` so no google library and no network is involved, and lock the
promise the module's own docstring makes — *never a 500, always a "connect your calendar" state*:

* a corrupt/unreadable token file degrades to :class:`CalendarNotConnected`, not ``ValueError``;
* an expired refresh token (``RefreshError``) degrades the same way, with re-login copy;
* an unreachable Google (``TransportError``) says so instead of blaming the token;
* ``is_connected()`` tells the truth about a token that cannot be used, so ``GET /schedule`` can't
  report ``connected: true`` over endpoints that are about to fail.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pytest

from app.studycal.google import GoogleCalendarPort
from app.studycal.port import CalendarNotConnected


class _RefreshError(Exception):
    """Stands in for ``google.auth.exceptions.RefreshError`` (revoked/expired refresh token)."""


class _TransportError(Exception):
    """Stands in for ``google.auth.exceptions.TransportError`` (Google unreachable)."""


class _Creds:
    """A minimal google-auth ``Credentials`` stand-in."""

    def __init__(self, *, valid: bool = True, expired: bool = False, refresh_token: Optional[str] = "rt",
                 raises: Optional[Exception] = None) -> None:
        self.valid, self.expired, self.refresh_token, self._raises = valid, expired, refresh_token, raises

    def refresh(self, _request: Any) -> None:
        if self._raises is not None:
            raise self._raises
        self.valid, self.expired = True, False

    def to_json(self) -> str:
        return json.dumps({"refreshed": True})


def _port(tmp_path: Path, *, token: str = '{"refresh_token": "rt"}') -> GoogleCalendarPort:
    p = GoogleCalendarPort(data_dir=tmp_path)
    if token is not None:
        p.token_path.write_text(token, encoding="utf-8")
    return p


def _stub_libs(monkeypatch, port: GoogleCalendarPort, *, creds: Any = None, load_raises: Optional[Exception] = None):
    """Point ``_import_libs`` at fakes — no google package, no network, no real token."""

    class _Credentials:
        @staticmethod
        def from_authorized_user_file(_path: str, _scopes: Any) -> Any:
            if load_raises is not None:
                raise load_raises
            return creds

    monkeypatch.setattr(
        type(port),
        "_import_libs",
        staticmethod(lambda: {
            "Credentials": _Credentials,
            "Request": lambda: None,
            "build": lambda *a, **k: object(),
            "RefreshError": _RefreshError,
            "TransportError": _TransportError,
        }),
    )


# -- _service(): every unusable-token path becomes CalendarNotConnected --------------------------


def test_corrupt_token_file_degrades_instead_of_raising_valueerror(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path, token="{not json at all")
    _stub_libs(monkeypatch, port, load_raises=ValueError("Expecting property name"))
    # The router catches CalendarNotConnected and nothing else — a bare ValueError here is a 500.
    with pytest.raises(CalendarNotConnected) as exc:
        port._service()
    assert "login" in str(exc.value).lower()


def test_expired_refresh_token_degrades_with_re_login_copy(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path)
    _stub_libs(monkeypatch, port, creds=_Creds(valid=False, expired=True, raises=_RefreshError("invalid_grant")))
    # This is the ~07-29 failure: consent expires, refresh is rejected, and every scheduler
    # endpoint used to 500 behind a connected=true facade.
    with pytest.raises(CalendarNotConnected) as exc:
        port._service()
    assert "login" in str(exc.value).lower()


def test_unreachable_google_says_so_rather_than_blaming_the_token(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path)
    _stub_libs(monkeypatch, port, creds=_Creds(valid=False, expired=True, raises=_TransportError("dns")))
    with pytest.raises(CalendarNotConnected) as exc:
        port._service()
    # Honest labelling: a dropped connection must not tell Kyle to re-run the login.
    assert "reach" in str(exc.value).lower() and "login" not in str(exc.value).lower()


def test_unreadable_token_file_degrades(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path)
    _stub_libs(monkeypatch, port, load_raises=OSError("permission denied"))
    # OSError is not a ValueError — it would otherwise escape the except clause entirely.
    with pytest.raises(CalendarNotConnected):
        port._service()


def test_a_healthy_token_still_builds_a_service(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path)
    _stub_libs(monkeypatch, port, creds=_Creds(valid=True))
    assert port._service() is not None  # the degrade must not swallow the happy path


def test_a_refreshed_token_is_written_back(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path)
    _stub_libs(monkeypatch, port, creds=_Creds(valid=False, expired=True))
    assert port._service() is not None
    assert json.loads(port.token_path.read_text(encoding="utf-8")) == {"refreshed": True}


# -- is_connected(): stops reporting True for a token that cannot be used ------------------------


def test_is_connected_is_false_for_a_corrupt_token(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path, token="garbage")
    _stub_libs(monkeypatch, port, load_raises=ValueError("bad json"))
    # The whole point: GET /schedule must not claim connected while propose/confirm 409.
    assert port.is_connected() is False


def test_is_connected_is_false_when_the_token_cannot_be_renewed(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path)
    _stub_libs(monkeypatch, port, creds=_Creds(valid=False, expired=True, refresh_token=None))
    assert port.is_connected() is False


def test_is_connected_is_true_for_a_stale_but_refreshable_token(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path)
    _stub_libs(monkeypatch, port, creds=_Creds(valid=False, expired=True, refresh_token="rt"))
    # Expired access token + a live refresh token is the normal steady state — still connected.
    assert port.is_connected() is True


def test_is_connected_is_false_without_a_token_file(tmp_path, monkeypatch) -> None:
    port = GoogleCalendarPort(data_dir=tmp_path)
    _stub_libs(monkeypatch, port, creds=_Creds())
    assert port.is_connected() is False


# -- token_age_days(): days since CONSENT, which survives the hourly silent refresh --------------


def test_token_age_days_is_none_without_a_token(tmp_path) -> None:
    assert GoogleCalendarPort(data_dir=tmp_path).token_age_days() is None


def test_token_age_days_reads_the_consent_stamp(tmp_path) -> None:
    port = _port(tmp_path)
    stamped = datetime.now(timezone.utc) - timedelta(days=6, hours=12)
    port.issued_path.write_text(stamped.isoformat(), encoding="utf-8")
    age = port.token_age_days()
    assert age is not None and 6.4 < age < 6.6


def test_token_age_days_survives_a_token_rewrite(tmp_path, monkeypatch) -> None:
    port = _port(tmp_path)
    stamped = datetime.now(timezone.utc) - timedelta(days=6)
    port.issued_path.write_text(stamped.isoformat(), encoding="utf-8")
    _stub_libs(monkeypatch, port, creds=_Creds(valid=False, expired=True))
    port._service()  # silent hourly refresh rewrites google-token.json...
    age = port.token_age_days()
    # ...but the age still tracks consent, or the near-day-7 warning would never fire.
    assert age is not None and age > 5.9


def test_token_age_days_falls_back_to_the_token_file_when_unstamped(tmp_path) -> None:
    port = _port(tmp_path)  # no issued stamp — a pre-existing install
    age = port.token_age_days()
    assert age is not None and age < 1


def test_token_age_days_ignores_a_corrupt_stamp(tmp_path) -> None:
    port = _port(tmp_path)
    port.issued_path.write_text("not-a-timestamp", encoding="utf-8")
    age = port.token_age_days()
    assert age is not None and age < 1  # falls back rather than raising
