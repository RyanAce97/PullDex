"""Service layer for the digital binder.

The binder represents the National Pokédex as fixed slots (#1–#1025).
Each slot corresponds to one species. The slot state depends on ownership:

- NOT owned: empty pocket
- Owned via species-level only (no cards): owned placeholder, no card image
- Owned with cards: shows the selected binder card (or first owned card as fallback)

Only cards actually owned by the active profile are ever displayed.
"""

import math

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.profile_service import get_active_profile, get_active_profile_id

NATIONAL_DEX_COUNT = 1025


def get_binder_page(
    session: Session,
    *,
    page: int = 1,
    page_size: int | None = None,
) -> dict:
    """Return a page of National Dex binder slots for the active profile.

    Each slot represents one species and has three possible states:
    - owned=False: not owned at all
    - owned=True, has_card=False: species-level ownership only, no card image
    - owned=True, has_card=True: card ownership with binder card shown
    """
    profile = get_active_profile(session)
    profile_id = profile.id

    if page_size is None:
        page_size = profile.binder_rows * profile.binder_columns

    total_pages = math.ceil(NATIONAL_DEX_COUNT / page_size)

    # Calculate the dex range for this page
    start_dex = (page - 1) * page_size + 1
    end_dex = min(start_dex + page_size - 1, NATIONAL_DEX_COUNT)

    # Get species for this page
    species_list = list(session.exec(
        select(PokemonSpecies)
        .where(
            PokemonSpecies.national_dex_number >= start_dex,
            PokemonSpecies.national_dex_number <= end_dex,
        )
        .order_by(PokemonSpecies.national_dex_number)  # type: ignore[arg-type]
    ).all())

    species_by_dex: dict[int, PokemonSpecies] = {}
    species_ids: list[int] = []
    for s in species_list:
        species_by_dex[s.national_dex_number] = s
        if s.id is not None:
            species_ids.append(s.id)

    # Find species owned via species-level entries
    owned_via_species: set[int] = set()
    if species_ids:
        direct_stmt = (
            select(Collection.pokemon_species_id)
            .where(
                Collection.profile_id == profile_id,
                Collection.pokemon_species_id.in_(species_ids),  # type: ignore[union-attr]
                Collection.card_id.is_(None),  # type: ignore[union-attr]
            )
        )
        owned_via_species = set(session.exec(direct_stmt).all())

    # Find species owned via card-level entries (ONLY cards this profile owns)
    owned_via_cards: set[int] = set()
    if species_ids:
        card_stmt = (
            select(Card.pokemon_species_id)
            .join(Collection, Collection.card_id == Card.id)
            .where(
                Collection.profile_id == profile_id,
                Card.pokemon_species_id.in_(species_ids),  # type: ignore[union-attr]
            )
            .distinct()
        )
        owned_via_cards = set(session.exec(card_stmt).all())

    owned_species_ids = owned_via_species | owned_via_cards
    # Species that have card-level entries (vs species-only)
    species_with_cards = owned_via_cards

    # Get the binder card for each species with cards.
    # Priority: is_binder_card=True first, then fallback to first owned card.
    binder_card_by_species: dict[int, dict] = {}
    if species_with_cards:
        # Get all owned card entries for these species with card details
        owned_cards_stmt = (
            select(
                Card.id,
                Card.api_card_id,
                Card.card_number,
                Card.rarity,
                Card.image_url,
                Card.pokemon_species_id,
                Set.name.label("set_name"),  # type: ignore[attr-defined]
                Set.api_set_id.label("set_code"),  # type: ignore[attr-defined]
                Collection.is_binder_card,
                Collection.quantity,
            )
            .join(Collection, Collection.card_id == Card.id)
            .join(Set, Card.set_id == Set.id, isouter=True)
            .where(
                Collection.profile_id == profile_id,
                Card.pokemon_species_id.in_(species_with_cards),  # type: ignore[union-attr]
            )
            .order_by(
                Collection.is_binder_card.desc(),  # type: ignore[union-attr]
                Card.card_number,
                Card.id,
            )
        )
        all_owned_cards = list(session.exec(owned_cards_stmt).all())  # type: ignore[call-overload]

        # Pick one card per species: binder_card=True first, then first by ordering
        for row in all_owned_cards:
            sp_id = row.pokemon_species_id
            if sp_id not in binder_card_by_species:
                binder_card_by_species[sp_id] = {
                    "id": row.id,
                    "api_card_id": row.api_card_id,
                    "card_number": row.card_number,
                    "rarity": row.rarity,
                    "image_url": row.image_url,
                    "set_name": row.set_name,
                    "set_code": row.set_code,
                    "quantity": row.quantity,
                }

    # Get total card quantity per species for the badge
    quantity_by_species: dict[int, int] = {}
    if species_with_cards:
        qty_stmt = (
            select(
                Card.pokemon_species_id,
                func.sum(Collection.quantity).label("total_qty"),
            )
            .join(Collection, Collection.card_id == Card.id)
            .where(
                Collection.profile_id == profile_id,
                Card.pokemon_species_id.in_(species_with_cards),  # type: ignore[union-attr]
            )
            .group_by(Card.pokemon_species_id)
        )
        for row in session.exec(qty_stmt).all():  # type: ignore[call-overload]
            quantity_by_species[row.pokemon_species_id] = row.total_qty

    # Build the slots array
    slots = []
    for dex_num in range(start_dex, end_dex + 1):
        species = species_by_dex.get(dex_num)
        if species is None:
            slots.append({
                "dex_number": dex_num,
                "species_name": None,
                "species_id": None,
                "owned": False,
                "has_card": False,
                "card": None,
                "total_cards": 0,
            })
            continue

        is_owned = species.id in owned_species_ids
        has_card = species.id in species_with_cards
        card = binder_card_by_species.get(species.id) if has_card else None  # type: ignore
        total_cards = quantity_by_species.get(species.id, 0) if has_card else 0  # type: ignore

        slots.append({
            "dex_number": dex_num,
            "species_name": species.name,
            "species_id": species.id,
            "owned": is_owned,
            "has_card": has_card,
            "card": card,
            "total_cards": total_cards,
        })

    # Pad remaining slots on the last page
    while len(slots) < page_size:
        slots.append({
            "dex_number": None,
            "species_name": None,
            "species_id": None,
            "owned": False,
            "has_card": False,
            "card": None,
            "total_cards": 0,
        })

    return {
        "page": page,
        "page_size": page_size,
        "total_species": NATIONAL_DEX_COUNT,
        "total_pages": total_pages,
        "slots": slots,
    }


