"""Service layer for data management: export, import, backup, restore.

Export/import use a portable JSON format with external identifiers.
Backup/restore use SQLite's built-in backup mechanism for safety.
"""

import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.config import settings
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.profile import Profile
from app.services.profile_service import get_active_profile, get_active_profile_id

# Current export format version
FORMAT_VERSION = 1


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_collection(session: Session) -> dict:
    """Export the active profile's collection as a portable JSON-serializable dict.

    The export contains:
    - format_version: for forward compatibility
    - profile settings (name, binder config)
    - collection entries using external identifiers (dex numbers, api_card_ids)

    Does NOT contain reference data (species, sets, cards databases).
    """
    profile = get_active_profile(session)
    profile_id = profile.id

    # Get all collection entries for this profile
    entries = session.exec(
        select(Collection).where(Collection.profile_id == profile_id)
    ).all()

    collection_data = []
    for entry in entries:
        if entry.card_id is not None:
            # Card-level entry — look up the api_card_id
            card = session.get(Card, entry.card_id)
            if card:
                collection_data.append({
                    "type": "card",
                    "api_card_id": card.api_card_id,
                    "quantity": entry.quantity,
                })
        elif entry.pokemon_species_id is not None:
            # Species-level entry — look up dex number and name
            species = session.get(PokemonSpecies, entry.pokemon_species_id)
            if species:
                collection_data.append({
                    "type": "species",
                    "national_dex_number": species.national_dex_number,
                    "species_name": species.name,
                })

    return {
        "format_version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "app_version": settings.app_version,
        "profile": {
            "name": profile.name,
            "binder_rows": profile.binder_rows,
            "binder_columns": profile.binder_columns,
            "binder_sort": profile.binder_sort,
        },
        "collection": collection_data,
    }


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class ImportResult:
    """Results of an import operation."""

    def __init__(self):
        self.imported_species: int = 0
        self.imported_cards: int = 0
        self.skipped_species: int = 0
        self.skipped_cards: int = 0
        self.warnings: list[str] = []
        self.pre_import_backup: dict | None = None

    def to_dict(self) -> dict:
        return {
            "imported_species": self.imported_species,
            "imported_cards": self.imported_cards,
            "skipped_species": self.skipped_species,
            "skipped_cards": self.skipped_cards,
            "warnings": self.warnings,
            "total_imported": self.imported_species + self.imported_cards,
            "total_skipped": self.skipped_species + self.skipped_cards,
            "has_backup": self.pre_import_backup is not None,
        }


def validate_import_data(data: dict) -> list[str]:
    """Validate import data structure. Returns a list of error messages."""
    errors = []

    if not isinstance(data, dict):
        errors.append("Import file must be a JSON object.")
        return errors

    if "format_version" not in data:
        errors.append("Missing 'format_version' field.")
    elif data["format_version"] != FORMAT_VERSION:
        errors.append(
            f"Unsupported format version {data['format_version']}. "
            f"Expected {FORMAT_VERSION}."
        )

    if "collection" not in data:
        errors.append("Missing 'collection' field.")
    elif not isinstance(data["collection"], list):
        errors.append("'collection' must be an array.")

    if "profile" not in data:
        errors.append("Missing 'profile' field.")
    elif not isinstance(data["profile"], dict):
        errors.append("'profile' must be an object.")

    return errors


def import_as_new_profile(session: Session, data: dict) -> ImportResult:
    """Import collection data as a new profile.

    Creates a new profile with the exported name (appending a suffix if
    the name already exists) and imports all valid collection entries.
    """
    result = ImportResult()
    profile_data = data.get("profile", {})

    # Determine profile name (avoid conflicts)
    base_name = profile_data.get("name", "Imported")
    name = base_name
    suffix = 1
    while session.exec(select(Profile).where(Profile.name == name)).first():
        suffix += 1
        name = f"{base_name} ({suffix})"

    # Create the profile
    profile = Profile(
        name=name,
        is_active=False,
        binder_rows=profile_data.get("binder_rows", 5),
        binder_columns=profile_data.get("binder_columns", 4),
        binder_sort=profile_data.get("binder_sort", "dex_number"),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)

    # Import collection entries
    _import_entries_fresh(session, profile.id, data.get("collection", []), result)  # type: ignore

    session.commit()
    return result


