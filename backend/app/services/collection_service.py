"""Service layer for Collection queries and mutations.

Supports two levels of tracking:
  1. Species-level: quick "I own this Pokémon" without specifying a card.
  2. Card-level: "I own N copies of this specific card."

All operations are scoped to the active profile. The profile_id is
automatically determined from the active profile — callers do not need
to pass it explicitly.
"""

from sqlmodel import Session, select

from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.services.profile_service import get_active_profile_id


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_collection(
    session: Session,
    limit: int = 250,
    offset: int = 0,
) -> list[Collection]:
    """Return all collection entries for the active profile, paginated."""
    profile_id = get_active_profile_id(session)
    statement = (
        select(Collection)
        .where(Collection.profile_id == profile_id)
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_collection_entry_by_id(session: Session, entry_id: int) -> Collection | None:
    """Return a single collection entry by primary key, or None."""
    return session.get(Collection, entry_id)


def get_species_entry(session: Session, species_id: int) -> Collection | None:
    """Return the species-level entry for a given species (active profile), or None."""
    profile_id = get_active_profile_id(session)
    return session.exec(
        select(Collection).where(
            Collection.profile_id == profile_id,
            Collection.pokemon_species_id == species_id,
            Collection.card_id.is_(None),  # type: ignore[union-attr]
        )
    ).first()


def get_card_entries_for_species(session: Session, species_id: int) -> list[Collection]:
    """Return all card-level entries for cards belonging to a species (active profile)."""
    profile_id = get_active_profile_id(session)
    statement = (
        select(Collection)
        .join(Card, Collection.card_id == Card.id)
        .where(
            Collection.profile_id == profile_id,
            Card.pokemon_species_id == species_id,
        )
    )
    return list(session.exec(statement).all())


# ---------------------------------------------------------------------------
# Species-level operations
# ---------------------------------------------------------------------------

def add_species_to_collection(session: Session, species_id: int) -> Collection:
    """Add a species to the collection (fast entry). Idempotent.

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

    profile_id = get_active_profile_id(session)
    entry = Collection(pokemon_species_id=species_id, profile_id=profile_id)
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


def remove_species_cascade(session: Session, species_id: int) -> dict:
    """Remove a species from the collection, including all associated card entries.

    Removes:
    - The species-level entry (if any)
    - All card-level entries for cards of that species

    All scoped to the active profile.

    Returns:
        Dict with removed_species (bool) and removed_cards (int count).
    """
    profile_id = get_active_profile_id(session)
    removed_species = False
    removed_cards = 0

    # Remove species-level entry
    species_entry = get_species_entry(session, species_id)
    if species_entry:
        session.delete(species_entry)
        removed_species = True

    # Remove all card-level entries for cards of this species
    card_entries = session.exec(
        select(Collection)
        .join(Card, Collection.card_id == Card.id)
        .where(
            Collection.profile_id == profile_id,
            Card.pokemon_species_id == species_id,
        )
    ).all()
    for entry in card_entries:
        session.delete(entry)
        removed_cards += 1

    if removed_species or removed_cards > 0:
        session.commit()

    return {"removed_species": removed_species, "removed_cards": removed_cards}


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

    profile_id = get_active_profile_id(session)

    # Check if already tracked in this profile
    existing = session.exec(
        select(Collection).where(
            Collection.profile_id == profile_id,
            Collection.card_id == card_id,
        )
    ).first()

    if existing:
        existing.quantity += quantity
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    entry = Collection(card_id=card_id, quantity=quantity, profile_id=profile_id)
    session.add(entry)
    session.commit()
    session.refresh(entry)

    # Auto-select as binder card if this is the only card for this species
    if card.pokemon_species_id:
        from app.services.binder_service import auto_select_binder_card_for_species
        auto_select_binder_card_for_species(session, profile_id, card.pokemon_species_id)
        session.refresh(entry)

    return entry


def update_card_quantity(session: Session, entry_id: int, quantity: int) -> Collection | None:
    """Update the quantity of a card-level entry.

    If quantity <= 0, removes the entry entirely and auto-selects
    a new binder card for the species if needed.

    Returns:
        The updated entry, or None if removed or not found.
    """
    entry = session.get(Collection, entry_id)
    if entry is None:
        return None

    if quantity <= 0:
        # Need species_id for binder card auto-selection
        card_id = entry.card_id
        profile_id = entry.profile_id
        species_id = None
        if card_id:
            card = session.get(Card, card_id)
            if card:
                species_id = card.pokemon_species_id

        session.delete(entry)
        session.commit()

        # Auto-select binder card if needed
        if species_id and profile_id:
            from app.services.binder_service import auto_select_binder_card_for_species
            auto_select_binder_card_for_species(session, profile_id, species_id)

        return None

    entry.quantity = quantity
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def remove_from_collection(session: Session, entry_id: int) -> bool:
    """Remove a collection entry by primary key.

    If removing a card-level entry, auto-selects a new binder card
    for the species if needed.

    Returns:
        True if deleted, False if not found.
    """
    entry = session.get(Collection, entry_id)
    if entry is None:
        return False

    # Capture info before deletion for binder card auto-selection
    card_id = entry.card_id
    profile_id = entry.profile_id
    species_id = None
    if card_id:
        card = session.get(Card, card_id)
        if card:
            species_id = card.pokemon_species_id

    session.delete(entry)
    session.commit()

    # Auto-select binder card if needed
    if species_id and profile_id:
        from app.services.binder_service import auto_select_binder_card_for_species
        auto_select_binder_card_for_species(session, profile_id, species_id)

    return True
