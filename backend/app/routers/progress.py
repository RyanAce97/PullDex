"""Living Dex progress routes for the PullDex API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.database import get_session
from app.schemas.progress import MissingSpeciesRead, ProgressRead
from app.services.progress_service import get_missing_species, get_progress

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get("", response_model=ProgressRead, summary="Get Living Dex progress")
def progress(session=Depends(get_session)):
    """Return a summary of Living Dex completion.

    Shows total species count, owned count, missing count, and completion
    percentage.  All values are derived from Collection entries linked
    through Cards to PokémonSpecies.
    """
    return get_progress(session)


@router.get("/missing", response_model=list[MissingSpeciesRead], summary="List missing species")
def missing_species(
    limit: Annotated[int, Query(ge=1, le=1025, description="Maximum results to return.")] = 250,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    session=Depends(get_session),
):
    """Return the list of Pokémon species not currently in the user's collection.

    Ordered by National Pokédex number.  Paginated.
    """
    return get_missing_species(session, limit=limit, offset=offset)
