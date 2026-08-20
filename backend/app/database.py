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

    # Step 3: Repair card-species mappings for cards missing nationalPokedexNumbers.
    _repair_card_species_mapping()


def _repair_card_species_mapping() -> None:
    """Fix cards that are missing pokemon_species_id due to the Pokémon TCG API
    not providing nationalPokedexNumbers for some cards.

    This runs automatically after migrations on every startup. It is:
    - Idempotent: safe to run repeatedly (only updates NULL → valid ID)
    - Non-destructive: never modifies collection entries, quantities,
      profiles, or binder selections
    - Offline: uses only local data (no API calls)
    - Fast: simple UPDATE with a known set of card IDs
    - Self-contained: no external imports that require httpx/network libs

    Only touches cards.pokemon_species_id where it is currently NULL and
    the card is in the known affected list.
    """
    import sqlite3

    db_path = _get_db_path()
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Build species name → id lookup
    cur.execute("SELECT id, name FROM pokemon_species")
    species_id_by_name: dict[str, int] = {row[1]: row[0] for row in cur.fetchall()}

    # Known card api_card_id → species_name mappings.
    # These Pokémon cards have no nationalPokedexNumbers in the TCG API.
    _CARD_TO_SPECIES: dict[str, str] = {
        "sv7-107": "archaludon", "sv7-155": "archaludon",
        "sv6-112": "ogerpon", "sv6-199": "ogerpon", "sv6-215": "ogerpon",
        "sv6-18": "dipplin", "sv6-127": "dipplin", "sv6-170": "dipplin", "sv7-13": "dipplin",
        "sv6-96": "fezandipiti", "sv6pt5-73": "fezandipiti",
        "sv6pt5-38": "fezandipiti", "sv6pt5-84": "fezandipiti", "sv6pt5-92": "fezandipiti",
        "sv8pt5-43": "flutter-mane",
        "svp-151": "gouging-fire", "sv5-38": "gouging-fire", "sv5-188": "gouging-fire",
        "sv5-204": "gouging-fire", "sv5-214": "gouging-fire", "svp-144": "gouging-fire",
        "sv8pt5-55": "great-tusk",
        "sv6-40": "ogerpon", "sv6-192": "ogerpon", "sv6-212": "ogerpon",
        "sv7-14": "hydrapple", "sv7-156": "hydrapple", "sv7-167": "hydrapple",
        "sv7-71": "iron-boulder", "sv8pt5-46": "iron-boulder",
        "sv5-99": "iron-boulder", "sv5-192": "iron-boulder", "sv5-207": "iron-boulder",
        "sv5-217": "iron-boulder", "svp-147": "iron-boulder",
        "sv5-81": "iron-crown", "sv5-191": "iron-crown", "sv5-206": "iron-crown",
        "sv5-216": "iron-crown", "svp-146": "iron-crown", "sv8pt5-158": "iron-crown",
        "sv8pt5-31": "iron-hands", "sv8pt5-154": "iron-hands",
        "sv8pt5-176": "iron-leaves",
        "sv6pt5-9": "iron-moth",
        "sv8pt5-32": "iron-thorns",
        "sv8pt5-157": "iron-valiant",
        "sv6-95": "munkidori", "sv6pt5-72": "munkidori",
        "sv6pt5-37": "munkidori", "sv6pt5-83": "munkidori", "sv6pt5-91": "munkidori",
        "sv6-111": "okidogi", "sv6pt5-74": "okidogi", "sv8pt5-57": "okidogi", "me2pt5-122": "okidogi",
        "sv6pt5-36": "okidogi", "sv6pt5-82": "okidogi", "sv6pt5-90": "okidogi",
        "svp-149": "pecharunt", "sv6pt5-39": "pecharunt", "sv6pt5-85": "pecharunt",
        "sv6pt5-93": "pecharunt", "sv6pt5-95": "pecharunt",
        "sv6-20": "poltchageist", "sv6-21": "poltchageist", "sv6-171": "poltchageist",
        "sv7-111": "raging-bolt", "sv5-123": "raging-bolt", "sv5-196": "raging-bolt",
        "sv5-208": "raging-bolt", "sv5-218": "raging-bolt", "svp-145": "raging-bolt",
        "sv8pt5-166": "raging-bolt",
        "sv8pt5-65": "roaring-moon", "sv8pt5-162": "roaring-moon",
        "sv8pt5-56": "sandy-shocks", "sv8pt5-159": "sandy-shocks",
        "sv8pt5-42": "scream-tail",
        "sv6-22": "sinistcha", "sv6-23": "sinistcha", "sv6-189": "sinistcha",
        "sv6-210": "sinistcha",
        "sv6pt5-26": "slither-wing",
        "sv6pt5-6": "tapu-bulu", "sv6pt5-65": "tapu-bulu",
        "sv6-24": "ogerpon", "sv6-25": "ogerpon",
        "sv6-190": "ogerpon", "sv6-211": "ogerpon", "sv6-221": "ogerpon",
        "sv7-128": "terapagos", "sv7-170": "terapagos", "sv7-173": "terapagos",
        "sv8pt5-178": "walking-wake",
        "sv6-64": "ogerpon", "sv6-194": "ogerpon", "sv6-213": "ogerpon",
    }

    updated = 0
    for api_card_id, species_name in _CARD_TO_SPECIES.items():
        if species_name not in species_id_by_name:
            continue

        species_id = species_id_by_name[species_name]

        # Only update if currently NULL (idempotent)
        cur.execute(
            "UPDATE cards SET pokemon_species_id = ? "
            "WHERE api_card_id = ? AND pokemon_species_id IS NULL",
            (species_id, api_card_id),
        )
        updated += cur.rowcount

    if updated > 0:
        conn.commit()
        print(f"Card species mapping: repaired {updated} cards.")
    else:
        print("Card species mapping: all cards already linked.")

    conn.close()


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
