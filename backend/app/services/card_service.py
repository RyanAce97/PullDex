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


def search_cards_paginated(
    session: Session,
    query: str | None = None,
    species: str | None = None,
    set_name: str | None = None,
    rarity: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """Paginated card search with optional filters.

    Filters are combined with AND logic. At least one of ``query`` or a filter
    must be provided (enforced at the router level).

    Args:
        session:   An open SQLModel Session.
        query:     Free-text search across name, card number, set code, set name.
        species:   Filter by Pokémon species name (substring match).
        set_name:  Filter by set name or set code (substring match).
        rarity:    Filter by exact rarity value.
        page:      Page number (1-indexed).
        page_size: Number of results per page.

    Returns:
        A tuple of (results list of dicts, total matching count).
    """
    from sqlalchemy import case as sa_case, func, literal

    base = (
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
        )
        .join(PokemonSpecies, Card.pokemon_species_id == PokemonSpecies.id, isouter=True)
        .join(Set, Card.set_id == Set.id, isouter=True)
    )

    # Build WHERE conditions (AND logic)
    conditions = []

    if query:
        term = f"%{query}%"
        conditions.append(
            (PokemonSpecies.name.ilike(term))  # type: ignore[union-attr]
            | (Card.api_card_id.ilike(term))  # type: ignore[union-attr]
            | (Card.card_number.ilike(term))  # type: ignore[union-attr]
            | (Set.api_set_id.ilike(term))  # type: ignore[union-attr]
            | (Set.name.ilike(term))  # type: ignore[union-attr]
        )

    if species:
        species_term = f"%{species}%"
        conditions.append(PokemonSpecies.name.ilike(species_term))  # type: ignore[union-attr]

    if set_name:
        set_term = f"%{set_name}%"
        conditions.append(
            (Set.name.ilike(set_term))  # type: ignore[union-attr]
            | (Set.api_set_id.ilike(set_term))  # type: ignore[union-attr]
        )

    if rarity:
        conditions.append(Card.rarity == rarity)

    for condition in conditions:
        base = base.where(condition)

    # Count total matching rows
    count_stmt = select(func.count()).select_from(base.subquery())
    total = session.exec(count_stmt).one()  # type: ignore[call-overload]

    # Add ordering
    if query:
        term = f"%{query}%"
        priority = sa_case(
            (Card.card_number.ilike(term), literal(1)),  # type: ignore[union-attr]
            (Card.api_card_id.ilike(term), literal(1)),  # type: ignore[union-attr]
            (Set.api_set_id.ilike(term), literal(2)),  # type: ignore[union-attr]
            else_=literal(3),
        )
        base = base.order_by(priority, PokemonSpecies.name, Card.card_number)  # type: ignore[arg-type]
    else:
        base = base.order_by(PokemonSpecies.name, Set.name, Card.card_number)  # type: ignore[arg-type]

    # Pagination
    offset = (page - 1) * page_size
    base = base.offset(offset).limit(page_size)

    rows = session.exec(base).all()  # type: ignore[call-overload]

    items = [
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

    return items, total


def get_filter_options(session: Session) -> dict:
    """Return available filter values for the card search UI.

    Currently returns distinct non-null rarity values sorted alphabetically.
    """
    from sqlalchemy import func  # noqa: F811

    stmt = (
        select(Card.rarity)
        .where(Card.rarity.is_not(None))  # type: ignore[union-attr]
        .distinct()
        .order_by(Card.rarity)
    )
    rarities = list(session.exec(stmt).all())
    return {"rarities": rarities}
