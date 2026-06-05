"""Typed errors for the nlm boundary. The API layer maps these to friendly responses."""

from __future__ import annotations

from typing import Optional


class NlmError(Exception):
    """Base for every nlm-boundary failure. ``user_message`` is safe to show in the UI."""

    user_message = "NotebookLM access failed."

    def __init__(self, message: Optional[str] = None, *, detail: str = "") -> None:
        super().__init__(message or self.user_message)
        self.detail = detail

    @property
    def message(self) -> str:
        return str(self)


class NlmAuthError(NlmError):
    user_message = (
        "NotebookLM needs you to sign in again. Run `nlm login` in a terminal, then refresh."
    )


class NlmNotFoundError(NlmError):
    user_message = "That NotebookLM notebook or artifact was not found."


class NlmExecError(NlmError):
    user_message = "The nlm command failed. Make sure nlm is installed and on your PATH."


class DisallowedCommandError(NlmError):
    """Raised before any subprocess starts when a non-read-only command is attempted."""

    user_message = "Blocked a NotebookLM command that is not read-only."
