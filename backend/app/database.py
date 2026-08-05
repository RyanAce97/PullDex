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

def create_db_and_tables() -> None:
    """Create the SQLite database file and all registered tables.

    Called once at application startup.  When Alembic migrations are in
    use this function is kept for initial bootstrapping only; Alembic
    handles subsequent schema changes.
    """
    # Ensure the parent directory exists so SQLite can create the file.
    db_path = settings.database_url.removeprefix("sqlite:///")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

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
