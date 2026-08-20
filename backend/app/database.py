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

    # Known card_id → species_name mappings for cards missing dex numbers.
    # These are Pokémon cards where the TCG API omits nationalPokedexNumbers.
    from app.services.importers.card_importer import (
        _EXCLUDED_CARD_NAMES,
        _FORM_MAPPINGS,
        _TCG_SUFFIXES,
        normalize_card_name,
    )

    # The known affected card IDs and their Pokémon names (from investigation).
    _KNOWN_CARDS: dict[str, str] = {
        "sv7-107": "Archaludon", "sv7-155": "Archaludon",
        "sv6-112": "Cornerstone Mask Ogerpon ex", "sv6-199": "Cornerstone Mask Ogerpon ex",
        "sv6-215": "Cornerstone Mask Ogerpon ex",
        "sv6-18": "Dipplin", "sv6-127": "Dipplin", "sv6-170": "Dipplin", "sv7-13": "Dipplin",
        "sv6-96": "Fezandipiti", "sv6pt5-73": "Fezandipiti",
        "sv6pt5-38": "Fezandipiti ex", "sv6pt5-84": "Fezandipiti ex", "sv6pt5-92": "Fezandipiti ex",
        "sv8pt5-43": "Flutter Mane",
        "svp-151": "Gouging Fire", "sv5-38": "Gouging Fire ex", "sv5-188": "Gouging Fire ex",
        "sv5-204": "Gouging Fire ex", "sv5-214": "Gouging Fire ex", "svp-144": "Gouging Fire ex",
        "sv8pt5-55": "Great Tusk",
        "sv6-40": "Hearthflame Mask Ogerpon ex", "sv6-192": "Hearthflame Mask Ogerpon ex",
        "sv6-212": "Hearthflame Mask Ogerpon ex",
        "sv7-14": "Hydrapple ex", "sv7-156": "Hydrapple ex", "sv7-167": "Hydrapple ex",
        "sv7-71": "Iron Boulder", "sv8pt5-46": "Iron Boulder",
        "sv5-99": "Iron Boulder ex", "sv5-192": "Iron Boulder ex", "sv5-207": "Iron Boulder ex",
        "sv5-217": "Iron Boulder ex", "svp-147": "Iron Boulder ex",
        "sv5-81": "Iron Crown ex", "sv5-191": "Iron Crown ex", "sv5-206": "Iron Crown ex",
        "sv5-216": "Iron Crown ex", "svp-146": "Iron Crown ex", "sv8pt5-158": "Iron Crown ex",
        "sv8pt5-31": "Iron Hands ex", "sv8pt5-154": "Iron Hands ex",
        "sv8pt5-176": "Iron Leaves ex",
        "sv6pt5-9": "Iron Moth",
        "sv8pt5-32": "Iron Thorns ex",
        "sv8pt5-157": "Iron Valiant ex",
        "sv6-95": "Munkidori", "sv6pt5-72": "Munkidori",
        "sv6pt5-37": "Munkidori ex", "sv6pt5-83": "Munkidori ex", "sv6pt5-91": "Munkidori ex",
        "sv6-111": "Okidogi", "sv6pt5-74": "Okidogi", "sv8pt5-57": "Okidogi", "me2pt5-122": "Okidogi",
        "sv6pt5-36": "Okidogi ex", "sv6pt5-82": "Okidogi ex", "sv6pt5-90": "Okidogi ex",
        "svp-149": "Pecharunt", "sv6pt5-39": "Pecharunt ex", "sv6pt5-85": "Pecharunt ex",
        "sv6pt5-93": "Pecharunt ex", "sv6pt5-95": "Pecharunt ex",
        "sv6-20": "Poltchageist", "sv6-21": "Poltchageist", "sv6-171": "Poltchageist",
        "sv7-111": "Raging Bolt", "sv5-123": "Raging Bolt ex", "sv5-196": "Raging Bolt ex",
        "sv5-208": "Raging Bolt ex", "sv5-218": "Raging Bolt ex", "svp-145": "Raging Bolt ex",
        "sv8pt5-166": "Raging Bolt ex",
        "sv8pt5-65": "Roaring Moon", "sv8pt5-162": "Roaring Moon ex",
        "sv8pt5-56": "Sandy Shocks ex", "sv8pt5-159": "Sandy Shocks ex",
        "sv8pt5-42": "Scream Tail",
        "sv6-22": "Sinistcha", "sv6-23": "Sinistcha ex", "sv6-189": "Sinistcha ex",
        "sv6-210": "Sinistcha ex",
        "sv6pt5-26": "Slither Wing",
        "sv6pt5-6": "Tapu Bulu", "sv6pt5-65": "Tapu Bulu",
        "sv6-24": "Teal Mask Ogerpon", "sv6-25": "Teal Mask Ogerpon ex",
        "sv6-190": "Teal Mask Ogerpon ex", "sv6-211": "Teal Mask Ogerpon ex",
        "sv6-221": "Teal Mask Ogerpon ex",
        "sv7-128": "Terapagos ex", "sv7-170": "Terapagos ex", "sv7-173": "Terapagos ex",
        "sv8pt5-178": "Walking Wake ex",
        "sv6-64": "Wellspring Mask Ogerpon ex", "sv6-194": "Wellspring Mask Ogerpon ex",
        "sv6-213": "Wellspring Mask Ogerpon ex",
    }

    updated = 0
    for api_card_id, card_name in _KNOWN_CARDS.items():
        # Resolve species name from card name
        normalized = normalize_card_name(card_name)
        normalized_spaces = normalized.replace("-", " ")
        species_name = _FORM_MAPPINGS.get(normalized_spaces, normalized)

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
