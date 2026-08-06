"""Response schemas for Living Dex progress endpoints."""

from pydantic import BaseModel, ConfigDict


class ProgressRead(BaseModel):
    """Summary of Living Dex completion progress."""

    total_species: int
    owned_species: int
    missing_species: int
    completion_percentage: float


class MissingSpeciesRead(BaseModel):
    """Public representation of a missing Pokémon species."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    national_dex_number: int
    name: str
    generation: int | None
