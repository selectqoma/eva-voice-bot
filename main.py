"""Voice Bot API Server - Main Entry Point."""

import uvicorn

from src.voice_bot.api import create_app
from src.voice_bot.config import get_settings


def main():
    """Run the Voice Bot API server."""
    settings = get_settings()

    app = create_app()

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
