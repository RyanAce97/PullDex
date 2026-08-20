"""Response schemas for the card search endpoint used by the Add Cards page."""

import math

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


class PaginatedCardSearchResponse(BaseModel):
    """Paginated card search results with metadata for frontend pagination controls."""

    items: list[CardSearchResult]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def build(
        cls,
        items: list[dict],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedCardSearchResponse":
        """Factory that calculates total_pages automatically."""
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=[CardSearchResult(**item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class CardFilterOptions(BaseModel):
    """Available filter values for card search dropdowns."""

    rarities: list[str]
