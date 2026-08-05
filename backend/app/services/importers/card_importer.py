"""Importer for Pokémon TCG card data from the Pokémon TCG API.

Fetches cards from /cards and upserts them into the local Card table.
Safe to re-run: existing records are updated, new records are inserted,
and nothing is duplicated.

Set and PokémonSpecies records must already exist in the database before
running this importer — run set_importer and species_importer first.
"""

from sqlmodel import Session, select

from app.database import get_session_context
from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.api.pokemon_tcg_client import PokemonTCGClient


def _resolve_set_id(session: Session, api_set_id: str | None) -> int | None:
    """Return the local Set.id for the given api_set_id, or None."""
    if not api_set_id:
        return None
    result = session.exec(
        select(Set).where(Set.api_set_id == api_set_id)
    ).first()
    return result.id if result else None


def _resolve_species_id(session: Session, national_dex_number: int | None) -> int | None:
    """Return the local PokemonSpecies.id for the given dex number, or None."""
    if national_dex_number is None:
        return None
    result = session.exec(
        select(PokemonSpecies).where(
            PokemonSpecies.national_dex_number == national_dex_number
        )
    ).first()
    return result.id if result else None


def _pick_image_url(images: dict | None) -> str | None:
    """Return the best available image URL from the API images object.

    Prefers the large image; falls back to small if large is absent.

    Args:
        images: The ``images`` dict from an API card object, e.g.
                ``{"small": "https://...", "large": "https://"}``,
                or None.

    Returns:
        A URL string, or None if no image is available.
    """
    if not images:
        return None
    return images.get("large") or images.get("small")


def upsert_card(session: Session, data: dict) -> Card:
    """Insert or update a single Card row from a TCG API card object.

    Uses ``api_card_id`` (the API's ``id`` field) as the unique external
    identifier.  Set and species links are resolved by looking up the
    corresponding local rows.

    Trainer and energy cards typically have no ``nationalPokedexNumbers``
    entry; ``pokemon_species_id`` is left as ``None`` for those cards.

    Args:
        session: An open SQLModel Session.
        data:    A single card object from the Pokémon TCG API.

    Returns:
        The created or updated :class:`Card` instance.
    """
    api_card_id: str = data["id"]

    # Resolve foreign keys from related local tables.
    api_set_id: str | None = (data.get("set") or {}).get("id")
    set_id = _resolve_set_id(session, api_set_id)

    dex_numbers: list[int] = data.get("nationalPokedexNumbers") or []
    national_dex_number: int | None = dex_numbers[0] if dex_numbers else None
    species_id = _resolve_species_id(session, national_dex_number)

    card_number: str | None = data.get("number")
    rarity: str | None = data.get("rarity")
    image_url: str | None = _pick_image_url(data.get("images"))

    existing = session.exec(
        select(Card).where(Card.api_card_id == api_card_id)
    ).first()

    if existing:
        existing.set_id = set_id
        existing.pokemon_species_id = species_id
        existing.card_number = card_number
        existing.rarity = rarity
        existing.image_url = image_url
        session.add(existing)
        return existing

    card = Card(
        api_card_id=api_card_id,
        set_id=set_id,
        pokemon_species_id=species_id,
        card_number=card_number,
        rarity=rarity,
        image_url=image_url,
    )
    session.add(card)
    return card


def import_all_cards(page_size: int = 250) -> None:
    """Fetch all cards from the Pokémon TCG API and upsert into the database.

    Pages through /cards using 1-based page numbers until the API returns
    fewer results than requested.  Commits once per page to limit memory use.

    Set and species records should already exist — unresolved foreign keys
    are stored as None rather than raising an error, so the importer is
    tolerant of a partially-populated database.

    Args:
        page_size: Number of cards to request per page (max 250).
    """
    with PokemonTCGClient() as api, get_session_context() as session:
        page_number = 1
        total_imported = 0

        while True:
            response = api.get_cards(page=page_number, page_size=page_size)
            cards = response.get("data", [])

            if not cards:
                break

            for card_data in cards:
                upsert_card(session, card_data)

            session.commit()
            total_imported += len(cards)
            total_count = response.get("totalCount", "?")
            print(f"Imported {total_imported} / {total_count} cards")

            if len(cards) < page_size:
                break

            page_number += 1

    print(f"Done. Total cards imported: {total_imported}")


if __name__ == "__main__":
    import_all_cards()
