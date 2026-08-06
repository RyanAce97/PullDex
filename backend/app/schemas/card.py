"""Response schemas for card-related API endpoints.

These are plain Pydantic models used as ``response_model`` on routes.
They decouple the public API contract from the SQLModel table models,
preventing internal fields (relationship objects, SQLAlchemy state, etc.)
from leaking into responses.
"""

from pydantic import BaseModel, ConfigDict


class CardRead(BaseModel):
    """Public representation of a Card returned by the API.

    All fields are optional to accommodate cards that were imported
    with incomplete data from the external API.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    api_card_id: str | None
    set_id: int | None
    pokemon_species_id: int | None
    card_number: str | None
    rarity: str | None
    variant: str | None
    image_url: str | None
