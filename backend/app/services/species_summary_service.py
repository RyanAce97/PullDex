"""Service layer for species summary queries.

Returns one row per Pokémon species with a boolean ownership flag.
A species is "owned" if the user has at least one collection entry
for any card linked to that species.
"""

from sqlmodel import Session, func, select

from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies


def get_species_summary(session: Session) -> list[dict]:
    """Return one row per species with an ownership boolean.

    The query:
      - LEFT JOINs cards and collection to detect ownership
      - Groups by species
      - Orders by national dex number

    Returns:
        A list of dicts with keys: species_id, national_dex_number, name,
        generation, owned.
    """
    # A species is owned if any of its cards appear in the collection.
    owned_flag = (
        func.count(Collection.id).label("owned_count")
    )

    statement = (
        select(
            PokemonSpecies.id.label("species_id"),  # type: ignore[attr-defined]
            PokemonSpecies.national_dex_number,
            PokemonSpecies.name,
            PokemonSpecies.generation,
            owned_flag,
        )
        .outerjoin(Card, Card.pokemon_species_id == PokemonSpecies.id)
        .outerjoin(Collection, Collection.card_id == Card.id)
        .group_by(PokemonSpecies.id)
        .order_by(PokemonSpecies.national_dex_number)  # type: ignore[arg-type]
    )

    rows = session.exec(statement).all()  # type: ignore[call-overload]

    return [
        {
            "species_id": row.species_id,
            "national_dex_number": row.national_dex_number,
            "name": row.name,
            "generation": row.generation,
            "owned": row.owned_count > 0,
        }
        for row in rows
    ]
