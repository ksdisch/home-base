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

        # The nlm binary (overridable so tests never touch the real CLI).
        self.nlm_bin = os.environ.get("NLM_BIN", "nlm")

        # Vite dev origin(s). CORS also allows private-LAN origins via regex (see main.py).
        self.cors_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
