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


def search_cards_full(
    session: Session,
    query: str,
    limit: int = 50,
) -> list[dict]:
    """Search cards across multiple fields, returning rich results with context.

    Matches against:
      - Pokémon species name (ilike)
      - Card api_card_id (ilike)
      - Card card_number (ilike)
      - Set api_set_id / set code (ilike)
      - Set name (ilike)

    Results are ordered to prioritize:
      1. Exact card_number or api_card_id matches
      2. Set code matches
      3. Species name matches

    Args:
        session: An open SQLModel Session.
        query:   Search string (case-insensitive, substring).
        limit:   Maximum results to return.

    Returns:
        A list of dicts with card details + denormalized species/set info.
    """
    from sqlalchemy import case as sa_case, literal

    term = f"%{query}%"

    # Priority scoring: exact-ish matches rank higher
    # card_number or api_card_id match → priority 1
    # set code match → priority 2
    # species name or set name match → priority 3
    priority = sa_case(
        (Card.card_number.ilike(term), literal(1)),  # type: ignore[union-attr]
        (Card.api_card_id.ilike(term), literal(1)),  # type: ignore[union-attr]
        (Set.api_set_id.ilike(term), literal(2)),  # type: ignore[union-attr]
        else_=literal(3),
    ).label("priority")

    statement = (
        select(
            Card.id,
            Card.api_card_id,
            Card.card_number,
            Card.rarity,
            Card.image_url,
            PokemonSpecies.name.label("pokemon_name"),  # type: ignore[attr-defined]
            PokemonSpecies.national_dex_number,
            Set.name.label("set_name"),  # type: ignore[attr-defined]
            Set.api_set_id.label("set_code"),  # type: ignore[attr-defined]
            priority,
        )
        .join(PokemonSpecies, Card.pokemon_species_id == PokemonSpecies.id, isouter=True)
        .join(Set, Card.set_id == Set.id, isouter=True)
        .where(
            (PokemonSpecies.name.ilike(term))  # type: ignore[union-attr]
            | (Card.api_card_id.ilike(term))  # type: ignore[union-attr]
            | (Card.card_number.ilike(term))  # type: ignore[union-attr]
            | (Set.api_set_id.ilike(term))  # type: ignore[union-attr]
            | (Set.name.ilike(term))  # type: ignore[union-attr]
        )
        .order_by(priority, PokemonSpecies.name, Card.card_number)  # type: ignore[arg-type]
        .limit(limit)
    )

    rows = session.exec(statement).all()  # type: ignore[call-overload]

    return [
        {
            "id": row.id,
            "api_card_id": row.api_card_id,
            "card_number": row.card_number,
            "rarity": row.rarity,
            "image_url": row.image_url,
            "pokemon_name": row.pokemon_name,
            "national_dex_number": row.national_dex_number,
            "set_name": row.set_name,
            "set_code": row.set_code,
        }
        for row in rows
    ]
