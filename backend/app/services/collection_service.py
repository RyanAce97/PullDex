"""Service layer for Collection queries and mutations.

Provides functions used by API routes and other consumers.
All functions accept an open SQLModel Session and return model instances
or lists — no HTTP concerns live here.
"""

from sqlmodel import Session, select

from app.models.card import Card
from app.models.collection import Collection


def get_collection(
    session: Session,
    limit: int = 250,
    offset: int = 0,
) -> list[Collection]:
    """Return all collection entries, paginated.

    Args:
        session: An open SQLModel Session.
        limit:   Maximum number of results to return.
        offset:  Number of results to skip (for pagination).

    Returns:
        A list of :class:`Collection` instances, possibly empty.
    """
    statement = select(Collection).offset(offset).limit(limit)
    return list(session.exec(statement).all())


def get_collection_entry_by_id(session: Session, entry_id: int) -> Collection | None:
    """Return a single Collection entry by its local primary key, or None.

    Args:
        session:  An open SQLModel Session.
        entry_id: The local integer primary key of the collection entry.

    Returns:
        The matching :class:`Collection`, or ``None``.
    """
    return session.get(Collection, entry_id)


def add_card_to_collection(session: Session, card_id: int) -> Collection:
    """Add a card to the user's collection.

    Validates that the referenced card exists before creating the entry.

    Args:
        session: An open SQLModel Session.
        card_id: The local primary key of the :class:`Card` to add.

    Returns:
        The newly created :class:`Collection` instance.

    Raises:
        ValueError: If no card with the given ``card_id`` exists.
    """
    card = session.get(Card, card_id)
    if card is None:
        raise ValueError(f"Card {card_id} does not exist.")

    entry = Collection(card_id=card_id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def remove_from_collection(session: Session, entry_id: int) -> bool:
    """Remove a collection entry by its primary key.

    Args:
        session:  An open SQLModel Session.
        entry_id: The local primary key of the collection entry to remove.

    Returns:
        ``True`` if the entry was deleted, ``False`` if it did not exist.
    """
    entry = session.get(Collection, entry_id)
    if entry is None:
        return False
    session.delete(entry)
    session.commit()
    return True


def is_card_in_collection(session: Session, card_id: int) -> bool:
    """Check whether a card is already in the collection.

    Args:
        session: An open SQLModel Session.
        card_id: The local primary key of the card to check.

    Returns:
        ``True`` if at least one collection entry references this card.
    """
    entry = session.exec(
        select(Collection).where(Collection.card_id == card_id)
    ).first()
    return entry is not None
