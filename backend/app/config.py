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

        # Where the user's *generated* learning paths live (M8) — one JSON sidecar per topic,
        # ``<notebook_id>.json``, whose steps reference the topic's real artifacts (the path owns no
        # files of its own). Bundled example paths ship in the package and are always read too (see
        # ``app.paths.manifest``); this dir overlays/adds the user's own. Gitignored.
        self.paths_dir = Path(
            os.environ.get("PATHS_DIR", str(self.data_dir / "paths"))
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

        # FR2: the sweep runner POST /brief/sweep re-invokes — the same repo-root
        # ./sweep.sh that `make sweep` and the 06:00 launchd lane run. Overridable so
        # tests point it at a sandbox copy (never the real pipeline).
        self.sweep_script = Path(
            os.environ.get("SWEEP_SCRIPT", str(backend_dir.parent / "sweep.sh"))
        ).expanduser()

        # The news-mode category roster (M7): ordered slugs/titles + their Google News RSS
        # feed URLs, shared shape with the topic roster above. Overridable for tests.
        self.news_categories_file = Path(
            os.environ.get(
                "NEWS_CATEGORIES_FILE",
                str(backend_dir.parent / "sweeps" / "news_categories.json"),
            )
        ).expanduser()

        # PR5 sweep-trust gauge: the hand-appended accuracy re-grade log. The newest
        # `## YYYY-MM-DD` heading is served as last_graded on GET /brief/habit so an
        # ungraded stretch is visible on Today instead of assumed fine.
        self.trust_log = Path(
            os.environ.get(
                "TRUST_LOG", str(backend_dir.parent / "docs" / "sweep-trust-log.md")
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

        # Calibrated Doubt v0: the append-only graded-wager ledger behind the
        # 'Yesterday's calls' strip — backend data for the same reason as the chat
        # ledger: data/sweeps stays strictly read-only.
        self.brief_calibration_ledger = self.data_dir / "calibration.jsonl"

        # Overnight Chief of Staff v0: the draft-only proposal queue. Proposal rows are
        # appended by the nightly sweeps/actions_queue.py pass, approve/discard status
        # rows by the API — backend data for the same reason as the other ledgers.
        self.brief_overnight_ledger = self.data_dir / "overnight.jsonl"

        # Courses M5 authoring loop: the model for POST /courses/{slug}/lessons/{id}/regenerate
        # (same claude binary + subscription-lane guards as brief chat) and its usage ledger.
        self.course_regen_model = os.environ.get("COURSE_REGEN_MODEL", "sonnet")
        self.course_regen_ledger = self.data_dir / "course-regen.jsonl"

        # M8 learning paths: the formative bridge-check grader shares the M5 subscription lane +
        # guards; its usage rows land here (backend data, like the other ledgers).
        self.paths_grade_ledger = self.data_dir / "paths-grade.jsonl"

        # M8 the on-demand path Designer: composes a path over a topic's real artifacts on the same
        # subscription lane. Its own model knob (a bigger model composes better paths — the slice's
        # riskiest assumption) + its own usage ledger.
        self.paths_designer_model = os.environ.get("PATHS_DESIGNER_MODEL", "sonnet")
        self.paths_generate_ledger = self.data_dir / "paths-generate.jsonl"

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
        self.paths_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
