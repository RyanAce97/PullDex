"""Pack recommendation routes for the PullDex API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.database import get_session
from app.schemas.progress import MissingSpeciesRead
from app.schemas.recommendation import RecommendationResponse, SetRecommendation
from app.services.progress_service import (
    get_missing_species_count,
    get_owned_species_count,
    get_total_species_count,
)
from app.services.recommendation_service import (
    get_missing_species_in_set,
    get_set_recommendations,
)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=RecommendationResponse, summary="Get pack recommendations")
def recommendations(
    limit: Annotated[int, Query(ge=1, le=50, description="Maximum number of sets to recommend.")] = 10,
    session=Depends(get_session),
):
    """Return the top recommended TCG sets for completing the Living Dex.

    Sets are ranked by the number of distinct missing Pokémon species
    they contain.  Only sets with at least one missing species appear.

    Tie-breaking: fewer total cards (higher density), then newest release date.
    """
    recs = get_set_recommendations(session, limit=limit)
    total = get_total_species_count(session)
    owned = get_owned_species_count(session)
    missing = total - owned

    return RecommendationResponse(
        total_species=total,
        owned_species=owned,
        total_missing_species=missing,
        recommendations=[SetRecommendation(**r) for r in recs],
    )


@router.get(
    "/{set_id}/species",
    response_model=list[MissingSpeciesRead],
    summary="Missing species available in a set",
)
def missing_in_set(set_id: int, session=Depends(get_session)):
    """Return the specific missing species that have cards in the given set.

    Useful for drill-down: "What would I gain from buying this set?"
    Returns an empty list if the set has no cards for missing species.
    """
    return get_missing_species_in_set(session, set_id)
