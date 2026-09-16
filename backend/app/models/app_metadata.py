from typing import Optional

from sqlmodel import Field, SQLModel


class AppMetadata(SQLModel, table=True):
    """Small key/value store for application-level metadata.

    This table is intentionally isolated from all card and user-data tables
    (cards, sets, collection, profiles, pokemon_species). It holds simple
    scalar settings that PullDex needs to persist across restarts — for
    example the local *card-data catalogue version*.

    It must NEVER hold collection, ownership, quantity, binder, or profile
    information. It is reference/config metadata only.
    """

    __tablename__ = "app_metadata"

    key: str = Field(
        primary_key=True,
        max_length=100,
        description="Metadata key, e.g. 'card_data_version'.",
    )
    value: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Metadata value, stored as text.",
    )
