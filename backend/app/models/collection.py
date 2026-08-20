from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.pokemon_species import PokemonSpecies
    from app.models.profile import Profile


class Collection(SQLModel, table=True):
    """A collection entry representing ownership.

    Supports two levels of tracking:

    1. Species-level: ``pokemon_species_id`` set, ``card_id`` NULL.
       Means "I own this Pokémon" without specifying which card.

    2. Card-level: ``card_id`` set, ``quantity`` >= 1.
       Means "I own N copies of this specific card."

    A species is considered owned if EITHER:
      - A species-level entry exists for it, OR
      - Any card-level entry exists for a card linked to that species.

    Every collection entry belongs to a profile. The profile_id scopes
    collections so that different local users have independent data.
    """

    __tablename__ = "collection"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ------------------------------------------------------------------
    # Profile ownership
    # ------------------------------------------------------------------
    profile_id: int = Field(
        foreign_key="profiles.id",
        index=True,
        description="The profile this collection entry belongs to.",
    )

    # ------------------------------------------------------------------
    # Foreign keys (at least one must be set)
    # ------------------------------------------------------------------
    pokemon_species_id: Optional[int] = Field(
        default=None,
        foreign_key="pokemon_species.id",
        index=True,
        description="Direct species ownership (fast entry, no specific card).",
    )
    card_id: Optional[int] = Field(
        default=None,
        foreign_key="cards.id",
        index=True,
        description="Specific card ownership (detailed tracking).",
    )

    # ------------------------------------------------------------------
    # Quantity
    # ------------------------------------------------------------------
    quantity: int = Field(
        default=1,
        description="Number of copies owned (only meaningful for card-level entries).",
    )

    # ------------------------------------------------------------------
    # Binder card selection
    # ------------------------------------------------------------------
    is_binder_card: bool = Field(
        default=False,
        description="Whether this card-level entry is the selected binder card for its species. "
                    "Only one card per species per profile may be True.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    profile: Optional["Profile"] = Relationship(back_populates="collection_entries")
    card: Optional["Card"] = Relationship(back_populates="collection_entries")
    pokemon_species: Optional["PokemonSpecies"] = Relationship(
        back_populates="collection_entries",
    )
