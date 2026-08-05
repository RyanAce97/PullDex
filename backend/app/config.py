from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration.

    Values are read from environment variables or a .env file located
    at the project root (one directory above backend/).  All fields have
    sensible defaults so the app runs out-of-the-box without any configuration.
    """

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # Application                                                          #
    # ------------------------------------------------------------------ #
    app_name: str = "PullDex"
    app_version: str = "0.1.0"
    debug: bool = False

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    # Path is relative to the backend/ working directory.
    database_url: str = "sqlite:///../database/pulldex.db"

    # ------------------------------------------------------------------ #
    # External APIs                                                        #
    # ------------------------------------------------------------------ #
    pokemon_tcg_api_key: str | None = None

    # ------------------------------------------------------------------ #
    # CORS                                                                 #
    # ------------------------------------------------------------------ #
    allowed_origins: list[str] = ["http://localhost:5173"]


# Single shared instance imported everywhere else.
settings = Settings()
