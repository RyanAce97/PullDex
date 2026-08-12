import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

from sqlmodel import SQLModel, create_engine, Session

from app.config import settings


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# For SQLite we pass check_same_thread=False so FastAPI's async handlers
# (which may run on different threads) can reuse the same connection safely.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,  # logs SQL statements when debug=True
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_path() -> Path:
    """Extract the filesystem path from the SQLite database URL."""
    return Path(settings.database_url.removeprefix("sqlite:///"))


def _get_alembic_dir() -> Path:
    """Locate the Alembic directory.

    When running from a PyInstaller bundle, alembic scripts are inside
    the bundle at ``{_MEIPASS}/alembic/``.  In development, they are at
    ``backend/alembic/`` (relative to the working directory).
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "alembic"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1] / "alembic"


def _seed_database_if_needed() -> None:
    """Copy the bundled seed database to the user-data location if no
    database file exists yet.

    The seed database contains all reference data (species, sets, cards)
    with an empty collection, already stamped at the current Alembic head.
    """
    db_path = _get_db_path()
    if db_path.exists():
        return  # Database already exists — nothing to do.

    seed_path = settings.pulldex_seed_db
    if not seed_path:
        return  # No seed configured — let create_db_and_tables handle it.

    seed_file = Path(seed_path)
    if not seed_file.is_file():
        print(f"WARNING: Seed database not found at {seed_file}")
        return

    # Ensure the target directory exists.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy seed → user location.
    shutil.copy2(seed_file, db_path)
    print(f"Initialised database from seed: {seed_file} -> {db_path}")


def run_migrations() -> None:
    """Run Alembic migrations programmatically (desktop mode).

    Called during application startup when PULLDEX_DESKTOP=true.
    Seeds the database first if it doesn't exist, then applies any
    pending migrations.

    If migration fails, the error is logged and the application will
    not start (the exception propagates up to the lifespan handler).
    """
    # Step 1: Seed the database if this is a first run.
    _seed_database_if_needed()

    db_path = _get_db_path()
    if not db_path.exists():
        # No database and no seed — create_db_and_tables will handle it.
        return

    # Step 2: Run Alembic upgrade head.
    alembic_dir = _get_alembic_dir()
    alembic_ini = alembic_dir.parent / "alembic.ini"

    # Use Alembic's command API for programmatic migrations.
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(alembic_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)

    try:
        command.upgrade(alembic_cfg, "head")
        print("Database migrations applied successfully.")
    except Exception as e:
        print(f"ERROR: Database migration failed: {e}")
        raise


def create_db_and_tables() -> None:
    """Create the SQLite database file and all registered tables.

    Called once at application startup.  When Alembic migrations are in
    use this function is kept for initial bootstrapping only; Alembic
    handles subsequent schema changes.
    """
    # Ensure the parent directory exists so SQLite can create the file.
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session


@contextmanager
def get_session_context():
    """Context manager that yields a database session for use in scripts.

    Use this outside of FastAPI (e.g. importer scripts, CLI tools) where
    the dependency-injection system is not available.

    Example::

        from app.database import get_session_context

        with get_session_context() as session:
            session.add(some_record)
            session.commit()
    """
    with Session(engine) as session:
        yield session
