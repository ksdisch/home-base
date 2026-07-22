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

from datetime import datetime
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

    # -- connection -------------------------------------------------------------

    @staticmethod
    def _import_libs() -> Optional[Any]:
        """Lazily import the google-api client. Returns a small namespace, or ``None`` if the
        libraries aren't installed — so an un-provisioned machine degrades instead of crashing."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            return {"Request": Request, "Credentials": Credentials, "build": build}
        except ImportError:
            return None

    def is_connected(self) -> bool:
        """True only when both the libraries and a saved token are present — the honest gate the API
        checks before proposing/writing."""
        return self.token_path.is_file() and self._import_libs() is not None

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
        creds = libs["Credentials"].from_authorized_user_file(str(self.token_path), SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(libs["Request"]())
                self.token_path.write_text(creds.to_json(), encoding="utf-8")
            else:
                raise CalendarNotConnected("Google Calendar token invalid — re-run login")
        return libs["build"]("calendar", "v3", credentials=creds, cache_discovery=False)

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

    def create_events(self, calendar_id: str, events: Sequence[Mapping[str, Any]]) -> List[str]:
        """Insert each proposed block as an event; return the created event ids (order preserved), so
        the ledger can delete them later. Each ``event`` carries ``summary``/``start``/``end`` and an
        optional ``description``."""
        svc = self._service()
        ids: List[str] = []
        for e in events:
            body = {
                "summary": e["summary"],
                "description": e.get("description", ""),
                "start": {"dateTime": e["start"], "timeZone": _TZ},
                "end": {"dateTime": e["end"], "timeZone": _TZ},
            }
            created = svc.events().insert(calendarId=calendar_id, body=body).execute()
            ids.append(created["id"])
        return ids

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
    print(f"✓ Google Calendar connected — token saved to {port.token_path}")


if __name__ == "__main__":  # pragma: no cover - manual one-time setup
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "login":
        _login()
    else:
        print("usage: python -m app.studycal.google login")
