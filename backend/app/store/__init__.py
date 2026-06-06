"""Hub-owned SQLite store. The ONLY place user progress lives — never the sidecars."""

from .db import (
    add_custom_topic,
    connect,
    get_custom_topic,
    get_episode_progress,
    init_db,
    list_custom_topics,
    record_attempt,
    save_reflection,
    set_episode_listened,
    update_custom_topic,
)

__all__ = [
    "connect",
    "init_db",
    "get_episode_progress",
    "set_episode_listened",
    "save_reflection",
    "record_attempt",
    "add_custom_topic",
    "list_custom_topics",
    "get_custom_topic",
    "update_custom_topic",
]
