"""Which Kyle opened the brief? (docs/ideas/builder-vs-reader-metric.md)

``brief_visits`` stored only (day, visited_at), so the ~08-03 v1 success check (≥5
mornings/week = distinct visit days) could not tell a Tuesday morning read from a localhost
dev load, a Playwright run, or a verify pass. The verification culture that keeps this repo
trustworthy is exactly what poisoned the well: every clean verify WAS a counted visit.

This maps one request to one coarse bucket, written to ``brief_visits.source`` at write
time. Deliberately small — no analytics platform, no sessions, no user-agent
fingerprinting. One tag per visit, nothing else.

Buckets:

``phone``          a tailnet peer — the M6 read path, and the one signal that means
                   reader-Kyle. Caveat carried into the PR: Kyle sometimes reads on the
                   DESKTOP over the tailnet, and that lands here too. Separating them
                   would need the user-agent sniffing this idea put out of scope, so
                   'phone' means "over the tailnet", which over-counts rather than
                   under-counts. Revisit if the two numbers diverge oddly.
``mac-localhost``  loopback — builder-Kyle at the machine (or the deployed build opened
                   on the Mac itself).
``dev``            the Vite dev server's origin, whatever the peer IP. Build traffic.
``test``           starlette's TestClient — this suite's own traffic, self-labelling.
``lan``            a private-network peer that is not loopback and not the tailnet.
``other``          anything else (public address, unparseable host).
``unknown``        no peer information at all — never guessed as 'phone'.

Trust note: only the transport peer is read. ``X-Forwarded-For`` is deliberately IGNORED —
it is client-settable, and a spoofable header feeding the metric that certifies v1 would
reintroduce the exact problem this module exists to fix. The hub is served by uvicorn
directly (M6), so the peer is the real client.
"""

from __future__ import annotations

import ipaddress
from typing import Any, Optional
from urllib.parse import urlsplit

PHONE = "phone"
MAC_LOCALHOST = "mac-localhost"
DEV = "dev"
TEST = "test"
LAN = "lan"
OTHER = "other"
UNKNOWN = "unknown"

# Tailscale assigns every node a 100.64.0.0/10 (RFC 6598 carrier-grade NAT) v4 address and
# an fd7a:115c:a1e0::/48 v6 address. Both are checked BEFORE the generic private-address
# test: ipaddress counts CGNAT and ULA space as private, so a plain is_private check would
# file the phone under 'lan' and silently undercount the honest number.
_TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")
_TAILNET_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")

# starlette's TestClient reports this literal as the peer host.
_TEST_HOSTS = {"testclient"}

# Hostname forms that never reach ip_address() but mean loopback.
_LOOPBACK_HOSTS = {"localhost", "ip6-localhost"}

# The Vite dev server's port (frontend/vite.config.ts). It proxies /api to FastAPI, so a
# dev load arrives from loopback — same peer as a real read of the deployed build on :8000.
# The Origin header is the only thing that separates them.
_DEV_PORTS = {5173}


def _is_dev_origin(origin: Optional[str]) -> bool:
    """True when the page making the call was served by the Vite dev server."""
    if not origin:
        return False
    try:
        port = urlsplit(origin).port
    except ValueError:  # malformed port in the header
        return False
    return port in _DEV_PORTS


def classify_source(client_host: Optional[str], origin: Optional[str] = None) -> str:
    """One request's origin bucket. ``origin`` is the Origin (or Referer) header.

    The dev origin is checked first on purpose: browsing the dev server over the tailnet is
    still build traffic, not a morning read, so the header must beat the IP.
    """
    if _is_dev_origin(origin):
        return DEV
    if not client_host:
        return UNKNOWN

    host = client_host.strip().lower()
    if host in _TEST_HOSTS:
        return TEST
    if host in _LOOPBACK_HOSTS:
        return MAC_LOCALHOST

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return OTHER

    # A dual-stack socket can report a v4 peer as ::ffff:100.64.0.5 — same machine.
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped

    if addr.is_loopback:
        return MAC_LOCALHOST
    if addr in (_TAILNET_V4 if addr.version == 4 else _TAILNET_V6):
        return PHONE
    if addr.is_private:
        return LAN
    return OTHER


def source_from_request(request: Any) -> str:
    """Classify a FastAPI/starlette ``Request``. ``request.client`` is Optional, and an
    absent peer degrades to 'unknown' — a metric that guesses 'phone' when it does not know
    is the bug, not the fix."""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    headers = getattr(request, "headers", {}) or {}
    origin = headers.get("origin") or headers.get("referer")
    return classify_source(host, origin)
