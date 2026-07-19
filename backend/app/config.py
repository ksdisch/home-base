"""Central configuration. Paths are overridable via env for tests and LAN deploys."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

DEFAULT_NOTEBOOKLM_ROOT = Path.home() / "Projects" / "NotebookLMs"


class Settings:
    def __init__(self) -> None:
        backend_dir = Path(__file__).resolve().parent.parent  # .../backend

        self.notebooklm_root = Path(
            os.environ.get("NOTEBOOKLM_ROOT", str(DEFAULT_NOTEBOOKLM_ROOT))
        ).expanduser()

        self.data_dir = Path(
            os.environ.get("LEARNING_HUB_DATA", str(backend_dir / "data"))
        ).expanduser()
        self.db_path = self.data_dir / "learning-hub.sqlite"
        self.cache_dir = self.data_dir / "cache"

        # Where the user's *generated* courses live (a course = a sidecar dir: course.json +
        # material files). Bundled example courses ship in the package and are always read too
        # (see ``app.courses.manifest``); this dir overlays/adds the user's own. Gitignored.
        self.courses_dir = Path(
            os.environ.get("COURSES_DIR", str(self.data_dir / "courses"))
        ).expanduser()

        # Where the sweep runner (sweep.sh) drops daily briefs: <repo>/data/sweeps/<date>/.
        # Read-only for the backend (GET /api/brief); overridable for tests.
        self.sweeps_dir = Path(
            os.environ.get("SWEEPS_DIR", str(backend_dir.parent / "data" / "sweeps"))
        ).expanduser()

        # The topic roster (M2): ordered slugs/titles + manual pause flags, shared by
        # sweep.sh (which topics to run) and GET /api/brief (titles + display order).
        self.roster_file = Path(
            os.environ.get("ROSTER_FILE", str(backend_dir.parent / "sweeps" / "topics.json"))
        ).expanduser()

        # The news-mode category roster (M7): ordered slugs/titles + their Google News RSS
        # feed URLs, shared shape with the topic roster above. Overridable for tests.
        self.news_categories_file = Path(
            os.environ.get(
                "NEWS_CATEGORIES_FILE",
                str(backend_dir.parent / "sweeps" / "news_categories.json"),
            )
        ).expanduser()

        # The nlm binary (overridable so tests never touch the real CLI).
        self.nlm_bin = os.environ.get("NLM_BIN", "nlm")

        # M5 chat-with-the-brief: the claude CLI + model for POST /api/brief/chat
        # (overridable so tests inject fakes and other machines aren't hardcoded).
        self.claude_bin = os.environ.get("CLAUDE_BIN", "claude")
        self.brief_chat_model = os.environ.get("BRIEF_CHAT_MODEL", "sonnet")
        # Chat usage/cost rows live under backend data on purpose — the backend stays
        # strictly read-only over data/sweeps.
        self.brief_chat_ledger = self.data_dir / "brief-chat.jsonl"

        # Courses M5 authoring loop: the model for POST /courses/{slug}/lessons/{id}/regenerate
        # (same claude binary + subscription-lane guards as brief chat) and its usage ledger.
        self.course_regen_model = os.environ.get("COURSE_REGEN_MODEL", "sonnet")
        self.course_regen_ledger = self.data_dir / "course-regen.jsonl"

        # Vite dev origin(s). CORS also allows private-LAN origins via regex (see main.py).
        self.cors_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

        # The built frontend (M6): when this dir exists, main.py serves it on the same port
        # (one-port prod path); when absent — every dev flow — behavior is unchanged.
        self.frontend_dist = Path(
            os.environ.get("FRONTEND_DIST", str(backend_dir.parent / "frontend" / "dist"))
        ).expanduser()

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.courses_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
