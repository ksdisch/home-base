"""Hub-owned SQLite store. The ONLY place user progress lives — never the sidecars."""

from .db import (
    connect,
    get_episode_progress,
    init_db,
    record_attempt,
    save_reflection,
    set_episode_listened,
)

__all__ = [
    "connect",
    "init_db",
    "get_episode_progress",
    "set_episode_listened",
    "save_reflection",
    "record_attempt",
]
