"""Response schemas for the pack recommendation engine."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.progress import MissingSpeciesRead


class SetRecommendation(BaseModel):
    """A recommended set with its V1 score."""

    model_config = ConfigDict(from_attributes=True)

    set_id: int
    api_set_id: str | None
    set_name: str
    series: str
    release_date: date | None
    missing_species_count: int
    total_cards_in_set: int


class RecommendationResponse(BaseModel):
    """Top-level response for the recommendation endpoint."""

    total_missing_species: int
    recommendations: list[SetRecommendation]
