"""Service layer for set summary queries.

Returns one row per set with species ownership statistics.
Reuses get_owned_species_ids() from progress_service to determine ownership.
"""

from sqlmodel import Session, func, select

from app.models.card import Card
from app.models.set import Set
from app.services.progress_service import get_owned_species_ids


def get_set_summaries(session: Session) -> list[dict]:
    """Return one row per set with species counts and ownership breakdown.

    For each set, calculates:
      - total_species_in_set: distinct species with cards in this set
      - owned_species_in_set: how many of those the user owns
      - missing_species_in_set: total - owned

    Sets with zero Pokémon cards (trainer/energy only) are excluded.

    Returns:
        A list of dicts ordered by set name.
    """
    owned_ids = get_owned_species_ids(session)

    # Get distinct species per set
    statement = (
        select(
            Set.id.label("set_id"),  # type: ignore[attr-defined]
            Set.api_set_id,
            Set.name,
            Set.series,
            Set.release_date,
            func.count(Card.pokemon_species_id.distinct()).label("total_species_in_set"),  # type: ignore[union-attr]
        )
        .join(Card, Card.set_id == Set.id)
        .where(Card.pokemon_species_id.is_not(None))  # type: ignore[union-attr]
        .group_by(Set.id)
        .order_by(Set.name)  # type: ignore[arg-type]
    )

    rows = session.exec(statement).all()  # type: ignore[call-overload]

    # For each set, determine which species are owned
    # We need per-set species IDs to compute owned count
    set_species_stmt = (
        select(Card.set_id, Card.pokemon_species_id)
        .where(Card.pokemon_species_id.is_not(None))  # type: ignore[union-attr]
        .where(Card.set_id.is_not(None))  # type: ignore[union-attr]
        .distinct()
    )
    set_species_rows = session.exec(set_species_stmt).all()  # type: ignore[call-overload]

    # Build a map: set_id -> set of species IDs
    set_species_map: dict[int, set[int]] = {}
    for row in set_species_rows:
        set_id = row.set_id  # type: ignore[attr-defined]
        species_id = row.pokemon_species_id  # type: ignore[attr-defined]
        if set_id not in set_species_map:
            set_species_map[set_id] = set()
        set_species_map[set_id].add(species_id)

    results = []
    for row in rows:
        species_in_set = set_species_map.get(row.set_id, set())
        owned_in_set = len(species_in_set & owned_ids)
        missing_in_set = row.total_species_in_set - owned_in_set

        results.append({
            "set_id": row.set_id,
            "api_set_id": row.api_set_id,
            "name": row.name,
            "series": row.series,
            "release_date": row.release_date,
            "total_species_in_set": row.total_species_in_set,
            "owned_species_in_set": owned_in_set,
            "missing_species_in_set": missing_in_set,
        })

    return results
