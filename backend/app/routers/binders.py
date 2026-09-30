"""Multi-binder routes for the PullDex API.

Exposes management of a profile's binders and, for FREE_PLACEMENT binders,
explicit card placements. All operations are scoped to the active profile;
a binder or placement belonging to another profile is reported as 404 so
isolation cannot be probed.

The legacy ``/binder`` routes (see ``routers/binder.py``) remain for
backwards compatibility and operate on the active profile's default POKEDEX
binder.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.database import get_session
from app.services import binder_service as svc
from app.services.profile_service import get_active_profile_id

router = APIRouter(prefix="/binders", tags=["Binders"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BinderRead(BaseModel):
    """Public representation of a binder."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
    name: str
    binder_type: str
    rows: int
    columns: int
    sort_order: str
    is_default: bool
    created_at: datetime


class BinderCreate(BaseModel):
    name: str
    binder_type: str
    rows: int = 5
    columns: int = 4
    sort_order: str = "dex_number"


class BinderUpdate(BaseModel):
    name: str | None = None
    rows: int | None = None
    columns: int | None = None
    sort_order: str | None = None
    # Accepted but immutable: sending a different value returns 400.
    binder_type: str | None = None


class PlacementCreate(BaseModel):
    card_id: int
    page: int
    slot: int


class PlacementMove(BaseModel):
    page: int
    slot: int


class PlacementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    binder_id: int
    card_id: int
    page: int
    slot: int


# --- Page schemas (POKEDEX) -------------------------------------------------

class PokedexBinderCardInfo(BaseModel):
    id: int
    api_card_id: str | None
    card_number: str | None
    rarity: str | None
    image_url: str | None
    set_name: str | None
    set_code: str | None
    quantity: int


class PokedexBinderSlot(BaseModel):
    dex_number: int | None
    species_name: str | None
    species_id: int | None
    owned: bool
    has_card: bool
    card: PokedexBinderCardInfo | None
    total_cards: int


class PokedexBinderPage(BaseModel):
    binder_type: str = "POKEDEX"
    page: int
    page_size: int
    total_species: int
    total_pages: int
    slots: list[PokedexBinderSlot]


# --- Page schemas (FREE_PLACEMENT) -----------------------------------------

class FreePlacementCardInfo(BaseModel):
    card_id: int
    api_card_id: str | None
    card_number: str | None
    rarity: str | None
    image_url: str | None
    species_id: int | None
    pokemon_name: str | None
    national_dex_number: int | None
    set_name: str | None
    set_code: str | None


class FreePlacementSlot(BaseModel):
    slot: int
    placement_id: int | None
    card: FreePlacementCardInfo | None
    is_concept: bool


class FreePlacementPage(BaseModel):
    binder_type: str = "FREE_PLACEMENT"
    page: int
    page_size: int
    total_pages: int
    rows: int
    columns: int
    slots: list[FreePlacementSlot]


# ---------------------------------------------------------------------------
# Routes — binder CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[BinderRead], summary="List binders")
def list_all_binders(session=Depends(get_session)):
    """Return all binders for the active profile (oldest first)."""
    profile_id = get_active_profile_id(session)
    # Ensure at least one binder exists (first-run/legacy safety net).
    svc.ensure_default_binder(session, profile_id)
    return svc.list_binders(session, profile_id)


@router.get("/default", response_model=BinderRead, summary="Get default binder")
def get_default(session=Depends(get_session)):
    """Return the active profile's default binder."""
    profile_id = get_active_profile_id(session)
    svc.ensure_default_binder(session, profile_id)
    return svc.get_default_binder(session, profile_id)


@router.post("", response_model=BinderRead, status_code=201, summary="Create a binder")
def create_new_binder(body: BinderCreate, session=Depends(get_session)):
    """Create a new binder for the active profile."""
    profile_id = get_active_profile_id(session)
    try:
        return svc.create_binder(
            session,
            profile_id,
            name=body.name,
            binder_type=body.binder_type,
            rows=body.rows,
            columns=body.columns,
            sort_order=body.sort_order,
        )
    except svc.BinderLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except svc.BinderValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{binder_id}", response_model=BinderRead, summary="Update a binder")
