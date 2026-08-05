from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.card import Card


class Set(SQLModel, table=True):
    """A Pokémon TCG expansion set (e.g. 'Scarlet & Violet — Base Set').

    One set contains many cards.
    """

    __tablename__ = "sets"  # 'set' is a reserved word in SQL

    id: Optional[int] = Field(default=None, primary_key=True)
    api_set_id: Optional[str] = Field(
        default=None,
        index=True,
        max_length=50,
        description="External Pokémon TCG API set identifier, e.g. 'sv1'.",
    )
    name: str = Field(
        index=True,
        max_length=150,
        description="Full set name, e.g. 'Scarlet & Violet — Base Set'.",
    )
    series: str = Field(
        index=True,
        max_length=100,
        description="Series the set belongs to, e.g. 'Scarlet & Violet'.",
    )
    release_date: Optional[date] = Field(
        default=None,
        description="Official release date of the set.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    cards: list["Card"] = Relationship(back_populates="set")
