"""Thin, read-only wrapper around the `nlm` CLI.

Every nlm invocation in the entire hub flows through :class:`NlmClient`. Mutating
subcommands are impossible to run: ``_assert_readonly`` rejects anything outside a small
allowlist *before* a subprocess is spawned. A ``runner`` can be injected for tests so no real
CLI (or network) is touched.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from ..config import get_settings
from .errors import (
    DisallowedCommandError,
    NlmAuthError,
    NlmExecError,
    NlmNotFoundError,
)

# Read-only top-level subcommands the hub may invoke. Anything that could mutate a notebook
# (notebook/source/note/studio-create/share/import/...) is absent by construction.
_ALLOWED_TOP = frozenset({"studio", "download", "doctor"})
_ALLOWED_STUDIO_SUB = frozenset({"status"})
# All read-only artifact types `nlm download <type>` accepts (every one just fetches).
_ALLOWED_DOWNLOAD_SUB = frozenset(
    {
        "quiz", "report", "flashcards", "mind-map", "mind_map", "mindmap",
        "audio", "video", "slide-deck", "slide_deck", "slides",
        "infographic", "data-table", "data_table", "study-guide", "study_guide",
    }
)
_VERSION_TOKENS = frozenset({"--version", "-v"})

# Substrings (in an underscore-normalized, lowercased blob) that indicate an auth failure.
_AUTH_SIGNATURES = (
    "unauthenticated",
    "unauthorized",
    "not logged in",
    "please log in",
    "login required",
    "nlm login",
    "permission denied",
    "invalid credentials",
    "invalid grant",
    "expired token",
    "token has been expired",
    "token expired",
    "no refresh token",
    "could not refresh",
    "reauth",
    "re authenticate",
    "sign in",
    "oauth",
    "consent",
    "profile not found",
)
# HTTP auth codes matched only as standalone tokens (so a UUID containing "401" is not auth).
_AUTH_CODE_RE = re.compile(r"\b(401|403)\b")
_NOTFOUND_CODE_RE = re.compile(r"\b404\b")


@dataclass
class NlmResult:
    args: list[str]
    stdout: str
    stderr: str
    returncode: int


Runner = Callable[[Sequence[str]], NlmResult]


def _assert_readonly(args: Sequence[str]) -> None:
    """Raise :class:`DisallowedCommandError` if ``args`` is not a known read-only command."""
    if not args:
        raise DisallowedCommandError("Refusing to run nlm with no arguments.")
    head = args[0]
    if head in _VERSION_TOKENS:
        if len(args) != 1:  # never forward trailing tokens past a version flag
            raise DisallowedCommandError(
                f"nlm version flag does not take arguments: {' '.join(args)}",
                detail=" ".join(args),
            )
        return
    if head not in _ALLOWED_TOP:
        raise DisallowedCommandError(
            f"nlm subcommand '{head}' is not on the read-only allowlist.",
            detail=" ".join(args),
        )
    if head == "studio":
        sub = args[1] if len(args) > 1 else ""
        if sub not in _ALLOWED_STUDIO_SUB:
            raise DisallowedCommandError(
                f"nlm studio '{sub or '<none>'}' is not read-only (only 'status' is allowed).",
                detail=" ".join(args),
            )
    elif head == "download":
        sub = args[1] if len(args) > 1 else ""
        if sub not in _ALLOWED_DOWNLOAD_SUB:
            raise DisallowedCommandError(
                f"nlm download '{sub or '<none>'}' is not on the read-only download allowlist.",
                detail=" ".join(args),
            )


class NlmClient:
    def __init__(self, binary: Optional[str] = None, *, runner: Optional[Runner] = None) -> None:
        self.binary = binary or get_settings().nlm_bin
        self._runner = runner  # injected in tests; default uses subprocess

    # -- low-level -------------------------------------------------------------
    def _run(self, args: list[str], *, timeout: float = 60.0) -> NlmResult:
        _assert_readonly(args)  # enforced for BOTH real and injected runners
        if self._runner is not None:
            res = self._runner(args)
        else:
            exe = shutil.which(self.binary) or self.binary
            try:
                proc = subprocess.run(
                    [exe, *args], capture_output=True, text=True, timeout=timeout
                )
            except FileNotFoundError as e:
                raise NlmExecError("nlm executable not found on PATH.", detail=str(e)) from e
            except subprocess.TimeoutExpired as e:
                raise NlmExecError("nlm command timed out.", detail=str(e)) from e
            res = NlmResult(
                args=list(args),
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
            )
        if res.returncode != 0:
            self._raise_for_error(res)
        return res

    @staticmethod
    def _raise_for_error(res: NlmResult) -> None:
        # Normalize underscores->spaces so gRPC-style PERMISSION_DENIED / invalid_grant match.
        blob = f"{res.stderr}\n{res.stdout}".lower().replace("_", " ")
        detail = (res.stderr or res.stdout).strip()
        if any(sig in blob for sig in _AUTH_SIGNATURES) or _AUTH_CODE_RE.search(blob):
            raise NlmAuthError(detail=detail)
        if "not found" in blob or "notfound" in blob or _NOTFOUND_CODE_RE.search(blob):
            raise NlmNotFoundError(detail=detail)
        raise NlmExecError(detail=detail or f"exit {res.returncode}")

    # -- read-only operations --------------------------------------------------
    def version(self) -> str:
        return self._run(["--version"]).stdout.strip()

    def studio_status(self, notebook_id: str) -> list[dict[str, Any]]:
        """Return the studio artifact list for a notebook (id/type/status/custom_instructions)."""
        res = self._run(["studio", "status", notebook_id])
        return _parse_json_array(res.stdout)

    def download_quiz(self, notebook_id: str, artifact_id: str) -> dict[str, Any]:
        """Download a quiz artifact as JSON (Phase-2 quiz player feeds on this)."""
        res = self._run(
            ["download", "quiz", notebook_id, "--id", artifact_id, "-f", "json"]
        )
        return json.loads(res.stdout)


def _parse_json_array(text: str) -> list[dict]:
    """Parse a JSON array, tolerating a stray log line before the opening bracket."""
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        if start == -1:
            raise NlmExecError(
                "nlm studio status returned no JSON array.", detail=text[:200]
            )
        try:
            data = json.loads(text[start:])
        except json.JSONDecodeError as e:
            raise NlmExecError(
                "Could not parse nlm studio status JSON.", detail=str(e)
            ) from e
    return data if isinstance(data, list) else []
