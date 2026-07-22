"""app.studycal.port — the CalendarPort seam + an in-memory fake.

Everything the scheduler needs from a calendar is four calls: read free/busy, find-or-create the
dedicated 'Study' calendar, batch-create events, delete events by id. The API depends only on this
Protocol, so the whole feature is exercised against ``FakeCalendarPort`` in tests + local dry-run,
and the real Google adapter (``app.studycal.google``) is one isolated implementation swapped in via
``deps.get_calendar_port``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

Interval = Tuple[datetime, datetime]


class CalendarNotConnected(RuntimeError):
    """A calendar operation was attempted before the Google account is connected. The API catches
    this and degrades to an honest 'connect your calendar' state rather than 500ing."""


@runtime_checkable
class CalendarPort(Protocol):
    def is_connected(self) -> bool: ...
    def ensure_study_calendar(self) -> str: ...
    def free_busy(self, start: datetime, end: datetime) -> List[Interval]: ...
    def create_events(self, calendar_id: str, events: Sequence[Mapping[str, Any]]) -> List[str]: ...
    def delete_events(self, calendar_id: str, event_ids: Sequence[str]) -> None: ...


class FakeCalendarPort:
    """In-memory CalendarPort for tests + local dry-run.

    ``free_busy`` returns only the *external* busy it was seeded with — created study events are
    tracked separately, so a test's propose step sees a stable calendar and written blocks don't feed
    back into the next plan. Records created payloads + deletions for assertions. A ``connected=False``
    fake refuses every call with :class:`CalendarNotConnected`, exercising the honest-degrade path.
    """

    def __init__(self, *, connected: bool = True, busy: Optional[Sequence[Interval]] = None) -> None:
        self._connected = connected
        self._busy: List[Interval] = list(busy or [])
        self._cal_id = "study-cal-fake"
        self._events: Dict[str, Dict[str, Any]] = {}
        self._seq = 0
        self.deleted: List[str] = []

    def _require(self) -> None:
        if not self._connected:
            raise CalendarNotConnected("calendar not connected")

    def is_connected(self) -> bool:
        return self._connected

    def ensure_study_calendar(self) -> str:
        self._require()
        return self._cal_id

    def free_busy(self, start: datetime, end: datetime) -> List[Interval]:
        self._require()
        return [iv for iv in self._busy if iv[1] > start and iv[0] < end]

    def create_events(self, calendar_id: str, events: Sequence[Mapping[str, Any]]) -> List[str]:
        self._require()
        ids: List[str] = []
        for e in events:
            self._seq += 1
            eid = f"fake-ev-{self._seq}"
            self._events[eid] = {"calendar_id": calendar_id, **dict(e)}
            ids.append(eid)
        return ids

    def delete_events(self, calendar_id: str, event_ids: Sequence[str]) -> None:
        self._require()
        for eid in event_ids:
            self._events.pop(eid, None)
            self.deleted.append(eid)

    # -- test/dry-run helpers --
    def events(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._events)
