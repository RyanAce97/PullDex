"""Binder models for the multi-binder system.

A profile may own several physical-style binders. There are two kinds:

- ``POKEDEX``: a National Pokédex binder whose slots are DERIVED from
  National Dex numbers #1–#1025 and the profile's Collection. Its
  ``BinderPlacement`` rows are not used for slot content — the layout
  (rows × columns) only controls pagination. This preserves the original
  single-binder behaviour.

- ``FREE_PLACEMENT``: an arbitrary binder (e.g. "Trades", "Master
  Collection"). Cards are explicitly placed on a page/slot via
  ``BinderPlacement`` rows. A placement references a specific card printing
  only — ownership ("concept" vs "owned") is DERIVED from the active
  profile's Collection at read time and is never stored here.

Design note — future Pokédex concept cards:
    Ownership/concept state is intentionally never persisted on a placement.
    Concept status is computed from the Collection when a page is read. This
    keeps the schema flexible: enabling concept cards in POKEDEX binders
    later is a read-time business-rule change, not a schema migration.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.profile import Profile


class BinderType(str, Enum):
    """The kind of binder. Immutable after creation."""

    POKEDEX = "POKEDEX"
    FREE_PLACEMENT = "FREE_PLACEMENT"


# Sort orders that are meaningful (primarily for POKEDEX binders). Mirrors the
# values historically validated on Profile.binder_sort.
VALID_BINDER_SORTS = {"dex_number", "set", "card_number", "recent"}

# Layout bounds (rows and columns), inclusive.
MIN_BINDER_DIMENSION = 2
MAX_BINDER_DIMENSION = 5

# Binder name length bound.
MAX_BINDER_NAME_LENGTH = 100

# The default name given to the migrated/seeded Pokédex binder.
DEFAULT_POKEDEX_BINDER_NAME = "Pokédex Binder"


class Binder(SQLModel, table=True):
    """A single binder belonging to a profile."""

    __tablename__ = "binders"

    id: Optional[int] = Field(default=None, primary_key=True)

    profile_id: int = Field(
        foreign_key="profiles.id",
        index=True,
        description="The profile that owns this binder.",
    )

    name: str = Field(
        max_length=MAX_BINDER_NAME_LENGTH,
        description="Human-readable binder name, e.g. 'Master Collection'.",
    )

    binder_type: str = Field(
        default=BinderType.POKEDEX.value,
        max_length=20,
        index=True,
        description="POKEDEX or FREE_PLACEMENT. Immutable after creation.",
    )

    rows: int = Field(
        default=5,
        description="Number of rows in the binder grid (2–5).",
    )
    columns: int = Field(
        default=4,
        description="Number of columns in the binder grid (2–5).",
    )
    sort_order: str = Field(
        default="dex_number",
        max_length=50,
        description="Sort order, primarily meaningful for POKEDEX binders.",
    )

    is_default: bool = Field(
        default=False,
        index=True,
        description="Whether this is the profile's default binder.",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the binder was created.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    profile: Optional["Profile"] = Relationship(back_populates="binders")
    placements: list["BinderPlacement"] = Relationship(
        back_populates="binder",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class BinderPlacement(SQLModel, table=True):
    """An explicit placement of a card in a FREE_PLACEMENT binder.

    References a specific card printing only. Ownership/concept status is
    derived from the Collection at read time — never stored here.
    """

    __tablename__ = "binder_placements"
    __table_args__ = (
        UniqueConstraint("binder_id", "page", "slot", name="uq_placement_binder_page_slot"),
        UniqueConstraint("binder_id", "card_id", name="uq_placement_binder_card"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    binder_id: int = Field(
        foreign_key="binders.id",
        index=True,
        description="The binder this placement belongs to.",
    )

    card_id: int = Field(
        foreign_key="cards.id",
        index=True,
        description="The specific card printing placed. Ownership is derived, not stored.",
    )

    page: int = Field(
        description="1-indexed page within the binder.",
    )
    slot: int = Field(
        description="0-indexed slot within the page.",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the placement was created.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    binder: Optional["Binder"] = Relationship(back_populates="placements")
    card: Optional["Card"] = Relationship()
