"""Collection routes for the PullDex API.

Provides endpoints for managing the user's Living Dex collection:
adding cards, removing cards, and viewing the current collection.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_session
from app.schemas.collection import CollectionCreate, CollectionRead
from app.services.collection_service import (
    add_card_to_collection,
    get_collection,
    get_collection_entry_by_id,
    remove_from_collection,
)

router = APIRouter(prefix="/collection", tags=["Collection"])


@router.get("", response_model=list[CollectionRead], summary="List collection entries")
def list_collection(
    limit: Annotated[int, Query(ge=1, le=250, description="Maximum results to return.")] = 250,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    session=Depends(get_session),
):
    """Return all cards currently in the user's Living Dex collection.

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


@router.post("", response_model=CollectionRead, status_code=201, summary="Add a card to the collection")
def add_to_collection(body: CollectionCreate, session=Depends(get_session)):
    """Add a card to the user's Living Dex collection.

    Raises **404** if the referenced card does not exist.
    """
    try:
        entry = add_card_to_collection(session, body.card_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return entry


@router.delete("/{entry_id}", status_code=204, summary="Remove a card from the collection")
def delete_entry(entry_id: int, session=Depends(get_session)):
    """Remove a card from the user's Living Dex collection.

    Raises **404** if no entry with that ID exists.
    """
    deleted = remove_from_collection(session, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Collection entry {entry_id} not found.")
    return None
