"""Profile management routes for the PullDex API."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.database import get_session
from app.services.profile_service import (
    create_profile,
    delete_profile,
    get_active_profile,
    get_profile_by_id,
    list_profiles,
    rename_profile,
    switch_active_profile,
    update_profile_settings,
)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProfileRead(BaseModel):
    """Public representation of a profile."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    created_at: datetime
    binder_rows: int
    binder_columns: int
    binder_sort: str


class ProfileCreate(BaseModel):
    """Request body for creating a profile."""
    name: str


class ProfileRename(BaseModel):
    """Request body for renaming a profile."""
    name: str


class ProfileSettingsUpdate(BaseModel):
    """Request body for updating profile settings."""
    binder_rows: int | None = None
    binder_columns: int | None = None
    binder_sort: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ProfileRead], summary="List all profiles")
def list_all_profiles(session=Depends(get_session)):
    """Return all profiles ordered by creation date."""
    return list_profiles(session)


@router.get("/active", response_model=ProfileRead, summary="Get active profile")
def get_current_profile(session=Depends(get_session)):
    """Return the currently active profile."""
    return get_active_profile(session)


@router.post("", response_model=ProfileRead, status_code=201, summary="Create a profile")
def create_new_profile(body: ProfileCreate, session=Depends(get_session)):
    """Create a new local profile.

    The new profile is not automatically activated.
    """
    try:
        return create_profile(session, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/{profile_id}/activate", response_model=ProfileRead, summary="Switch active profile")
def activate_profile(profile_id: int, session=Depends(get_session)):
    """Make the specified profile the active one.

    All collection, progress, and recommendation queries will now use
    this profile's data.
    """
    try:
        return switch_active_profile(session, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{profile_id}", response_model=ProfileRead, summary="Update profile")
def update_profile(profile_id: int, body: ProfileSettingsUpdate, session=Depends(get_session)):
    """Update a profile's binder settings.

    Only provided fields are updated.
    """
    try:
        return update_profile_settings(
            session,
            profile_id,
            binder_rows=body.binder_rows,
            binder_columns=body.binder_columns,
            binder_sort=body.binder_sort,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{profile_id}/rename", response_model=ProfileRead, summary="Rename profile")
def rename_existing_profile(profile_id: int, body: ProfileRename, session=Depends(get_session)):
    """Rename an existing profile."""
    try:
        return rename_profile(session, profile_id, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{profile_id}", status_code=204, summary="Delete a profile")
def delete_existing_profile(profile_id: int, session=Depends(get_session)):
    """Delete a profile and all its collection data.

    Cannot delete the last remaining profile.
    """
    try:
        delete_profile(session, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return None
