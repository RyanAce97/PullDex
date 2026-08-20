"""Profile model for local user collection separation."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.collection import Collection


class Profile(SQLModel, table=True):
    """A local user profile.

    Profiles allow multiple collections to exist on the same machine.
    Each profile has its own collection, binder preferences, and settings.

    Exactly one profile is active at any time (is_active=True).
    There must always be at least one profile in the database.

    Designed to potentially evolve into online accounts in the future —
    uses no filesystem-specific assumptions.
    """

    __tablename__ = "profiles"

    id: Optional[int] = Field(default=None, primary_key=True)

    name: str = Field(
        max_length=100,
        description="Human-readable profile name, e.g. 'Ryan'.",
    )

    is_active: bool = Field(
        default=False,
        description="Whether this is the currently active profile.",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the profile was created.",
    )

    # ------------------------------------------------------------------
    # Binder preferences
    # ------------------------------------------------------------------
    binder_rows: int = Field(
        default=5,
        ge=2,
        le=5,
        description="Number of rows in the binder grid (2–5).",
    )
    binder_columns: int = Field(
        default=4,
        ge=2,
        le=5,
        description="Number of columns in the binder grid (2–5).",
    )
    binder_sort: str = Field(
        default="dex_number",
        max_length=50,
        description="Default binder sort order: dex_number, set, card_number, recent.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    collection_entries: list["Collection"] = Relationship(back_populates="profile")
