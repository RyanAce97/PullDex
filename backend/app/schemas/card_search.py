"""Response schema for the card search endpoint used by the Add Cards page."""

from pydantic import BaseModel, ConfigDict


class CardSearchResult(BaseModel):
    """Rich card search result with denormalized species and set info.

    Provides everything the frontend needs to display a card search result
    without additional API calls.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    api_card_id: str | None
    card_number: str | None
    rarity: str | None
    image_url: str | None
    pokemon_name: str | None
    national_dex_number: int | None
    set_name: str | None
    set_code: str | None
