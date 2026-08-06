"""Service layer for PokemonSpecies queries.

Provides read functions used by API routes and other consumers.
All functions accept an open SQLModel Session and return model instances
or lists — no HTTP concerns live here.
"""

from sqlmodel import Session, select

from app.models.pokemon_species import PokemonSpecies


def get_species_by_id(session: Session, species_id: int) -> PokemonSpecies | None:
    """Return a single PokemonSpecies by its local primary key, or None.

    Args:
        session:    An open SQLModel Session.
        species_id: The local integer primary key.

    Returns:
        The matching :class:`PokemonSpecies`, or ``None``.
    """
    return session.get(PokemonSpecies, species_id)


def get_species_by_dex_number(session: Session, national_dex_number: int) -> PokemonSpecies | None:
    """Return a single PokemonSpecies by its National Pokédex number, or None.

    Args:
        session:             An open SQLModel Session.
        national_dex_number: National Pokédex number, e.g. 25 for Pikachu.

    Returns:
        The matching :class:`PokemonSpecies`, or ``None``.
    """
    return session.exec(
        select(PokemonSpecies).where(
            PokemonSpecies.national_dex_number == national_dex_number
        )
    ).first()


def get_all_species(
    session: Session,
    limit: int = 250,
    offset: int = 0,
) -> list[PokemonSpecies]:
    """Return all species, paginated.

    Args:
        session: An open SQLModel Session.
        limit:   Maximum number of results to return.
        offset:  Number of results to skip (for pagination).

    Returns:
        A list of :class:`PokemonSpecies` instances, possibly empty.
    """
    statement = select(PokemonSpecies).offset(offset).limit(limit)
    return list(session.exec(statement).all())


def search_species_by_name(
    session: Session,
    name: str,
    limit: int = 50,
    offset: int = 0,
) -> list[PokemonSpecies]:
    """Return species whose name contains the search term (case-insensitive).

    Args:
        session: An open SQLModel Session.
        name:    Substring to search for (case-insensitive).
        limit:   Maximum number of results to return.
        offset:  Number of results to skip (for pagination).

    Returns:
        A list of matching :class:`PokemonSpecies` instances, possibly empty.
    """
    term = f"%{name}%"
    statement = (
        select(PokemonSpecies)
        .where(PokemonSpecies.name.ilike(term))  # type: ignore[union-attr]
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())
