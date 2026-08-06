from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.collection import Collection
    from app.models.pokemon_species import PokemonSpecies
    from app.models.set import Set


class Card(SQLModel, table=True):
    """An individual Pokémon TCG card.

    A card belongs to one set and features one Pokémon species.
    A single card may appear in many Collection entries (one per pull).
    """

    __tablename__ = "cards"

    id: Optional[int] = Field(default=None, primary_key=True)

    # External API identifier (e.g. TCGdx / PokéTCG API card ID such as "sv1-25").
    api_card_id: Optional[str] = Field(
        default=None,
        unique=True,
        index=True,
        max_length=50,
        description="Identifier from the external card API, e.g. 'sv1-25'.",
    )

    # ------------------------------------------------------------------
    # Foreign keys
    # ------------------------------------------------------------------
    pokemon_species_id: Optional[int] = Field(
        default=None,
        foreign_key="pokemon_species.id",
        index=True,
        description="The species featured on this card.",
    )
    set_id: Optional[int] = Field(
        default=None,
        foreign_key="sets.id",
        index=True,
        description="The set this card belongs to.",
    )

    # ------------------------------------------------------------------
    # Card details
    # ------------------------------------------------------------------
    card_number: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Card number within its set, e.g. '025/198'.",
    )
    rarity: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Card rarity string, e.g. 'Rare Holo', 'Common'.",
    )
    variant: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Variant type if applicable, e.g. 'Reverse Holo', 'Full Art'.",
    )
    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL to the card image.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    pokemon_species: Optional["PokemonSpecies"] = Relationship(back_populates="cards")
    set: Optional["Set"] = Relationship(back_populates="cards")
    collection_entries: list["Collection"] = Relationship(back_populates="card")
