from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to the project root .env file, resolved relative to this
# file's location so it works regardless of the current working directory.
# config.py lives at  backend/app/config.py
# parents[0] = backend/app
# parents[1] = backend
# parents[2] = PullDex  (project root)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application configuration.

    Values are read from environment variables or the .env file at the
    project root.  All fields have sensible defaults so the app runs
    out-of-the-box without any configuration.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
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
