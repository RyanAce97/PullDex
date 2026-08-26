import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    """Locate the project root .env file.

    In development (non-frozen), the file lives at the project root:
        config.py → backend/app/config.py
        parents[2] → PullDex/ (project root)

    When packaged with PyInstaller (frozen), there is no .env file on
    disk — all configuration comes from environment variables set by the
    Electron main process.  Return None so pydantic-settings skips it.
    """
    if getattr(sys, "frozen", False):
        return None

    env_path = Path(__file__).resolve().parents[2] / ".env"
    return env_path if env_path.is_file() else None


_ENV_FILE = _find_env_file()


class Settings(BaseSettings):
    """Application configuration.

    Values are read from environment variables or the .env file at the
    project root.  All fields have sensible defaults so the app runs
    out-of-the-box without any configuration.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # Application                                                          #
    # ------------------------------------------------------------------ #
    app_name: str = "PullDex"
    app_version: str = "0.3.0"
    debug: bool = False

    # ------------------------------------------------------------------ #
    # Desktop mode                                                         #
    # ------------------------------------------------------------------ #
    # Set by Electron to signal the backend is running in desktop mode.
    pulldex_desktop: bool = False

    # Path to the seed database bundled with the application.
    pulldex_seed_db: str = ""

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    # In development: relative to the backend/ working directory.
    # In desktop mode: set via DATABASE_URL env var by Electron.
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
