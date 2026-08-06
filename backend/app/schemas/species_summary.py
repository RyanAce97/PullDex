"""Response schema for the species summary endpoint."""

from pydantic import BaseModel, ConfigDict


class SpeciesSummaryRead(BaseModel):
    """Species-level ownership status for the Collection page.

    One row per Pokémon species. Ownership means: the user has at least
    one card for this species in their collection.
    """

    model_config = ConfigDict(from_attributes=True)

    species_id: int
    national_dex_number: int
    name: str
    generation: int | None
    owned: bool
