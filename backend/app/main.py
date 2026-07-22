"""App factory: CORS for the Vite origin (+ LAN), router includes, DB init on startup.

When ``frontend/dist`` exists (built via ``make build``), the app also serves it on the
same port — the M6 one-port prod path. Absent a dist, behavior is exactly the dev setup.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import (
    brief,
    catalog,
    courses,
    custom_topics,
    episodes,
    health,
    news,
    paths,
    progress,
    quiz,
    reflections,
    review,
    study_plan,
    topics,
)
from .config import get_settings
from .store import init_db

# Allow localhost + private-LAN origins (so a phone on the same network can reach the hub).
_LAN_ORIGIN_REGEX = (
    r"^http://(localhost|127\.0\.0\.1|(192\.168|10\.\d{1,3})\.\d{1,3}\.\d{1,3})(:\d+)?$"
)


def create_app() -> FastAPI:
    settings = get_settings()
    settings.ensure_dirs()
    init_db()

    app = FastAPI(title="Learning Hub", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=_LAN_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(brief.router, prefix="/api", tags=["brief"])
    app.include_router(catalog.router, prefix="/api", tags=["catalog"])
    app.include_router(topics.router, prefix="/api", tags=["topics"])
    app.include_router(episodes.router, prefix="/api", tags=["episodes"])
    app.include_router(quiz.router, prefix="/api", tags=["quiz"])
    app.include_router(progress.router, prefix="/api", tags=["progress"])
    app.include_router(review.router, prefix="/api", tags=["review"])
    app.include_router(study_plan.router, prefix="/api", tags=["study-plan"])
    app.include_router(reflections.router, prefix="/api", tags=["reflections"])
    app.include_router(custom_topics.router, prefix="/api", tags=["custom-topics"])
    app.include_router(courses.router, prefix="/api", tags=["courses"])
    app.include_router(news.router, prefix="/api", tags=["news"])
    app.include_router(paths.router, prefix="/api", tags=["paths"])

    @app.get("/api")
    def api_root() -> dict:
        return {"name": "Learning Hub API", "version": __version__}

    _mount_frontend(app, settings.frontend_dist)

    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built SPA: /assets statics, root PWA files, catch-all → index.html.

    Registered after every /api route, so real API paths always win; unknown /api/*
    paths still 404 as JSON instead of falling through to the SPA shell.

    The dist check happens per request (bug #8): install-server.sh and the README
    promise 'run make build' with no restart, and the KeepAlive agent never restarts on
    its own — so the catch-all registers unconditionally and 404s until index.html
    exists. The /assets StaticFiles mount still needs the dir at startup; before it
    exists, hashed assets are served by the catch-all's file branch instead.
    """
    dist = dist.resolve()
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        if not (dist / "index.html").is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (dist / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(dist):
                return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
