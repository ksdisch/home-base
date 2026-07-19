"""P1 bug #5 (docs/bug-hunt/2026-07-19-post-m7.md): with the com.homebase.server
KeepAlive agent holding :8000, ./dev.sh let the dev uvicorn die at bind in a
backgrounded subshell while Vite came up and silently proxied /api to the PROD
server — backend edits never applied and dev-frontend writes landed in prod data.
The guard must detect the taken port and refuse to start, naming the LaunchAgent.

The test binds an ephemeral port and points dev.sh at it via BACKEND_PORT — the
real :8000 (possibly the live prod agent on this very machine) is never touched,
and the guard path exits before any server, pip, or npm process starts.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

DEV_SH = Path(__file__).resolve().parents[2] / "dev.sh"


def test_dev_sh_refuses_to_start_when_the_backend_port_is_taken():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        try:
            proc = subprocess.run(
                ["bash", str(DEV_SH)],
                env={**os.environ, "BACKEND_PORT": str(port)},
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise AssertionError(
                "dev.sh kept going with the backend port taken — the guard must "
                "refuse fast and name com.homebase.server"
            )
    finally:
        sock.close()

    out = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "com.homebase.server" in out  # names the likely culprit
    assert str(port) in out  # says which port is blocked
