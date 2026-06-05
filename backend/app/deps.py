"""FastAPI dependencies (so tests can override the nlm client + settings)."""

from __future__ import annotations

from .config import Settings, get_settings
from .nlm import NlmClient


def get_nlm_client() -> NlmClient:
    return NlmClient()


def get_app_settings() -> Settings:
    return get_settings()
