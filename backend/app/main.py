"""App factory: CORS for the Vite origin (+ LAN), router includes, DB init on startup."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import catalog, episodes, health, quiz, topics
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
    app.include_router(catalog.router, prefix="/api", tags=["catalog"])
    app.include_router(topics.router, prefix="/api", tags=["topics"])
    app.include_router(episodes.router, prefix="/api", tags=["episodes"])
    app.include_router(quiz.router, prefix="/api", tags=["quiz"])

    @app.get("/api")
    def api_root() -> dict:
        return {"name": "Learning Hub API", "version": __version__}

    return app


app = create_app()