def update_existing_binder(binder_id: int, body: BinderUpdate, session=Depends(get_session)):
    """Update a binder's name/layout/sort. ``binder_type`` is immutable."""
    profile_id = get_active_profile_id(session)
    try:
        return svc.update_binder(
            session,
            binder_id,
            profile_id,
            name=body.name,
            rows=body.rows,
            columns=body.columns,
            sort_order=body.sort_order,
            binder_type=body.binder_type,
        )
    except svc.BinderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except svc.BinderValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{binder_id}/default", response_model=BinderRead, summary="Set default binder")
def make_default(binder_id: int, session=Depends(get_session)):
    """Make the given binder the active profile's default."""
    profile_id = get_active_profile_id(session)
    try:
        return svc.set_default_binder(session, binder_id, profile_id)
    except svc.BinderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{binder_id}", status_code=204, summary="Delete a binder")
def delete_existing_binder(binder_id: int, session=Depends(get_session)):
    """Delete a binder. The last remaining binder cannot be deleted."""
    profile_id = get_active_profile_id(session)
    try:
        svc.delete_binder(session, binder_id, profile_id)
    except svc.BinderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except svc.BinderMinimumError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return None


# ---------------------------------------------------------------------------
# Routes — binder page
# ---------------------------------------------------------------------------

@router.get("/{binder_id}/page", summary="Get a binder page")
def get_binder_page(
    binder_id: int,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed).")] = 1,
    session=Depends(get_session),
):
    """Return a page of a binder.

    The response shape branches on the binder type:
    - POKEDEX: derived National Dex slots (owned / not-owned / has-card).
    - FREE_PLACEMENT: explicit slots with owned vs concept cards.
    """
    profile_id = get_active_profile_id(session)
    try:
        binder = svc.get_binder_for_profile(session, binder_id, profile_id)
    except svc.BinderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    result = svc.get_binder_page_for(session, binder, profile_id=profile_id, page=page)

    if binder.binder_type == "FREE_PLACEMENT":
        return FreePlacementPage(**result)
    return PokedexBinderPage(**result)


# ---------------------------------------------------------------------------
# Routes — placements (FREE_PLACEMENT only)
# ---------------------------------------------------------------------------

@router.post(
    "/{binder_id}/placements",
    response_model=PlacementRead,
    status_code=201,
    summary="Add a placement",
)
def add_placement(binder_id: int, body: PlacementCreate, session=Depends(get_session)):
    """Place a card on a specific page/slot of a FREE_PLACEMENT binder."""
    profile_id = get_active_profile_id(session)
    try:
        return svc.add_placement(
            session,
            binder_id,
            profile_id,
            card_id=body.card_id,
            page=body.page,
            slot=body.slot,
        )
    except svc.BinderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except svc.PlacementConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except svc.PlacementValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch(
    "/{binder_id}/placements/{placement_id}",
    response_model=PlacementRead,
    summary="Move a placement",
)
def move_placement(
    binder_id: int, placement_id: int, body: PlacementMove, session=Depends(get_session)
):
    """Move an existing placement to a new empty slot (409 if occupied)."""
    profile_id = get_active_profile_id(session)
    try:
        return svc.move_placement(
            session,
            binder_id,
            profile_id,
            placement_id,
            page=body.page,
            slot=body.slot,
        )
    except svc.BinderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except svc.PlacementNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except svc.PlacementConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except svc.PlacementValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/{binder_id}/placements/{placement_id}",
    status_code=204,
    summary="Remove a placement",
)
def remove_placement(binder_id: int, placement_id: int, session=Depends(get_session)):
    """Remove a placement. Never modifies the Collection."""
    profile_id = get_active_profile_id(session)
    try:
        svc.remove_placement(session, binder_id, profile_id, placement_id)
    except svc.BinderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except svc.PlacementNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return None
