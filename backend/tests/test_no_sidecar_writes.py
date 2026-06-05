"""Prove the hub never writes under the NotebookLM sidecar tree.

Snapshot every file's (size, mtime, sha256) under the real root, run a full catalog load + a
per-notebook topic build (and a pure reconcile against a synthetic live listing), then assert the
tree is byte-for-byte unchanged.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.catalog.build import to_topic_detail
from app.catalog.ingest import load_sidecars
from app.catalog.reconcile import reconcile

from .conftest import REAL_ROOT, needs_real_data

pytestmark = needs_real_data


def _snapshot(root: Path) -> dict:
    snap = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            data = p.read_bytes()
            st = p.stat()
            snap[str(p)] = (st.st_size, st.st_mtime_ns, hashlib.sha256(data).hexdigest())
    return snap


def test_catalog_and_reconcile_do_not_mutate_sidecars():
    before = _snapshot(REAL_ROOT)

    load = load_sidecars(REAL_ROOT)
    for sc in load.sidecars:
        to_topic_detail(sc, sc.artifacts, {})
        # Exercise reconcile with a fake live listing (no nlm call, no writes).
        fake_live = [{"id": a.artifact_id, "type": a.type, "status": "completed"} for a in sc.artifacts]
        reconcile(sc.artifacts, fake_live)

    after = _snapshot(REAL_ROOT)
    assert before == after, "the sidecar tree changed — the hub must be read-only toward it"
