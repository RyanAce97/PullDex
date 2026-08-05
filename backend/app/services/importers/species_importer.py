"""Importer for Pokémon species data from the PokéAPI.

Fetches every species from /pokemon-species and upserts them into the
local PokemonSpecies table.  Safe to re-run: existing records are updated,
new records are inserted, and nothing is duplicated.
"""

import re

from sqlmodel import Session, select

from app.database import get_session_context
from app.models.pokemon_species import PokemonSpecies
from app.services.api.pokeapi_client import PokeApiClient

# PokéAPI returns generation names like "generation-i", "generation-iv".
# This table converts the Roman numeral suffix to an integer.
_ROMAN_TO_INT: dict[str, int] = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
}

# Matches the trailing Roman numeral in a generation name, e.g. "generation-iv" → "iv".
_GENERATION_RE = re.compile(r"generation-([a-z]+)$")


def parse_generation(generation_name: str) -> int | None:
    """Parse a PokéAPI generation name into an integer.

    Args:
        generation_name: e.g. "generation-iv"

    Returns:
        The generation number (1–9), or None if the name cannot be parsed.
    """
    match = _GENERATION_RE.search(generation_name)
    if not match:
        return None
    return _ROMAN_TO_INT.get(match.group(1))


def upsert_species(session: Session, data: dict) -> PokemonSpecies:
    """Insert or update a single PokémonSpecies row from a detail API response.

    Args:
        session: An open SQLModel Session.
        data:    Parsed JSON from /pokemon-species/{name}.

    Returns:
        The created or updated PokemonSpecies instance.
    """
    national_dex_number: int = data["id"]
    name: str = data["name"]
    generation: int | None = None

    generation_data = data.get("generation")
    if generation_data:
        generation = parse_generation(generation_data.get("name", ""))

    # Look up by national dex number — the stable external identifier.
    existing = session.exec(
        select(PokemonSpecies).where(
            PokemonSpecies.national_dex_number == national_dex_number
        )
    ).first()

    if existing:
        existing.name = name
        existing.generation = generation
        session.add(existing)
        return existing

    species = PokemonSpecies(
        national_dex_number=national_dex_number,
        name=name,
        generation=generation,
    )
    session.add(species)
    return species


def import_all_species(page_size: int = 100) -> None:
    """Fetch all Pokémon species from the PokéAPI and upsert into the database.

    Pages through /pokemon-species to collect every species name, then
    fetches the detail endpoint for each to get the national dex number
    and generation.  Commits in batches of one page to limit memory use.

    Args:
        page_size: Number of species to request per page (max 100).
    """
    with PokeApiClient() as api, get_session_context() as session:
        offset = 0
        total_imported = 0

        while True:
            page = api.get_pokemon_species_page(limit=page_size, offset=offset)
            results = page.get("results", [])

            if not results:
                break

            for entry in results:
                detail = api.get_pokemon_species(entry["name"])
                upsert_species(session, detail)

            session.commit()
            total_imported += len(results)
            print(f"Imported {total_imported} / {page['count']} species")

            if page.get("next") is None:
                break

            offset += page_size

    print(f"Done. Total species imported: {total_imported}")


if __name__ == "__main__":
    import_all_species()
