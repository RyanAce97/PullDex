"""Read-only card routes for the PullDex API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_session
from app.schemas.card import CardRead
from app.services.card_service import (
    get_card_by_id,
    get_cards_by_national_dex_number,
    search_cards_by_name,
)

router = APIRouter(prefix="/cards", tags=["Cards"])


@router.get("", response_model=list[CardRead], summary="Search cards by name")
def search_cards(
    name: Annotated[str, Query(min_length=1, description="Pokémon name substring to search for.")],
    limit: Annotated[int, Query(ge=1, le=250, description="Maximum results to return.")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    session=Depends(get_session),
):
    """Search for cards by Pokémon species name (case-insensitive substring).

    Trainer and energy cards are matched against their API card ID when they
    have no linked species.

    Returns an empty list when no cards match — never raises 404.
    """
    return search_cards_by_name(session, name, limit=limit, offset=offset)


@router.get("/by-dex/{national_dex_number}", response_model=list[CardRead], summary="Get cards by National Dex number")
def get_cards_by_dex(
    national_dex_number: int,
    limit: Annotated[int, Query(ge=1, le=250, description="Maximum results to return.")] = 100,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    session=Depends(get_session),
):
    """Return all cards featuring the Pokémon with the given National Pokédex number.

    Returns an empty list if the species is unknown or has no cards — never
    raises 404.
    """
    return get_cards_by_national_dex_number(
        session, national_dex_number, limit=limit, offset=offset
    )


@router.get("/{card_id}", response_model=CardRead, summary="Get a card by ID")
def get_card(card_id: int, session=Depends(get_session)):
    """Return a single card by its local database ID.

    Raises **404** if no card with that ID exists.
    """
    card = get_card_by_id(session, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found.")
    return card
