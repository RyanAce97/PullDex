"""Binder routes for the PullDex API.

The binder represents the National Pokédex as fixed slots (#1–#1025).
Each page shows a range of dex positions with three possible states:
- Not owned (empty pocket)
- Owned, no card (species-level only)
- Owned with card (shows selected binder card)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.database import get_session
from app.services.binder_service import get_binder_page, set_binder_card, unset_binder_card

router = APIRouter(prefix="/binder", tags=["Binder"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BinderCardInfo(BaseModel):
    """Representative card for an owned species slot."""
    id: int
    api_card_id: str | None
    card_number: str | None
    rarity: str | None
    image_url: str | None
    set_name: str | None
    set_code: str | None
    quantity: int


class BinderSlot(BaseModel):
    """A single binder slot representing one National Dex position."""
    dex_number: int | None
    species_name: str | None
    species_id: int | None
    owned: bool
    has_card: bool
    card: BinderCardInfo | None
    total_cards: int


class BinderPageResponse(BaseModel):
    """A page of National Dex binder slots."""
    page: int
    page_size: int
    total_species: int
    total_pages: int
    slots: list[BinderSlot]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/page", response_model=BinderPageResponse, summary="Get binder page")
def get_binder_slots(
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed).")] = 1,
    page_size: Annotated[int | None, Query(ge=4, le=25, description="Slots per page.")] = None,
    session=Depends(get_session),
):
    """Return a page of National Dex binder slots for the active profile.

    Each slot has three possible states:
    - owned=false: Pokémon not owned (empty pocket)
    - owned=true, has_card=false: Species-level ownership, no card image
    - owned=true, has_card=true: Card ownership with selected binder card shown
    """
    return get_binder_page(session, page=page, page_size=page_size)


@router.put("/card/{entry_id}", status_code=200, summary="Set binder card")
def select_binder_card(entry_id: int, session=Depends(get_session)):
    """Select a card-level collection entry as the binder card for its species.

    Only one card per species per profile can be the binder card.
    Selecting a new card automatically deselects the previous one.
    """
    success = set_binder_card(session, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Collection entry not found or not a card entry.")
    return {"success": True}


@router.delete("/card/{entry_id}", status_code=200, summary="Unset binder card")
def deselect_binder_card(entry_id: int, session=Depends(get_session)):
    """Remove binder card selection from a collection entry."""
    success = unset_binder_card(session, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Collection entry not found.")
    return {"success": True}