# ---------------------------------------------------------------------------
# Binder card selection
# ---------------------------------------------------------------------------

def set_binder_card(session: Session, collection_entry_id: int) -> bool:
    """Select a card-level collection entry as the binder card for its species.

    Deselects any other binder card for the same species+profile.

    Returns True if successful, False if entry not found or not a card entry.
    """
    entry = session.get(Collection, collection_entry_id)
    if entry is None or entry.card_id is None:
        return False

    profile_id = entry.profile_id

    # Find the species for this card
    card = session.get(Card, entry.card_id)
    if card is None or card.pokemon_species_id is None:
        return False

    species_id = card.pokemon_species_id

    # Deselect all other binder cards for this species+profile
    other_entries = session.exec(
        select(Collection)
        .join(Card, Collection.card_id == Card.id)
        .where(
            Collection.profile_id == profile_id,
            Card.pokemon_species_id == species_id,
            Collection.is_binder_card == True,  # noqa: E712
        )
    ).all()
    for other in other_entries:
        other.is_binder_card = False
        session.add(other)

    # Select this one
    entry.is_binder_card = True
    session.add(entry)
    session.commit()
    return True


def unset_binder_card(session: Session, collection_entry_id: int) -> bool:
    """Remove binder card selection from a collection entry.

    Returns True if successful.
    """
    entry = session.get(Collection, collection_entry_id)
    if entry is None:
        return False

    entry.is_binder_card = False
    session.add(entry)
    session.commit()
    return True


def auto_select_binder_card_for_species(
    session: Session, profile_id: int, species_id: int
) -> None:
    """Auto-select a binder card if only one card entry exists for the species.

    Called after a card removal to maintain a valid binder state.
    """
    remaining = session.exec(
        select(Collection)
        .join(Card, Collection.card_id == Card.id)
        .where(
            Collection.profile_id == profile_id,
            Card.pokemon_species_id == species_id,
            Collection.card_id.is_not(None),  # type: ignore[union-attr]
        )
    ).all()

    if len(remaining) == 1:
        # Only one card left — auto-select it
        remaining[0].is_binder_card = True
        session.add(remaining[0])
        session.commit()
    elif len(remaining) == 0:
        # No cards left — nothing to do
        pass
    else:
        # Multiple remain — check if any is already selected
        has_selected = any(e.is_binder_card for e in remaining)
        if not has_selected:
            # Select the first one as fallback
            remaining[0].is_binder_card = True
            session.add(remaining[0])
            session.commit()
