"""Pack recommendation engine — V1.

Ranks TCG sets by how many missing Pokémon species they can provide.
Only sets with at least one missing species appear in recommendations.

Scoring:
  1. Primary:   missing_species_count DESC (more missing species = better)
  2. Tie-break: total_cards_in_set ASC    (fewer cards = higher density)
  3. Tie-break: release_date DESC         (newer = easier to find in shops)
"""

from sqlmodel import Session, func, select

from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.progress_service import get_owned_species_ids


def get_set_recommendations(
    session: Session,
    limit: int = 10,
) -> list[dict]:
    """Return sets ranked by how many missing species they can provide.

    Only includes sets that contain at least one card for a missing species.
    Each result includes computed display fields (rank, coverage, density).

    Args:
        session: An open SQLModel Session.
        limit:   Maximum number of recommendations to return.

    Returns:
        A list of dicts with keys: rank, set_id, api_set_id, set_name, series,
        release_date, missing_species_count, total_species_in_set,
        total_cards_in_set, coverage_percentage, missing_species_density_percentage.
    """
    owned_ids = get_owned_species_ids(session)

    # All species IDs in the database.
    all_species_ids_stmt = select(PokemonSpecies.id)
    all_species_ids = set(session.exec(all_species_ids_stmt).all())

    missing_ids = all_species_ids - owned_ids
    total_missing = len(missing_ids)

    if not missing_ids:
        return []

    # Count distinct missing species per set (primary score).
    missing_count = (
        func.count(Card.pokemon_species_id.distinct())  # type: ignore[union-attr]
        .label("missing_species_count")
    )

    # Subquery: total cards in each set (for tie-breaking by density).
    # Separate subquery so the WHERE filter on missing species doesn't affect it.
    total_cards_subq = (
        select(
            Card.set_id,
            func.count(Card.id).label("total_cards_in_set"),
        )
        .where(Card.set_id.is_not(None))  # type: ignore[union-attr]
        .group_by(Card.set_id)
        .subquery()
    )

    # Subquery: total distinct species in each set (including owned ones).
    total_species_subq = (
        select(
            Card.set_id,
            func.count(Card.pokemon_species_id.distinct()).label("total_species_in_set"),  # type: ignore[union-attr]
        )
        .where(Card.set_id.is_not(None))  # type: ignore[union-attr]
        .where(Card.pokemon_species_id.is_not(None))  # type: ignore[union-attr]
        .group_by(Card.set_id)
        .subquery()
    )

    statement = (
        select(
            Set.id.label("set_id"),  # type: ignore[attr-defined]
            Set.api_set_id,
            Set.name.label("set_name"),  # type: ignore[attr-defined]
            Set.series,
            Set.release_date,
            missing_count,
            total_cards_subq.c.total_cards_in_set,
            total_species_subq.c.total_species_in_set,
        )
        .join(Card, Card.set_id == Set.id)
        .join(total_cards_subq, total_cards_subq.c.set_id == Set.id)
        .join(total_species_subq, total_species_subq.c.set_id == Set.id)
        .where(Card.pokemon_species_id.in_(missing_ids))  # type: ignore[union-attr]
        .group_by(
            Set.id,
            total_cards_subq.c.total_cards_in_set,
            total_species_subq.c.total_species_in_set,
        )
        .order_by(
            missing_count.desc(),
            total_cards_subq.c.total_cards_in_set.asc(),
            Set.release_date.desc(),  # type: ignore[union-attr]
        )
        .limit(limit)
    )

    rows = session.exec(statement).all()  # type: ignore[call-overload]

    results = []
    for rank, row in enumerate(rows, start=1):
        coverage = round((row.missing_species_count / total_missing) * 100, 1) if total_missing > 0 else 0.0
        density = round((row.missing_species_count / row.total_cards_in_set) * 100, 1) if row.total_cards_in_set > 0 else 0.0

        results.append({
            "rank": rank,
            "set_id": row.set_id,
            "api_set_id": row.api_set_id,
            "set_name": row.set_name,
            "series": row.series,
            "release_date": row.release_date,
            "missing_species_count": row.missing_species_count,
            "total_species_in_set": row.total_species_in_set,
            "total_cards_in_set": row.total_cards_in_set,
            "coverage_percentage": coverage,
            "missing_species_density_percentage": density,
        })

    return results


def get_missing_species_in_set(
    session: Session,
    set_id: int,
) -> list[PokemonSpecies]:
    """Return the specific missing species that have cards in the given set.

    Useful for drill-down: "What would I gain from buying this set?"

    Args:
        session: An open SQLModel Session.
        set_id:  The local primary key of the set.

    Returns:
        A list of :class:`PokemonSpecies` instances the user does not own
        but which have at least one card in this set, ordered by dex number.
    """
    owned_ids = get_owned_species_ids(session)

    # Species IDs that have cards in this set.
    species_in_set_stmt = (
        select(Card.pokemon_species_id)
        .where(Card.set_id == set_id)
        .where(Card.pokemon_species_id.is_not(None))  # type: ignore[union-attr]
        .distinct()
    )
    species_in_set = set(session.exec(species_in_set_stmt).all())

    missing_in_set = species_in_set - owned_ids

    if not missing_in_set:
        return []

    statement = (
        select(PokemonSpecies)
        .where(PokemonSpecies.id.in_(missing_in_set))  # type: ignore[union-attr]
        .order_by(PokemonSpecies.national_dex_number)  # type: ignore[arg-type]
    )
    return list(session.exec(statement).all())
