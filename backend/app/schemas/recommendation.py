"""Response schemas for the pack recommendation engine."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class SetRecommendation(BaseModel):
    """A recommended set with its V1 score and computed display fields."""

    model_config = ConfigDict(from_attributes=True)

    rank: int
    set_id: int
    api_set_id: str | None
    set_name: str
    series: str
    release_date: date | None
    missing_species_count: int
    total_species_in_set: int
    total_cards_in_set: int
    coverage_percentage: float
    missing_species_density_percentage: float


class RecommendationResponse(BaseModel):
    """Top-level response for the recommendation endpoint."""

    total_species: int
    owned_species: int
    total_missing_species: int
    recommendations: list[SetRecommendation]