def import_replace_profile(session: Session, data: dict) -> ImportResult:
    """Import collection data, replacing the active profile's collection.

    The imported .pulldex becomes the profile's collection state:
    - Cards in the file replace existing quantities
    - Cards NOT in the file are removed from the collection
    - Species entries follow the same logic

    This is idempotent: importing the same file twice produces the same result.

    An automatic export of the current collection is included in the result
    so the user can recover if needed.
    """
    result = ImportResult()
    profile_id = get_active_profile_id(session)

    # Save current state for recovery (stored in result.pre_import_backup)
    result.pre_import_backup = export_collection(session)

    # Remove all existing collection entries for this profile
    existing_entries = session.exec(
        select(Collection).where(Collection.profile_id == profile_id)
    ).all()
    for entry in existing_entries:
        session.delete(entry)
    session.flush()

    # Import all entries from the file
    _import_entries_fresh(session, profile_id, data.get("collection", []), result)

    session.commit()
    return result


def import_merge_into_profile(session: Session, data: dict) -> ImportResult:
    """Import collection data, merging into the active profile.

    Merge semantics:
    - Cards in both collections: quantities are ADDED together
    - Cards only in the file: created with the file's quantity
    - Cards only in existing collection: unchanged
    - Species entries: added if missing, skipped if already present

    There is always only one collection row per (profile_id, card_id).
    """
    result = ImportResult()
    profile_id = get_active_profile_id(session)

    _import_entries_merge(session, profile_id, data.get("collection", []), result)

    session.commit()
    return result


def _import_entries_fresh(
    session: Session,
    profile_id: int,
    entries: list[dict],
    result: ImportResult,
) -> None:
    """Import entries into an empty profile (used by replace mode after clearing)."""
    for entry in entries:
        entry_type = entry.get("type")

        if entry_type == "species":
            dex_num = entry.get("national_dex_number")
            if dex_num is None:
                result.warnings.append(f"Species entry missing national_dex_number: {entry}")
                result.skipped_species += 1
                continue

            species = session.exec(
                select(PokemonSpecies).where(
                    PokemonSpecies.national_dex_number == dex_num
                )
            ).first()
            if species is None:
                result.warnings.append(
                    f"Species with dex #{dex_num} not found in local database."
                )
                result.skipped_species += 1
                continue

            session.add(Collection(
                profile_id=profile_id,
                pokemon_species_id=species.id,
                quantity=1,
            ))
            result.imported_species += 1

        elif entry_type == "card":
            api_card_id = entry.get("api_card_id")
            quantity = entry.get("quantity", 1)

            if not api_card_id:
                result.warnings.append(f"Card entry missing api_card_id: {entry}")
                result.skipped_cards += 1
                continue

            card = session.exec(
                select(Card).where(Card.api_card_id == api_card_id)
            ).first()
            if card is None:
                result.warnings.append(
                    f"Card '{api_card_id}' not found in local database."
                )
                result.skipped_cards += 1
                continue

            session.add(Collection(
                profile_id=profile_id,
                card_id=card.id,
                quantity=quantity,
            ))
            result.imported_cards += 1

        else:
            result.warnings.append(f"Unknown entry type: {entry_type}")


