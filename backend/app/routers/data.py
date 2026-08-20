"""Data management routes: export, import, backup, restore."""

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import get_session
from app.services.data_service import (
    create_backup,
    export_collection,
    import_as_new_profile,
    import_merge_into_profile,
    import_replace_profile,
    restore_backup,
    validate_backup,
    validate_import_data,
)

router = APIRouter(prefix="/data", tags=["Data Management"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ExportResponse(BaseModel):
    """The exported collection data."""
    format_version: int
    exported_at: str
    app_version: str
    profile: dict
    collection: list[dict]


class ImportRequest(BaseModel):
    """Request body for JSON import."""
    data: dict
    mode: str = "new_profile"  # "new_profile", "replace", or "merge"


class ImportResponse(BaseModel):
    """Result of an import operation."""
    imported_species: int
    imported_cards: int
    skipped_species: int
    skipped_cards: int
    warnings: list[str]
    total_imported: int
    total_skipped: int
    has_backup: bool = False


class BackupResponse(BaseModel):
    """Result of a backup operation."""
    success: bool
    backup_path: str | None = None
    error: str | None = None


class RestoreRequest(BaseModel):
    """Request body for restore."""
    backup_path: str


class RestoreResponse(BaseModel):
    """Result of a restore operation."""
    success: bool
    errors: list[str]
    pre_restore_backup: str | None = None
    message: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/export", response_model=ExportResponse, summary="Export collection")
def export_data(session=Depends(get_session)):
    """Export the active profile's collection as portable JSON.

    The export contains profile settings and collection entries using
    external identifiers (dex numbers, API card IDs). It does NOT contain
    the reference database.

    Save the response body as a .pulldex file.
    """
    return export_collection(session)


@router.post("/import", response_model=ImportResponse, summary="Import collection")
def import_data(body: ImportRequest, session=Depends(get_session)):
    """Import collection data from a previously exported .pulldex file.

    Modes:
    - "new_profile": Creates a new profile with the imported data.
    - "replace": Replaces the active profile's collection with the imported data.
      Creates an automatic backup before replacing. Idempotent.
    - "merge": Merges into the active profile. Existing card quantities are
      added together. Species entries are added if missing.

    Invalid references are reported but non-blocking.
    """
    # Validate the data
    errors = validate_import_data(body.data)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    if body.mode == "replace":
        result = import_replace_profile(session, body.data)
    elif body.mode == "merge":
        result = import_merge_into_profile(session, body.data)
    else:
        result = import_as_new_profile(session, body.data)

    return result.to_dict()


@router.post("/backup", response_model=BackupResponse, summary="Create backup")
def create_data_backup(session=Depends(get_session)):
    """Create a safe backup of the current PullDex database.

    Uses SQLite's built-in backup mechanism, which is safe while the
    application is running.

    Returns the path where the backup was saved.
    """
    try:
        backup_path = create_backup()
        return {"success": True, "backup_path": backup_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/restore", response_model=RestoreResponse, summary="Restore backup")
def restore_data_backup(body: RestoreRequest, session=Depends(get_session)):
    """Restore the database from a backup file.

    Safety:
    1. Validates the backup file
    2. Creates an automatic backup of the current state
    3. Replaces the database

    After a successful restore, the application should be restarted.
    """
    result = restore_backup(body.backup_path)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    return result
