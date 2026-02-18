"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from retrai.server.routes import runs, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from dotenv import load_dotenv

    load_dotenv()
    yield
    # Shutdown: close all active run buses
    from retrai.server.run_manager import run_manager

    for entry in run_manager.list_runs():
        if entry.status == "running":
            await entry.bus.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="retrAI",
        description="Self-solving AI agent loop",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(runs.router)
    app.include_router(ws.router)

    # Serve the built Vue frontend if it exists
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

    return app


app = create_app()
