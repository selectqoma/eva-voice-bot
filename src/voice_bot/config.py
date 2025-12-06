"""Application configuration using Pydantic settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    deepgram_api_key: str
    openai_api_key: str
    cartesia_api_key: str
    daily_api_key: str
    groq_api_key: str = ""  # Optional: for cheap alternative stack
    elevenlabs_api_key: str = ""  # Optional: for premium TTS

    # OpenAI Configuration
    openai_model: str = "gpt-4o-mini"

    # Cartesia Configuration
    cartesia_voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091"

    # Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Data Storage
    customer_data_path: Path = Path("./customer_data")

    def ensure_data_dirs(self) -> None:
        """Ensure required data directories exist."""
        self.customer_data_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    settings = Settings()
    settings.ensure_data_dirs()
    return settings

