"""Collection routes for the PullDex API.

Supports two levels of tracking:
  - Species-level: quick "I own this Pokémon" (fast collection entry)
  - Card-level: "I own N copies of this specific card" (detailed tracking)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_session
from app.schemas.collection import (
    CollectionCardCreate,
    CollectionCardUpdate,
    CollectionRead,
    CollectionSpeciesCreate,
)
from app.services.collection_service import (
    add_card_to_collection,
    add_species_to_collection,
    get_card_entries_for_species,
    get_collection,
    get_collection_entry_by_id,
    remove_from_collection,
    remove_species_from_collection,
    update_card_quantity,
)

router = APIRouter(prefix="/collection", tags=["Collection"])


# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CollectionRead], summary="List collection entries")
def list_collection(
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum results to return.")] = 1000,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    session=Depends(get_session),
):
    """Return all collection entries (species-level and card-level).

    Paginated. Returns an empty list when the collection is empty.
    """
    return get_collection(session, limit=limit, offset=offset)


@router.get("/{entry_id}", response_model=CollectionRead, summary="Get a collection entry")
def get_entry(entry_id: int, session=Depends(get_session)):
    """Return a single collection entry by its ID.

    Raises **404** if no entry with that ID exists.
    """
    entry = get_collection_entry_by_id(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Collection entry {entry_id} not found.")
    return entry


@router.delete("/{entry_id}", status_code=204, summary="Remove a collection entry")
def delete_entry(entry_id: int, session=Depends(get_session)):
    """Remove any collection entry by its ID.

    Raises **404** if no entry with that ID exists.
    """
    deleted = remove_from_collection(session, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Collection entry {entry_id} not found.")
    return None


# ---------------------------------------------------------------------------
# Species-level (fast entry)
# ---------------------------------------------------------------------------

@router.post("/species", response_model=CollectionRead, status_code=201, summary="Add species to collection")
def add_species(body: CollectionSpeciesCreate, session=Depends(get_session)):
    """Mark a Pokémon species as owned (fast entry — no specific card needed).

    Idempotent: if already owned at species level, returns the existing entry.
    Raises **404** if the species does not exist.
    """
    try:
        entry = add_species_to_collection(session, body.pokemon_species_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return entry


@router.delete("/species/{species_id}", status_code=204, summary="Remove species from collection")
def remove_species(species_id: int, session=Depends(get_session)):
    """Remove species-level ownership. Does NOT remove card-level entries.

    Raises **404** if no species-level entry exists.
    """
    deleted = remove_species_from_collection(session, species_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No species-level entry for species {species_id}.")
    return None


# ---------------------------------------------------------------------------
# Card-level (detailed tracking)
# ---------------------------------------------------------------------------

@router.post("/cards", response_model=CollectionRead, status_code=201, summary="Add card to collection")
def add_card(body: CollectionCardCreate, session=Depends(get_session)):
    """Add a specific card to the collection with a quantity.

    If the card is already tracked, quantity is incremented.
    Raises **404** if the card does not exist.
    """
    try:
        entry = add_card_to_collection(session, body.card_id, body.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return entry


@router.patch("/cards/{entry_id}", response_model=CollectionRead, summary="Update card quantity")
def update_card(entry_id: int, body: CollectionCardUpdate, session=Depends(get_session)):
    """Update the quantity of a card-level entry.

    Setting quantity to 0 removes the entry entirely.
    Raises **404** if the entry does not exist.
    """
    result = update_card_quantity(session, entry_id, body.quantity)
    if result is None and body.quantity > 0:
        raise HTTPException(status_code=404, detail=f"Collection entry {entry_id} not found.")
    if result is None:
        # quantity <= 0 means deleted — return 204-like empty
        return CollectionRead(id=entry_id, pokemon_species_id=None, card_id=None, quantity=0)
    return result


@router.get("/species/{species_id}/cards", response_model=list[CollectionRead], summary="Get card entries for species")
def get_species_cards(species_id: int, session=Depends(get_session)):
    """Return all card-level collection entries for cards of a given species."""
    return get_card_entries_for_species(session, species_id)
