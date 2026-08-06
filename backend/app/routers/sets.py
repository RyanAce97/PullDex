"""Read-only set routes for the PullDex API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_session
from app.schemas.set import SetRead
from app.schemas.set_summary import SetSummaryRead
from app.services.set_service import (
    get_all_sets,
    get_set_by_api_id,
    get_set_by_id,
    search_sets_by_name,
)
from app.services.set_summary_service import get_set_summaries

router = APIRouter(prefix="/sets", tags=["Sets"])


@router.get("/summary", response_model=list[SetSummaryRead], summary="Set ownership summary")
def sets_summary(session=Depends(get_session)):
    """Return one row per set with species ownership statistics.

    Shows total species in set, owned species, and missing species.
    Only includes sets that contain at least one Pokémon card.
    """
    return get_set_summaries(session)


@router.get("", response_model=list[SetRead], summary="List or search sets")
def list_sets(
    name: Annotated[str | None, Query(min_length=1, description="Optional name substring to filter by.")] = None,
    limit: Annotated[int, Query(ge=1, le=250, description="Maximum results to return.")] = 250,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    session=Depends(get_session),
):
    """List all sets, optionally filtered by name substring.

    When ``name`` is provided, performs a case-insensitive substring search.
    When omitted, returns all sets paginated.

    Returns an empty list when no sets match — never raises 404.
    """
    if name:
        return search_sets_by_name(session, name, limit=limit, offset=offset)
    return get_all_sets(session, limit=limit, offset=offset)


@router.get("/api/{api_set_id}", response_model=SetRead, summary="Get a set by external API ID")
def get_set_by_external_id(api_set_id: str, session=Depends(get_session)):
    """Return a single set by its external Pokémon TCG API identifier (e.g. ``sv1``).

    Raises **404** if no set with that API ID exists.
    """
    tcg_set = get_set_by_api_id(session, api_set_id)
    if tcg_set is None:
        raise HTTPException(status_code=404, detail=f"Set with api_set_id '{api_set_id}' not found.")
    return tcg_set


@router.get("/{set_id}", response_model=SetRead, summary="Get a set by ID")
def get_set(set_id: int, session=Depends(get_session)):
    """Return a single set by its local database ID.

    Raises **404** if no set with that ID exists.
    """
    tcg_set = get_set_by_id(session, set_id)
    if tcg_set is None:
        raise HTTPException(status_code=404, detail=f"Set {set_id} not found.")
    return tcg_set
