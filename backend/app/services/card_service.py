"""Service layer for Card queries.

Provides read functions used by API routes and other consumers.
All functions accept an open SQLModel Session and return model instances
or lists — no HTTP concerns live here.
"""

from sqlmodel import Session, select

from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set


def get_card_by_id(session: Session, card_id: int) -> Card | None:
    """Return a single Card by its local primary key, or None if not found.

    Args:
        session: An open SQLModel Session.
        card_id: The local integer primary key of the card.

    Returns:
        The matching :class:`Card`, or ``None``.
    """
    return session.get(Card, card_id)


def search_cards_by_name(
    session: Session,
    name: str,
    limit: int = 50,
    offset: int = 0,
) -> list[Card]:
    """Return cards whose ``api_card_id`` or linked species name contains
    the search term (case-insensitive substring match).

    The search checks the species ``name`` field on the joined
    :class:`PokemonSpecies` row.  Trainer and energy cards (which have no
    linked species) are included when the query string matches their
    ``api_card_id``.

    Args:
        session: An open SQLModel Session.
        name:    Substring to search for (case-insensitive).
        limit:   Maximum number of results to return.
        offset:  Number of results to skip (for pagination).

    Returns:
        A list of matching :class:`Card` instances, possibly empty.
    """
    term = f"%{name.lower()}%"

    statement = (
        select(Card)
        .join(PokemonSpecies, Card.pokemon_species_id == PokemonSpecies.id, isouter=True)
        .where(
            # Match on species name or on the raw card ID as a fallback.
            (PokemonSpecies.name.ilike(term)) | (Card.api_card_id.ilike(term))  # type: ignore[union-attr]
        )
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_cards_by_set(
    session: Session,
    set_id: int,
    limit: int = 250,
    offset: int = 0,
) -> list[Card]:
    """Return all cards belonging to the given set (by local Set.id).

    Args:
        session: An open SQLModel Session.
        set_id:  The local integer primary key of the :class:`Set`.
        limit:   Maximum number of results to return.
        offset:  Number of results to skip (for pagination).

    Returns:
        A list of :class:`Card` instances, possibly empty.
    """
    statement = (
        select(Card)
        .where(Card.set_id == set_id)
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_cards_by_set_api_id(
    session: Session,
    api_set_id: str,
    limit: int = 250,
    offset: int = 0,
) -> list[Card]:
    """Return all cards belonging to the set identified by its external API id.

    Convenience wrapper around :func:`get_cards_by_set` that accepts the
    string set identifier (e.g. ``"sv1"``) instead of the local primary key.

    Args:
        session:    An open SQLModel Session.
        api_set_id: External set identifier, e.g. ``"sv1"``.
        limit:      Maximum number of results to return.
        offset:     Number of results to skip (for pagination).

    Returns:
        A list of :class:`Card` instances, possibly empty.
    """
    tcg_set = session.exec(
        select(Set).where(Set.api_set_id == api_set_id)
    ).first()
    if tcg_set is None or tcg_set.id is None:
        return []
    return get_cards_by_set(session, tcg_set.id, limit=limit, offset=offset)


def get_cards_by_species(
    session: Session,
    species_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[Card]:
    """Return all cards featuring the given Pokémon species (by local id).

    Args:
        session:    An open SQLModel Session.
        species_id: The local integer primary key of the :class:`PokemonSpecies`.
        limit:      Maximum number of results to return.
        offset:     Number of results to skip (for pagination).

    Returns:
        A list of :class:`Card` instances, possibly empty.
    """
    statement = (
        select(Card)
        .where(Card.pokemon_species_id == species_id)
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_cards_by_national_dex_number(
    session: Session,
    national_dex_number: int,
    limit: int = 100,
    offset: int = 0,
) -> list[Card]:
    """Return all cards featuring the Pokémon with the given National Dex number.

    Convenience wrapper around :func:`get_cards_by_species` that accepts the
    National Pokédex number instead of the local species primary key.

    Args:
        session:             An open SQLModel Session.
        national_dex_number: National Pokédex number, e.g. ``25`` for Pikachu.
        limit:               Maximum number of results to return.
        offset:              Number of results to skip (for pagination).

    Returns:
        A list of :class:`Card` instances, possibly empty.
    """
    species = session.exec(
        select(PokemonSpecies).where(
            PokemonSpecies.national_dex_number == national_dex_number
        )
    ).first()
    if species is None or species.id is None:
        return []
    return get_cards_by_species(session, species.id, limit=limit, offset=offset)
