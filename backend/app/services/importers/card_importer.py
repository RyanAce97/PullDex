"""Importer for Pokémon TCG card data from the Pokémon TCG API.

Fetches cards from /cards and upserts them into the local Card table.
Safe to re-run: existing records are updated, new records are inserted,
and nothing is duplicated.

Set and PokémonSpecies records must already exist in the database before
running this importer — run set_importer and species_importer first.
"""

import re

from sqlmodel import Session, select

from app.database import get_session_context
from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.api.pokemon_tcg_client import PokemonTCGClient


# ---------------------------------------------------------------------------
# TCG card name suffixes to strip when matching against species names.
# Order matters: longer suffixes must come before shorter ones to avoid
# partial matches (e.g., "VSTAR" before "V").
# ---------------------------------------------------------------------------
_TCG_SUFFIXES = [
    " VSTAR",
    " VMAX",
    " BREAK",
    " GX",
    " EX",
    " ex",
    " V",
    "-EX",
    "-GX",
    " δ",
    " ◇",
    " FB",
    " GL",
    " G",
    " C",
    " LV.X",
    " Prism Star",
    " Star",
    " ☆",
]

# Known card names that should NOT be mapped to any species despite having
# supertype=Pokémon in the API. These are typically Fossil/Item cards that
# function as Pokémon during gameplay.
_EXCLUDED_CARD_NAMES: set[str] = {
    "buried fossil",
    "mysterious fossil",
    "root fossil",
    "claw fossil",
}

# Special mappings for Pokémon with form names in the TCG that differ from
# the species name in the PokéAPI. Maps normalized card name → species name.
_FORM_MAPPINGS: dict[str, str] = {
    "teal mask ogerpon": "ogerpon",
    "hearthflame mask ogerpon": "ogerpon",
    "wellspring mask ogerpon": "ogerpon",
    "cornerstone mask ogerpon": "ogerpon",
}


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


def normalize_card_name(card_name: str) -> str:
    """Normalize a TCG card name to a species-matching form.

    Strips known TCG suffixes (ex, EX, V, VMAX, VSTAR, GX, etc.),
    converts to lowercase, and replaces spaces with hyphens to match
    the PokéAPI species naming convention.

    Examples:
        "Iron Boulder ex"  → "iron-boulder"
        "Raging Bolt ex"   → "raging-bolt"
        "Pikachu VMAX"     → "pikachu"
        "Okidogi"          → "okidogi"
        "Teal Mask Ogerpon ex" → "teal-mask-ogerpon"
    """
    name = card_name.strip()

    # Strip TCG suffixes (case-sensitive matching)
    for suffix in _TCG_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
            break

    # Lowercase and replace spaces with hyphens
    return name.lower().replace(" ", "-")


def _resolve_species_by_name(session: Session, card_name: str) -> int | None:
    """Attempt to resolve a species ID by matching the card name.

    This is the fallback used when nationalPokedexNumbers is not available.
    Uses controlled name matching with suffix stripping and form handling.

    Returns the species ID if a confident match is found, else None.
    """
    normalized = normalize_card_name(card_name)

    # Check exclusions
    if normalized.replace("-", " ") in _EXCLUDED_CARD_NAMES:
        return None

    # Check form mappings first
    normalized_with_spaces = normalized.replace("-", " ")
    if normalized_with_spaces in _FORM_MAPPINGS:
        target_name = _FORM_MAPPINGS[normalized_with_spaces]
        result = session.exec(
            select(PokemonSpecies).where(PokemonSpecies.name == target_name)
        ).first()
        return result.id if result else None

    # Direct exact match against species name
    result = session.exec(
        select(PokemonSpecies).where(PokemonSpecies.name == normalized)
    ).first()
    if result:
        return result.id

    return None


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

    Species resolution priority:
    1. nationalPokedexNumbers (dex number lookup — authoritative)
    2. Name-based fallback for Pokémon cards without dex numbers

    Trainer and energy cards (supertype != "Pokémon") are never matched
    by name and always have ``pokemon_species_id = None``.

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

    # Species resolution: dex number first, then name fallback
    dex_numbers: list[int] = data.get("nationalPokedexNumbers") or []
    national_dex_number: int | None = dex_numbers[0] if dex_numbers else None
    species_id = _resolve_species_id(session, national_dex_number)

    # Fallback: name-based matching for Pokémon cards without dex numbers
    if species_id is None and data.get("supertype") == "Pokémon":
        card_name = data.get("name", "")
        if card_name:
            species_id = _resolve_species_by_name(session, card_name)

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


def import_all_cards(page_size: int = 250, start_page: int = 1) -> None:
    """Fetch all cards from the Pokémon TCG API and upsert into the database.

    Pages through /cards using 1-based page numbers until the API returns
    fewer results than requested.  Commits once per page to limit memory use.

    Set and species records should already exist — unresolved foreign keys
    are stored as None rather than raising an error, so the importer is
    tolerant of a partially-populated database.

    Args:
        page_size:  Number of cards to request per page (max 250).
        start_page: 1-based page number to begin importing from.  Set this
                    to resume a previously interrupted import.
    """
    with PokemonTCGClient() as api, get_session_context() as session:
        page_number = start_page
        total_imported = 0

        while True:
            print(f"Fetching page {page_number}...")
            response = api.get_cards(page=page_number, page_size=page_size)
            cards = response.get("data", [])

            if not cards:
                break

            for card_data in cards:
                upsert_card(session, card_data)

            session.commit()
            total_imported += len(cards)
            total_count = response.get("totalCount", "?")
            print(f"Imported {total_imported} cards this run (total in DB may be higher) / {total_count} total")

            if len(cards) < page_size:
                break

            page_number += 1

    print(f"Done. Cards imported this run: {total_imported}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import Pokémon TCG cards into PullDex.")
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        metavar="N",
        help="Page number to start importing from (default: 1).",
    )
    args = parser.parse_args()
    import_all_cards(start_page=args.start_page)
