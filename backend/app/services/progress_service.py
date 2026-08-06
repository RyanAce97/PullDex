"""Service layer for Living Dex progress calculations.

All ownership data is derived from existing tables — no new fields needed.
A species is "owned" if the user has at least one Collection entry for any
Card that references that species.
"""

from sqlmodel import Session, func, select

from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies


def get_total_species_count(session: Session) -> int:
    """Return the total number of Pokémon species in the database."""
    result = session.exec(select(func.count(PokemonSpecies.id)))
    return result.one()


def get_owned_species_ids(session: Session) -> set[int]:
    """Return the set of PokemonSpecies IDs the user owns.

    A species is owned if EITHER:
      - A direct species-level Collection entry exists (pokemon_species_id set), OR
      - A card-level Collection entry exists for any card linked to that species.

    Duplicate entries do not affect the result — each species appears at most once.
    """
    # Direct species-level entries
    direct_stmt = (
        select(Collection.pokemon_species_id)
        .where(Collection.pokemon_species_id.is_not(None))  # type: ignore[union-attr]
    )
    direct_ids = set(session.exec(direct_stmt).all())

    # Card-level entries (existing logic)
    card_stmt = (
        select(Card.pokemon_species_id)
        .join(Collection, Collection.card_id == Card.id)
        .where(Card.pokemon_species_id.is_not(None))  # type: ignore[union-attr]
        .distinct()
    )
    card_ids = set(session.exec(card_stmt).all())

    return direct_ids | card_ids


def get_owned_species_count(session: Session) -> int:
    """Return the number of distinct species the user owns."""
    return len(get_owned_species_ids(session))


def get_missing_species_count(session: Session) -> int:
    """Return the number of species the user does NOT own."""
    total = get_total_species_count(session)
    owned = get_owned_species_count(session)
    return total - owned


def get_completion_percentage(session: Session) -> float:
    """Return the Living Dex completion percentage (0.0–100.0).

    Returns 0.0 if there are no species in the database (avoids division by zero).
    Rounded to one decimal place.
    """
    total = get_total_species_count(session)
    if total == 0:
        return 0.0
    owned = get_owned_species_count(session)
    return round((owned / total) * 100, 1)


def get_progress(session: Session) -> dict:
    """Return a summary dict of Living Dex progress.

    Returns:
        A dict with keys: total_species, owned_species, missing_species,
        completion_percentage.
    """
    total = get_total_species_count(session)
    owned_ids = get_owned_species_ids(session)
    owned = len(owned_ids)
    missing = total - owned
    percentage = round((owned / total) * 100, 1) if total > 0 else 0.0
    return {
        "total_species": total,
        "owned_species": owned,
        "missing_species": missing,
        "completion_percentage": percentage,
    }


def get_missing_species(
    session: Session,
    limit: int = 250,
    offset: int = 0,
) -> list[PokemonSpecies]:
    """Return the list of Pokémon species the user does NOT own.

    Args:
        session: An open SQLModel Session.
        limit:   Maximum number of results to return.
        offset:  Number of results to skip (for pagination).

    Returns:
        A list of :class:`PokemonSpecies` instances that have no matching
        Collection entry, ordered by national dex number.
    """
    owned_ids = get_owned_species_ids(session)

    statement = select(PokemonSpecies).order_by(PokemonSpecies.national_dex_number)  # type: ignore[arg-type]

    if owned_ids:
        statement = statement.where(
            PokemonSpecies.id.not_in(owned_ids)  # type: ignore[union-attr]
        )

    statement = statement.offset(offset).limit(limit)
    return list(session.exec(statement).all())
