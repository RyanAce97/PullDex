from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.card import Card


class Collection(SQLModel, table=True):
    """A card in the user's Living Dex collection.

    A row existing in this table means the user owns that card.
    Deleting a row removes it from the collection.
    """

    __tablename__ = "collection"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ------------------------------------------------------------------
    # Foreign keys
    # ------------------------------------------------------------------
    card_id: Optional[int] = Field(
        default=None,
        foreign_key="cards.id",
        index=True,
        description="The card owned by the user.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    card: Optional["Card"] = Relationship(back_populates="collection_entries")
