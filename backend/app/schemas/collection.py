"""Response schemas for collection-related API endpoints.

These are plain Pydantic models used as ``response_model`` on routes.
They decouple the public API contract from the SQLModel table models,
preventing internal fields (relationship objects, SQLAlchemy state, etc.)
from leaking into responses.
"""

from pydantic import BaseModel, ConfigDict


class CollectionRead(BaseModel):
    """Public representation of a Collection entry returned by the API.

    Each entry represents a card the user owns in their Living Dex.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int | None


class CollectionCreate(BaseModel):
    """Schema for adding a card to the collection."""

    card_id: int
