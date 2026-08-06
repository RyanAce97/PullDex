"""Response schemas for Pokémon species API endpoints.

These are plain Pydantic models used as ``response_model`` on routes.
They decouple the public API contract from the SQLModel table models,
preventing internal fields (relationship objects, SQLAlchemy state, etc.)
from leaking into responses.
"""

from pydantic import BaseModel, ConfigDict


class PokemonSpeciesRead(BaseModel):
    """Public representation of a PokemonSpecies returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    national_dex_number: int
    name: str
    generation: int | None
