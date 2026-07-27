"""app.studycal.port — the CalendarPort seam + the in-memory fakes.

Everything the scheduler needs from a calendar: read free/busy (bare intervals + titled events),
find-or-create the dedicated 'Study' calendar, create events (one at a time or as a batch), delete
events by id, and report how old the OAuth consent is. The API depends only on this Protocol, so the
whole feature is exercised against ``FakeCalendarPort`` in tests + local dry-run, and the real Google
adapter (``app.studycal.google``) is one isolated implementation swapped in via
``deps.get_calendar_port``.

Two fakes, because a fake that always succeeds hides real bugs: ``FakeCalendarPort`` is the happy
path, and ``FlakyCalendarPort`` fails mid-batch so the partial-write invariant is testable at all.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, Union, runtime_checkable

Interval = Tuple[datetime, datetime]
# A busy span the user can *see the title of* — used to flag "what's booked" + annotate double-books.
BusyEvent = Dict[str, Any]  # {"start": datetime, "end": datetime, "title": str}


class CalendarNotConnected(RuntimeError):
    """A calendar operation was attempted before the Google account is connected. The API catches
    this and degrades to an honest 'connect your calendar' state rather than 500ing."""


@runtime_checkable
class CalendarPort(Protocol):
    def is_connected(self) -> bool: ...
    def ensure_study_calendar(self) -> str: ...
    def free_busy(self, start: datetime, end: datetime) -> List[Interval]: ...
    def busy_events(self, start: datetime, end: datetime) -> List[BusyEvent]: ...
    # Single-event create is the primitive: the router writes one event, ledgers it, repeats — so a
    # mid-batch failure can never leave a created event without its (removable) ledger row.
    def create_event(self, calendar_id: str, event: Mapping[str, Any]) -> str: ...
    def create_events(self, calendar_id: str, events: Sequence[Mapping[str, Any]]) -> List[str]: ...
    def delete_events(self, calendar_id: str, event_ids: Sequence[str]) -> None: ...
    # Days since the OAuth consent that minted the current token, when knowable — lets the UI warn
    # before Google's testing-mode 7-day refresh-token expiry silently disconnects the calendar.
    def token_age_days(self) -> Optional[float]: ...


class FakeCalendarPort:
    """In-memory CalendarPort for tests + local dry-run.

    ``free_busy`` returns only the *external* busy it was seeded with — created study events are
    tracked separately, so a test's propose step sees a stable calendar and written blocks don't feed
    back into the next plan. Records created payloads + deletions for assertions. A ``connected=False``
    fake refuses every call with :class:`CalendarNotConnected`, exercising the honest-degrade path.

    ``feed_back=True`` opts out of that isolation: written study events also surface in
    ``free_busy``/``busy_events``, the way a real calendar cannot un-see what you just wrote to it.
    A real calendar always behaves this way, so the default here is a *test* convenience — and the
    reason a re-propose that duplicates already-written blocks was unreachable in tests until now.
    """

    def __init__(
        self,
        *,
        connected: bool = True,
        busy: Optional[Sequence[Union[Interval, Tuple[datetime, datetime, str]]]] = None,
        feed_back: bool = False,
        token_age_days: Optional[float] = None,
    ) -> None:
        self._connected = connected
        # Store as (start, end, title); a bare (start, end) 2-tuple gets the generic title "Busy".
        self._busy: List[Tuple[datetime, datetime, str]] = [
            (iv[0], iv[1], iv[2] if len(iv) > 2 else "Busy") for iv in (busy or [])
        ]
        self._cal_id = "study-cal-fake"
        self._events: Dict[str, Dict[str, Any]] = {}
        self._seq = 0
        self._feed_back = feed_back
        self._token_age_days = token_age_days
        self.deleted: List[str] = []

    def _require(self) -> None:
        if not self._connected:
            raise CalendarNotConnected("calendar not connected")

    def _written_busy(self) -> List[Tuple[datetime, datetime, str]]:
        """Created study events as busy spans (``feed_back`` only). Best-effort: an event whose
        start/end aren't parseable is skipped, never raised, so a junk payload can't break a plan."""
        if not self._feed_back:
            return []
        out: List[Tuple[datetime, datetime, str]] = []
        for ev in self._events.values():
            try:
                s = datetime.fromisoformat(str(ev.get("start", "")))
                e = datetime.fromisoformat(str(ev.get("end", "")))
            except ValueError:
                continue
            out.append((s, e, str(ev.get("summary") or "(busy)")))
        return out

    def is_connected(self) -> bool:
        return self._connected

    def token_age_days(self) -> Optional[float]:
        return self._token_age_days

    def ensure_study_calendar(self) -> str:
        self._require()
        return self._cal_id

    def free_busy(self, start: datetime, end: datetime) -> List[Interval]:
        self._require()
        spans = self._busy + self._written_busy()
        return [(s, e) for (s, e, _t) in spans if e > start and s < end]

    def busy_events(self, start: datetime, end: datetime) -> List[BusyEvent]:
        self._require()
        return [
            {"start": s, "end": e, "title": t}
            for (s, e, t) in self._busy + self._written_busy()
            if e > start and s < end
        ]

    def create_event(self, calendar_id: str, event: Mapping[str, Any]) -> str:
        self._require()
        self._seq += 1
        eid = f"fake-ev-{self._seq}"
        self._events[eid] = {"calendar_id": calendar_id, **dict(event)}
        return eid

    def create_events(self, calendar_id: str, events: Sequence[Mapping[str, Any]]) -> List[str]:
        self._require()  # explicit, so an EMPTY batch still honours the disconnected contract
        return [self.create_event(calendar_id, e) for e in events]

    def delete_events(self, calendar_id: str, event_ids: Sequence[str]) -> None:
        self._require()
        for eid in event_ids:
            self._events.pop(eid, None)
            self.deleted.append(eid)

    # -- test/dry-run helpers --
    def events(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._events)


class FlakyCalendarPort(FakeCalendarPort):
    """A fake that can fail **mid-batch** — the one thing :class:`FakeCalendarPort` cannot do.

    ``create_event`` raises on the ``fail_at``-th call (0-indexed), modelling a rate limit or a
    transient 5xx from Google. Deliberately a plain :class:`RuntimeError`, *not* a
    :class:`CalendarNotConnected`: the router's honest-degrade path already handles the latter, and
    it was the *unhandled* mid-batch failure that orphaned created events outside the removable
    ledger. Every event before ``fail_at`` really is written, so a test can assert the hard rule —
    everything on the calendar has a ledger row — against a genuinely partial write.
    """

    def __init__(self, *, fail_at: Optional[int] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._fail_at = fail_at
        self._creates = 0

    def create_event(self, calendar_id: str, event: Mapping[str, Any]) -> str:
        self._require()
        n, self._creates = self._creates, self._creates + 1
        if self._fail_at is not None and n == self._fail_at:
            raise RuntimeError("calendar write failed (simulated rate limit)")
        return super().create_event(calendar_id, event)
