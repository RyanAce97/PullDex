"""Read-only card routes for the PullDex API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_session
from app.schemas.card import CardRead
from app.schemas.card_search import (
    CardFilterOptions,
    CardSearchResult,
    PaginatedCardSearchResponse,
)
from app.services.card_service import (
    get_card_by_id,
    get_cards_by_national_dex_number,
    get_filter_options,
    search_cards_by_name,
    search_cards_full,
    search_cards_paginated,
)

router = APIRouter(prefix="/cards", tags=["Cards"])


@router.get("/search", response_model=PaginatedCardSearchResponse, summary="Search cards (paginated)")
def search_cards_rich(
    q: Annotated[str | None, Query(min_length=1, description="Free-text search across name, card number, set code, set name.")] = None,
    species: Annotated[str | None, Query(min_length=1, description="Filter by Pokémon species name (substring).")] = None,
    set_name: Annotated[str | None, Query(min_length=1, description="Filter by set name or set code (substring).")] = None,
    rarity: Annotated[str | None, Query(min_length=1, description="Filter by exact rarity value.")] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed).")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Results per page.")] = 50,
    session=Depends(get_session),
):
    """Search cards with pagination and optional filters.

    At least one of ``q``, ``species``, ``set_name``, or ``rarity`` must be
    provided. Filters are combined with AND logic.

    Returns paginated results with total count metadata.
    """
    # Require at least one search criterion
    if not any([q, species, set_name, rarity]):
        raise HTTPException(
            status_code=422,
            detail="At least one of q, species, set_name, or rarity is required.",
        )

    items, total = search_cards_paginated(
        session,
        query=q,
        species=species,
        set_name=set_name,
        rarity=rarity,
        page=page,
        page_size=page_size,
    )

    return PaginatedCardSearchResponse.build(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/filter-options", response_model=CardFilterOptions, summary="Get card filter options")
def get_card_filter_options(session=Depends(get_session)):
    """Return available filter values for the card search UI.

    Currently returns distinct rarity values present in the database.
    """
    return get_filter_options(session)


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


@router.get("/by-dex/{national_dex_number}", response_model=list[CardSearchResult], summary="Get cards by National Dex number")
def get_cards_by_dex(
    national_dex_number: int,
    limit: Annotated[int, Query(ge=1, le=250, description="Maximum results to return.")] = 100,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    session=Depends(get_session),
):
    """Return all cards featuring the Pokémon with the given National Pokédex number.

    Returns rich results with set name and species info for display purposes.

    Returns an empty list if the species is unknown or has no cards — never
    raises 404.
    """
    return _get_cards_by_dex_rich(session, national_dex_number, limit, offset)


def _get_cards_by_dex_rich(session, national_dex_number: int, limit: int, offset: int) -> list[dict]:
    """Return cards for a dex number with full set/species context."""
    from sqlmodel import select as sm_select

    from app.models.card import Card
    from app.models.pokemon_species import PokemonSpecies
    from app.models.set import Set

    species = session.exec(
        sm_select(PokemonSpecies).where(
            PokemonSpecies.national_dex_number == national_dex_number
        )
    ).first()
    if species is None:
        return []

    statement = (
        sm_select(
            Card.id,
            Card.api_card_id,
            Card.card_number,
            Card.rarity,
            Card.image_url,
            PokemonSpecies.name.label("pokemon_name"),  # type: ignore[attr-defined]
            PokemonSpecies.national_dex_number,
            Set.name.label("set_name"),  # type: ignore[attr-defined]
            Set.api_set_id.label("set_code"),  # type: ignore[attr-defined]
        )
        .join(PokemonSpecies, Card.pokemon_species_id == PokemonSpecies.id, isouter=True)
        .join(Set, Card.set_id == Set.id, isouter=True)
        .where(Card.pokemon_species_id == species.id)
        .order_by(Set.name, Card.card_number)  # type: ignore[arg-type]
        .offset(offset)
        .limit(limit)
    )

    rows = session.exec(statement).all()  # type: ignore[call-overload]

    return [
        {
            "id": row.id,
            "api_card_id": row.api_card_id,
            "card_number": row.card_number,
            "rarity": row.rarity,
            "image_url": row.image_url,
            "pokemon_name": row.pokemon_name,
            "national_dex_number": row.national_dex_number,
            "set_name": row.set_name,
            "set_code": row.set_code,
        }
        for row in rows
    ]


@router.get("/{card_id}", response_model=CardRead, summary="Get a card by ID")
def get_card(card_id: int, session=Depends(get_session)):
    """Return a single card by its local database ID.

    Raises **404** if no card with that ID exists.
    """
    card = get_card_by_id(session, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found.")
    return card
