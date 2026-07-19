"""FastAPI dependencies (so tests can override the nlm/chat clients + settings)."""

from __future__ import annotations

from .chat import BriefChatClient
from .config import Settings, get_settings
from .courses.regen import CourseRegenClient
from .news import NewsFetcher
from .nlm import NlmClient


def get_nlm_client() -> NlmClient:
    return NlmClient()


def get_news_fetcher() -> NewsFetcher:
    return NewsFetcher()


def get_brief_chat_client() -> BriefChatClient:
    return BriefChatClient()


def get_course_regen_client() -> CourseRegenClient:
    return CourseRegenClient()


def get_app_settings() -> Settings:
    return get_settings()
