"""Response and request schemas for collection endpoints."""

from pydantic import BaseModel, ConfigDict


class CollectionRead(BaseModel):
    """Public representation of a collection entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    pokemon_species_id: int | None
    card_id: int | None
    quantity: int
    is_binder_card: bool = False


class CollectionSpeciesCreate(BaseModel):
    """Add a species to the collection (fast entry — no specific card)."""

    pokemon_species_id: int


class CollectionCardCreate(BaseModel):
    """Add a specific card to the collection."""

    card_id: int
    quantity: int = 1


class CollectionCardUpdate(BaseModel):
    """Update quantity of a card-level collection entry."""

    quantity: int
