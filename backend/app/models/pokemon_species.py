from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.card import Card


class PokemonSpecies(SQLModel, table=True):
    """A Pokémon species as defined by the National Pokédex.

    One species may appear on many different cards across many sets.
    """

    __tablename__ = "pokemon_species"

    id: Optional[int] = Field(default=None, primary_key=True)
    national_dex_number: int = Field(
        unique=True,
        index=True,
        description="National Pokédex number, e.g. 25 for Pikachu.",
    )
    name: str = Field(
        index=True,
        max_length=100,
        description="English species name, e.g. 'Pikachu'.",
    )
    generation: Optional[int] = Field(
        default=None,
        description="Generation the species was introduced in (1–9+).",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    cards: list["Card"] = Relationship(back_populates="pokemon_species")
