"""Importer for Pokémon TCG set data from the Pokémon TCG API.

Fetches every set from /sets and upserts them into the local Set table.
Safe to re-run: existing records are updated, new records are inserted,
and nothing is duplicated.
"""

from datetime import date

from sqlmodel import Session, select

from app.database import get_session_context
from app.models.set import Set
from app.services.api.pokemon_tcg_client import PokemonTCGClient


def parse_release_date(value: str | None) -> date | None:
    """Parse a Pokémon TCG API release date string into a Python date.

    The API returns dates as ``"YYYY/MM/DD"`` strings.

    Args:
        value: Date string, e.g. ``"2010/11/03"``, or None / empty string.

    Returns:
        A :class:`datetime.date` object, or ``None`` if the value is missing
        or cannot be parsed.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value.replace("/", "-"))
    except ValueError:
        return None


def upsert_set(session: Session, data: dict) -> Set:
    """Insert or update a single Set row from a TCG API set object.

    Uses ``api_set_id`` (the API's ``id`` field) as the unique external
    identifier to detect whether the record already exists.

    Args:
        session: An open SQLModel Session.
        data:    A single set object from the Pokémon TCG API, e.g.:
                 ``{"id": "sv1", "name": "Scarlet & Violet",
                    "series": "Scarlet & Violet", "releaseDate": "2023/03/31"}``.

    Returns:
        The created or updated :class:`Set` instance.
    """
    api_set_id: str = data["id"]
    name: str = data["name"]
    series: str = data["series"]
    release_date: date | None = parse_release_date(data.get("releaseDate"))

    # Look up by the stable external identifier.
    existing = session.exec(
        select(Set).where(Set.api_set_id == api_set_id)
    ).first()

    if existing:
        existing.name = name
        existing.series = series
        existing.release_date = release_date
        session.add(existing)
        return existing

    tcg_set = Set(
        api_set_id=api_set_id,
        name=name,
        series=series,
        release_date=release_date,
    )
    session.add(tcg_set)
    return tcg_set


def import_all_sets(page_size: int = 50) -> None:
    """Fetch all sets from the Pokémon TCG API and upsert into the database.

    The TCG API returns all sets in a single page at the default page size
    of 50 (there are currently ~163 sets), but this function pages through
    the full result set to be future-proof.  Commits once per page.

    Args:
        page_size: Number of sets to request per page (max 50).
    """
    with PokemonTCGClient() as api, get_session_context() as session:
        page_number = 1
        total_imported = 0

        while True:
            response = api.get_sets(page=page_number, page_size=page_size)
            sets = response.get("data", [])

            if not sets:
                break

            for set_data in sets:
                upsert_set(session, set_data)

            session.commit()
            total_imported += len(sets)
            total_count = response.get("totalCount", "?")
            print(f"Imported {total_imported} / {total_count} sets")

            # Stop when the current page returned fewer results than requested
            # (last page) or when we have imported everything.
            if len(sets) < page_size:
                break

            page_number += 1

    print(f"Done. Total sets imported: {total_imported}")


if __name__ == "__main__":
    import_all_sets()