def _import_entries_merge(
    session: Session,
    profile_id: int,
    entries: list[dict],
    result: ImportResult,
) -> None:
    """Merge entries into an existing profile (additive quantities)."""
    for entry in entries:
        entry_type = entry.get("type")

        if entry_type == "species":
            dex_num = entry.get("national_dex_number")
            if dex_num is None:
                result.warnings.append(f"Species entry missing national_dex_number: {entry}")
                result.skipped_species += 1
                continue

            species = session.exec(
                select(PokemonSpecies).where(
                    PokemonSpecies.national_dex_number == dex_num
                )
            ).first()
            if species is None:
                result.warnings.append(
                    f"Species with dex #{dex_num} not found in local database."
                )
                result.skipped_species += 1
                continue

            # Check if already exists in this profile
            existing = session.exec(
                select(Collection).where(
                    Collection.profile_id == profile_id,
                    Collection.pokemon_species_id == species.id,
                    Collection.card_id.is_(None),  # type: ignore[union-attr]
                )
            ).first()

            if existing:
                result.skipped_species += 1
                continue

            session.add(Collection(
                profile_id=profile_id,
                pokemon_species_id=species.id,
                quantity=1,
            ))
            result.imported_species += 1

        elif entry_type == "card":
            api_card_id = entry.get("api_card_id")
            quantity = entry.get("quantity", 1)

            if not api_card_id:
                result.warnings.append(f"Card entry missing api_card_id: {entry}")
                result.skipped_cards += 1
                continue

            card = session.exec(
                select(Card).where(Card.api_card_id == api_card_id)
            ).first()
            if card is None:
                result.warnings.append(
                    f"Card '{api_card_id}' not found in local database."
                )
                result.skipped_cards += 1
                continue

            # Check if already exists in this profile
            existing = session.exec(
                select(Collection).where(
                    Collection.profile_id == profile_id,
                    Collection.card_id == card.id,
                )
            ).first()

            if existing:
                # Add imported quantity to existing
                existing.quantity += quantity
                session.add(existing)
                result.imported_cards += 1
                continue

            session.add(Collection(
                profile_id=profile_id,
                card_id=card.id,
                quantity=quantity,
            ))
            result.imported_cards += 1

        else:
            result.warnings.append(f"Unknown entry type: {entry_type}")


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def _get_db_path() -> Path:
    """Get the filesystem path of the SQLite database."""
    return Path(settings.database_url.removeprefix("sqlite:///"))


def create_backup(destination: str | None = None) -> str:
    """Create a safe backup of the current database using sqlite3.backup().

    This is safe to call while the application is running — SQLite handles
    locking internally.

    Args:
        destination: Optional path for the backup file. If None, creates
            a timestamped backup in the database directory.

    Returns:
        The path to the backup file.
    """
    db_path = _get_db_path()

    if destination:
        backup_path = Path(destination)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.parent / f"pulldex_backup_{timestamp}.db"

    # Ensure the destination directory exists
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    # Use sqlite3's backup API for a consistent point-in-time copy
    source_conn = sqlite3.connect(str(db_path))
    dest_conn = sqlite3.connect(str(backup_path))
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()

    return str(backup_path)


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def validate_backup(backup_path: str) -> list[str]:
    """Validate that a file is a valid PullDex SQLite database.

    Returns a list of error messages (empty = valid).
    """
    errors = []
    path = Path(backup_path)

    if not path.is_file():
        errors.append(f"File not found: {backup_path}")
        return errors

    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()

        # Check for expected tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        required_tables = {"pokemon_species", "sets", "cards", "collection"}
        missing = required_tables - tables
        if missing:
            errors.append(f"Missing required tables: {missing}")

        conn.close()
    except sqlite3.DatabaseError as e:
        errors.append(f"Not a valid SQLite database: {e}")

    return errors


def restore_backup(backup_path: str) -> dict:
    """Restore a database from a backup file.

    Safety steps:
    1. Validate the backup file
    2. Create an automatic backup of the current database
    3. Replace the current database with the backup

    Returns a dict with status and pre-restore backup path.

    The caller should restart the application after a successful restore
    to reinitialize the database connection.
    """
    errors = validate_backup(backup_path)
    if errors:
        return {
            "success": False,
            "errors": errors,
            "pre_restore_backup": None,
        }

    db_path = _get_db_path()

    # Step 1: Create automatic pre-restore backup
    pre_restore_path = str(db_path.parent / "pulldex_pre_restore_backup.db")
    try:
        create_backup(pre_restore_path)
    except Exception as e:
        return {
            "success": False,
            "errors": [f"Failed to create pre-restore backup: {e}"],
            "pre_restore_backup": None,
        }

    # Step 2: Replace the current database
    try:
        shutil.copy2(backup_path, str(db_path))
    except Exception as e:
        return {
            "success": False,
            "errors": [f"Failed to restore database: {e}"],
            "pre_restore_backup": pre_restore_path,
        }

    return {
        "success": True,
        "errors": [],
        "pre_restore_backup": pre_restore_path,
        "message": "Database restored successfully. Please restart PullDex.",
    }
