"""Service layer for Collection queries and mutations.

Supports two levels of tracking:
  1. Species-level: quick "I own this Pokémon" without specifying a card.
  2. Card-level: "I own N copies of this specific card."
"""

from sqlmodel import Session, select

from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_collection(
    session: Session,
    limit: int = 250,
    offset: int = 0,
) -> list[Collection]:
    """Return all collection entries, paginated."""
    statement = select(Collection).offset(offset).limit(limit)
    return list(session.exec(statement).all())


def get_collection_entry_by_id(session: Session, entry_id: int) -> Collection | None:
    """Return a single collection entry by primary key, or None."""
    return session.get(Collection, entry_id)


def get_species_entry(session: Session, species_id: int) -> Collection | None:
    """Return the species-level entry for a given species, or None."""
    return session.exec(
        select(Collection).where(
            Collection.pokemon_species_id == species_id,
            Collection.card_id.is_(None),  # type: ignore[union-attr]
        )
    ).first()


def get_card_entries_for_species(session: Session, species_id: int) -> list[Collection]:
    """Return all card-level entries for cards belonging to a species."""
    statement = (
        select(Collection)
        .join(Card, Collection.card_id == Card.id)
        .where(Card.pokemon_species_id == species_id)
    )
    return list(session.exec(statement).all())


# ---------------------------------------------------------------------------
# Species-level operations
# ---------------------------------------------------------------------------

def add_species_to_collection(session: Session, species_id: int) -> Collection:
    """Add a species to the collection (fast entry).

    Idempotent: if a species-level entry already exists, returns it.

    Args:
        species_id: The PokemonSpecies primary key.

    Returns:
        The existing or new Collection entry.

    Raises:
        ValueError: If the species does not exist.
    """
    species = session.get(PokemonSpecies, species_id)
    if species is None:
        raise ValueError(f"Species {species_id} does not exist.")

    existing = get_species_entry(session, species_id)
    if existing:
        return existing

    entry = Collection(pokemon_species_id=species_id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def remove_species_from_collection(session: Session, species_id: int) -> bool:
    """Remove the species-level entry for a species.

    Does NOT remove card-level entries for that species.

    Returns:
        True if the entry was deleted, False if it didn't exist.
    """
    entry = get_species_entry(session, species_id)
    if entry is None:
        return False
    session.delete(entry)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Card-level operations
# ---------------------------------------------------------------------------

def add_card_to_collection(session: Session, card_id: int, quantity: int = 1) -> Collection:
    """Add a card to the collection, or increment quantity if already tracked.

    Args:
        card_id:  The Card primary key.
        quantity: Number of copies to add (default 1).

    Returns:
        The new or updated Collection entry.

    Raises:
        ValueError: If the card does not exist.
    """
    card = session.get(Card, card_id)
    if card is None:
        raise ValueError(f"Card {card_id} does not exist.")

    # Check if already tracked
    existing = session.exec(
        select(Collection).where(Collection.card_id == card_id)
    ).first()

    if existing:
        existing.quantity += quantity
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    entry = Collection(card_id=card_id, quantity=quantity)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def update_card_quantity(session: Session, entry_id: int, quantity: int) -> Collection | None:
    """Update the quantity of a card-level entry.

    If quantity <= 0, removes the entry entirely.

    Returns:
        The updated entry, or None if removed or not found.
    """
    entry = session.get(Collection, entry_id)
    if entry is None:
        return None

    if quantity <= 0:
        session.delete(entry)
        session.commit()
        return None

    entry.quantity = quantity
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def remove_from_collection(session: Session, entry_id: int) -> bool:
    """Remove a collection entry by primary key.

    Returns:
        True if deleted, False if not found.
    """
    entry = session.get(Collection, entry_id)
    if entry is None:
        return False
    session.delete(entry)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def is_species_owned(session: Session, species_id: int) -> bool:
    """Check if a species is owned (either directly or via card entries)."""
    # Direct species entry
    direct = session.exec(
        select(Collection).where(Collection.pokemon_species_id == species_id)
    ).first()
    if direct:
        return True

    # Via card entries
    card_entry = session.exec(
        select(Collection)
        .join(Card, Collection.card_id == Card.id)
        .where(Card.pokemon_species_id == species_id)
    ).first()
    return card_entry is not None
