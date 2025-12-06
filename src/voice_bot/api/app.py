"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from .routers import customers, documents, sessions, voice_ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    settings.ensure_data_dirs()
    logging.info("Voice Bot API starting up...")
    yield
    logging.info("Voice Bot API shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Voice Bot API",
        description="Real-time Voice AI SaaS Platform API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(customers.router, prefix="/api/v1/customers", tags=["customers"])
    app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
    app.include_router(voice_ws.router, prefix="/api/v1/voice", tags=["voice"])

    # Serve static files
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": "0.1.0"}

    @app.get("/")
    async def root():
        """Serve the main chat interface."""
        static_dir = Path(__file__).parent.parent / "static"
        return FileResponse(str(static_dir / "cheap.html"))

    return app

