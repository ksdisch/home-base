"""app.studycal.google — the real Google Calendar adapter behind ``CalendarPort``.

Isolated on purpose: the whole feature is exercised against ``FakeCalendarPort``, so this file is the
one untested edge (real Google I/O). The google-api client is imported **lazily** inside methods, so
importing this module — and the honest-degrade path — works even when the libraries or a token aren't
installed yet: :meth:`is_connected` returns ``False`` and the API surfaces a "connect your calendar"
state instead of 500ing.

One-time setup (see ``docs/STUDY_SCHEDULER.md``): create an OAuth **Desktop** client in Google Cloud,
drop the client secret at ``<data_dir>/google-oauth-client.json``, then run
``python -m app.studycal.google login`` once to consent — it writes ``<data_dir>/google-token.json``,
after which the backend refreshes silently.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..config import get_settings
from .port import CalendarNotConnected

Interval = Tuple[datetime, datetime]

# Read/write the user's calendars + free/busy. One scope keeps the consent screen simple.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
STUDY_CALENDAR_NAME = "Study (Home Base)"
_TZ = "America/Chicago"


class GoogleCalendarPort:
    """CalendarPort over the Google Calendar API for Kyle's own account (single user, local)."""

    def __init__(self, *, data_dir: Optional[Path] = None) -> None:
        base = data_dir or get_settings().data_dir
        self.client_secret_path = base / "google-oauth-client.json"
        self.token_path = base / "google-token.json"
        # Consent timestamp, stamped once at login. Separate from the token file *because*
        # ``_service`` rewrites that file on every silent refresh — its mtime tracks the last
        # refresh (minutes ago), not the consent the 7-day leash actually counts from.
        self.issued_path = base / "google-token-issued"

    # -- connection -------------------------------------------------------------

    @staticmethod
    def _import_libs() -> Optional[Any]:
        """Lazily import the google-api client. Returns a small namespace, or ``None`` if the
        libraries aren't installed — so an un-provisioned machine degrades instead of crashing."""
        try:
            from google.auth.exceptions import RefreshError, TransportError
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            return {
                "Request": Request,
                "Credentials": Credentials,
                "build": build,
                "RefreshError": RefreshError,
                "TransportError": TransportError,
            }
        except ImportError:
            return None

    def _load_creds(self, libs: Any) -> Any:
        """Parse the saved token. File I/O + JSON only — never a refresh, never the network, so
        this is safe on the read-only ``is_connected`` path."""
        return libs["Credentials"].from_authorized_user_file(str(self.token_path), SCOPES)

    def is_connected(self) -> bool:
        """True only when the libraries, a saved token, and a *usable* credential are all present.

        Deliberately more than a file-existence check: a corrupt token, or one whose access token
        has expired with no refresh token left, cannot serve a single call — reporting ``True`` for
        it is how ``GET /schedule`` came to claim ``connected`` while every other endpoint 500'd."""
        libs = self._import_libs()
        if libs is None or not self.token_path.is_file():
            return False
        try:
            creds = self._load_creds(libs)
        except Exception:
            return False  # unreadable/corrupt token — honestly disconnected
        # Valid now, or stale-but-renewable (the normal steady state between hourly refreshes).
        return bool(getattr(creds, "valid", False) or getattr(creds, "refresh_token", None))

    def token_age_days(self) -> Optional[float]:
        """Days since the OAuth consent that minted the current token, or ``None`` when unknown.

        Read from the login-time stamp; falls back to the token file's mtime for installs that
        predate the stamp (imprecise — the refresh rewrite resets it — but better than nothing)."""
        try:
            if self.issued_path.is_file():
                stamped = datetime.fromisoformat(self.issued_path.read_text(encoding="utf-8").strip())
                if stamped.tzinfo is None:
                    stamped = stamped.replace(tzinfo=timezone.utc)
                return max(0.0, (datetime.now(timezone.utc) - stamped).total_seconds() / 86400)
        except (OSError, ValueError):
            pass  # corrupt stamp — fall through to the mtime estimate
        try:
            if self.token_path.is_file():
                age = datetime.now(timezone.utc).timestamp() - self.token_path.stat().st_mtime
                return max(0.0, age / 86400)
        except OSError:
            pass
        return None

    def _service(self) -> Any:
        libs = self._import_libs()
        if libs is None:
            raise CalendarNotConnected(
                "Google API libraries not installed — see docs/STUDY_SCHEDULER.md"
            )
        if not self.token_path.is_file():
            raise CalendarNotConnected(
                "Google Calendar not connected — run `python -m app.studycal.google login`"
            )
        # Everything from here to the built service is wrapped: an expired consent (the documented
        # ~7-day testing-mode leash), a truncated/corrupt token file, or an unreachable Google must
        # all surface as CalendarNotConnected — the one exception the router degrades on. Anything
        # else escapes as a 500 behind a `connected: true` state, which is the lie this prevents.
        try:
            creds = self._load_creds(libs)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(libs["Request"]())
                    self.token_path.write_text(creds.to_json(), encoding="utf-8")
                else:
                    raise CalendarNotConnected(
                        "Google Calendar token invalid — run `python -m app.studycal.google login`"
                    )
            return libs["build"]("calendar", "v3", credentials=creds, cache_discovery=False)
        except libs["TransportError"] as e:
            # A dropped connection is not an expired consent — never tell Kyle to re-run the login
            # because his wifi blinked.
            raise CalendarNotConnected(f"Couldn't reach Google Calendar — try again shortly ({e})")
        except libs["RefreshError"] as e:
            raise CalendarNotConnected(
                "Google Calendar access expired — run `python -m app.studycal.google login` again "
                f"(testing-mode consent lapses after ~7 days; see docs/STUDY_SCHEDULER.md) [{e}]"
            )
        except (ValueError, KeyError, OSError) as e:
            # json.JSONDecodeError/UnicodeDecodeError subclass ValueError; OSError does not.
            raise CalendarNotConnected(
                f"Google Calendar token unreadable — run `python -m app.studycal.google login` [{e}]"
            )

    # -- CalendarPort -----------------------------------------------------------

    def ensure_study_calendar(self) -> str:
        """Find the dedicated 'Study' calendar by name, creating it once if absent. Writing to a
        separate calendar (Kyle's call) keeps study blocks muteable + bulk-removable."""
        svc = self._service()
        page_token = None
        while True:
            resp = svc.calendarList().list(pageToken=page_token).execute()
            for cal in resp.get("items", []):
                if cal.get("summary") == STUDY_CALENDAR_NAME:
                    return cal["id"]
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        created = svc.calendars().insert(
            body={"summary": STUDY_CALENDAR_NAME, "timeZone": _TZ}
        ).execute()
        return created["id"]

    def free_busy(self, start: datetime, end: datetime) -> List[Interval]:
        """The user's busy intervals on their primary calendar between ``start`` and ``end`` — the
        real conflicts the planner must dodge. Returned as tz-aware ``(start, end)`` tuples."""
        svc = self._service()
        resp = svc.freebusy().query(
            body={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "items": [{"id": "primary"}],
            }
        ).execute()
        busy = resp.get("calendars", {}).get("primary", {}).get("busy", [])
        out: List[Interval] = []
        for b in busy:
            try:
                out.append((datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"])))
            except (KeyError, ValueError):
                continue
        return out

    def busy_events(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """The user's **titled** primary-calendar events in ``[start, end]`` — so the scheduler can
        flag *what* is booked (e.g. a shared "GF: dinner" the user can study through) and annotate a
        double-book. Only timed events count (all-day events don't occupy a time-of-day slot);
        declined and 'free'-transparency events are skipped (they aren't real conflicts). Best-effort:
        titles come from the same account already used for free/busy — the freebusy call remains the
        source of truth for *placement*."""
        svc = self._service()
        out: List[Dict[str, Any]] = []
        page_token = None
        while True:
            resp = svc.events().list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            ).execute()
            for ev in resp.get("items", []):
                s, e = ev.get("start", {}), ev.get("end", {})
                if "dateTime" not in s or "dateTime" not in e:
                    continue  # all-day / open-ended — not a time-of-day conflict
                if ev.get("transparency") == "transparent":
                    continue  # marked "free"
                if any(a.get("self") and a.get("responseStatus") == "declined" for a in ev.get("attendees", [])):
                    continue  # the user declined it — not their conflict
                try:
                    out.append({
                        "start": datetime.fromisoformat(s["dateTime"]),
                        "end": datetime.fromisoformat(e["dateTime"]),
                        "title": (ev.get("summary") or "(busy)").strip(),
                    })
                except (KeyError, ValueError):
                    continue
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    def create_event(self, calendar_id: str, event: Mapping[str, Any]) -> str:
        """Insert ONE proposed block and return its event id. The single-event primitive exists so
        the caller can record each event in the removable ledger the moment it lands — a batch that
        only reports ids after every insert succeeds strands the earlier ones on a mid-batch
        failure. ``event`` carries ``summary``/``start``/``end`` and an optional ``description``."""
        svc = self._service()
        body = {
            "summary": event["summary"],
            "description": event.get("description", ""),
            "start": {"dateTime": event["start"], "timeZone": _TZ},
            "end": {"dateTime": event["end"], "timeZone": _TZ},
        }
        created = svc.events().insert(calendarId=calendar_id, body=body).execute()
        return created["id"]

    def create_events(self, calendar_id: str, events: Sequence[Mapping[str, Any]]) -> List[str]:
        """Insert each proposed block as an event; return the created event ids (order preserved).
        Convenience batch over :meth:`create_event` — callers that must not strand a partial write
        should drive ``create_event`` themselves and ledger as they go."""
        return [self.create_event(calendar_id, e) for e in events]

    def delete_events(self, calendar_id: str, event_ids: Sequence[str]) -> None:
        """Delete events by id. An already-gone event (404/410) is treated as success — removal must
        be idempotent so a half-finished remove can always be retried."""
        svc = self._service()
        for eid in event_ids:
            try:
                svc.events().delete(calendarId=calendar_id, eventId=eid).execute()
            except Exception as exc:  # googleapiclient.errors.HttpError, lazily imported
                status = getattr(getattr(exc, "resp", None), "status", None)
                if status in (404, 410):
                    continue
                raise


def _login(data_dir: Optional[Path] = None) -> None:
    """One-time OAuth consent (installed-app flow): opens a browser, then writes the token. Run via
    ``python -m app.studycal.google login`` after dropping the client secret next to it."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    port = GoogleCalendarPort(data_dir=data_dir)
    if not port.client_secret_path.is_file():
        raise SystemExit(
            f"Missing OAuth client secret at {port.client_secret_path} — create an OAuth Desktop "
            "client in Google Cloud and download it there first (see docs/STUDY_SCHEDULER.md)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(port.client_secret_path), SCOPES)
    creds = flow.run_local_server(port=0)
    port.token_path.write_text(creds.to_json(), encoding="utf-8")
    # Stamp the consent time separately — the token file itself gets rewritten on every silent
    # refresh, so only this survives to tell the UI how close the 7-day leash is.
    port.issued_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    print(f"✓ Google Calendar connected — token saved to {port.token_path}")


if __name__ == "__main__":  # pragma: no cover - manual one-time setup
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "login":
        _login()
    else:
        print("usage: python -m app.studycal.google login")
