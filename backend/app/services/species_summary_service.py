"""Service layer for species summary queries.

Returns one row per Pokémon species with a boolean ownership flag.
A species is "owned" if EITHER:
  - A direct species-level Collection entry exists, OR
  - Any card-level Collection entry exists for a card linked to that species.
"""

from sqlmodel import Session, select

from app.models.pokemon_species import PokemonSpecies
from app.services.progress_service import get_owned_species_ids


def get_species_summary(session: Session) -> list[dict]:
    """Return one row per species with an ownership boolean.

    Uses get_owned_species_ids() which handles both species-level and
    card-level ownership detection.

    Returns:
        A list of dicts with keys: species_id, national_dex_number, name,
        generation, owned.
    """
    owned_ids = get_owned_species_ids(session)

    statement = (
        select(PokemonSpecies)
        .order_by(PokemonSpecies.national_dex_number)  # type: ignore[arg-type]
    )
    species_list = session.exec(statement).all()

    return [
        {
            "species_id": s.id,
            "national_dex_number": s.national_dex_number,
            "name": s.name,
            "generation": s.generation,
            "owned": s.id in owned_ids,
        }
        for s in species_list
    ]
