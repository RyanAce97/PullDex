"""Read-only Pokémon species routes for the PullDex API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_session
from app.schemas.pokemon_species import PokemonSpeciesRead
from app.schemas.species_summary import SpeciesSummaryRead
from app.services.pokemon_species_service import (
    get_all_species,
    get_species_by_dex_number,
    search_species_by_name,
)
from app.services.species_summary_service import get_species_summary

router = APIRouter(prefix="/species", tags=["Species"])


@router.get("/summary", response_model=list[SpeciesSummaryRead], summary="Species ownership summary")
def species_summary(session=Depends(get_session)):
    """Return one row per species with card variant counts and ownership status.

    Used by the Collection page to show species-level completion at a glance.
    Includes total available cards and how many the user owns for each species.
    """
    return get_species_summary(session)


@router.get("", response_model=list[PokemonSpeciesRead], summary="List or search species")
def list_species(
    name: Annotated[str | None, Query(min_length=1, description="Optional name substring to filter by.")] = None,
    limit: Annotated[int, Query(ge=1, le=1025, description="Maximum results to return.")] = 250,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    session=Depends(get_session),
):
    """List all Pokémon species, optionally filtered by name substring.

    When ``name`` is provided, performs a case-insensitive substring search.
    When omitted, returns all species paginated.

    Returns an empty list when no species match — never raises 404.
    """
    if name:
        return search_species_by_name(session, name, limit=limit, offset=offset)
    return get_all_species(session, limit=limit, offset=offset)


@router.get("/{national_dex_number}", response_model=PokemonSpeciesRead, summary="Get species by National Dex number")
def get_species(national_dex_number: int, session=Depends(get_session)):
    """Return a single Pokémon species by its National Pokédex number.

    Raises **404** if no species with that number exists.
    """
    species = get_species_by_dex_number(session, national_dex_number)
    if species is None:
        raise HTTPException(
            status_code=404,
            detail=f"Species with National Dex #{national_dex_number} not found.",
        )
    return species
