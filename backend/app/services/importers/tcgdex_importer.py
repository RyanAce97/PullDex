"""Supplementary importer that fills card/set gaps from TCGdex.

TCGdex has sets and cards that the Pokémon TCG API does not, particularly:
- MEP Black Star Promos (includes First Partner Illustration Collection)
- Missing SVP cards (#208+)
- Promos-A (Pokémon TCG Pocket promos)

This importer is:
- Additive: never modifies existing cards/sets from the primary source
- Idempotent: safe to run repeatedly
- Non-destructive: never touches collection, profiles, or binder data
"""

from dataclasses import dataclass, field
from datetime import date

from sqlmodel import Session, select

from app.database import get_session_context
from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.api.tcgdex_client import TCGdexClient


# ---------------------------------------------------------------------------
# ID Mapping: TCGdex set IDs → Pokémon TCG API set IDs
# ---------------------------------------------------------------------------

# Maps TCGdex set IDs to the equivalent Pokémon TCG API set IDs for sets
# that exist in both sources. Used for deduplication.
_TCGDEX_TO_API_SET_ID: dict[str, str] = {
    "me02.5": "me2pt5",
    "me02": "me2",
    "me01.5": "me1pt5",
    "me01": "me1",
    "sv08.5": "sv8pt5",
    "sv08": "sv8",
    "sv07": "sv7",
    "sv06.5": "sv6pt5",
    "sv06": "sv6",
    "sv05": "sv5",
    "sv04.5": "sv4pt5",
    "sv04": "sv4",
    "sv03.5": "sv3pt5",
    "sv03": "sv3",
    "sv02": "sv2",
    "sv01": "sv1",
    "svp": "svp",
    "swshp": "swshp",
    "smp": "smp",
    "basep": "basep",
}

# Sets in TCGdex to import as supplementary (not in Pokémon TCG API).
# English-language promo sets only.
SUPPLEMENTARY_SETS: list[str] = [
    "mep",  # MEP Black Star Promos (89 cards, includes First Partner)
]

# Additional SVP card numbers to import that are missing from our local DB.
# These exist in TCGdex svp but not in the Pokémon TCG API.
SVP_SUPPLEMENTARY_CARDS: list[str] = []  # Will be populated dynamically


@dataclass
class ImportReport:
    """Results of a supplementary import run."""

    sets_added: list[str] = field(default_factory=list)
    sets_already_present: list[str] = field(default_factory=list)
    cards_added: list[str] = field(default_factory=list)
    cards_already_present: list[str] = field(default_factory=list)
    cards_skipped: list[str] = field(default_factory=list)
    cards_unmatched: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a human-readable summary of the import."""
        lines = [
            "=== TCGdex Supplementary Import Report ===",
            f"Sets added: {len(self.sets_added)}",
            f"Sets already present: {len(self.sets_already_present)}",
            f"Cards added: {len(self.cards_added)}",
            f"Cards already present: {len(self.cards_already_present)}",
            f"Cards skipped: {len(self.cards_skipped)}",
            f"Cards unmatched (no species): {len(self.cards_unmatched)}",
        ]
        if self.sets_added:
            lines.append("\nSets added:")
            for s in self.sets_added:
                lines.append(f"  + {s}")
        if self.cards_added:
            lines.append(f"\nCards added (first 50):")
            for c in self.cards_added[:50]:
                lines.append(f"  + {c}")
            if len(self.cards_added) > 50:
                lines.append(f"  ... and {len(self.cards_added) - 50} more")
        if self.cards_unmatched:
            lines.append(f"\nCards with no species match:")
            for c in self.cards_unmatched:
                lines.append(f"  ? {c}")
        return "\n".join(lines)


def _tcgdex_card_id_to_api_format(tcgdex_set_id: str, local_id: str) -> str:
    """Convert a TCGdex card identifier to our api_card_id format.

    TCGdex uses IDs like "me02.5-084" but we store cards with IDs like
    "mep-42" for supplementary sets. For sets that exist in both APIs,
    we use the Pokémon TCG API format.

    For new supplementary sets (like mep), the api_card_id is:
        "{set_id}-{card_number}" with no zero-padding.
    """
    # Strip leading zeros from local_id for consistency
    card_num = local_id.lstrip("0") or "0"

    # If the TCGdex set has an equivalent in the primary API, use that ID
    if tcgdex_set_id in _TCGDEX_TO_API_SET_ID:
        api_set_id = _TCGDEX_TO_API_SET_ID[tcgdex_set_id]
        return f"{api_set_id}-{card_num}"

    # For new supplementary sets, use the TCGdex set ID directly
    return f"{tcgdex_set_id}-{card_num}"


def _resolve_species_by_name(session: Session, card_name: str) -> int | None:
    """Resolve a species ID from a card name using the same logic as card_importer."""
    from app.services.importers.card_importer import normalize_card_name, _FORM_MAPPINGS, _EXCLUDED_CARD_NAMES

    normalized = normalize_card_name(card_name)

    # Check exclusions
    if normalized.replace("-", " ") in _EXCLUDED_CARD_NAMES:
        return None

    # Check form mappings
    normalized_with_spaces = normalized.replace("-", " ")
    if normalized_with_spaces in _FORM_MAPPINGS:
        target_name = _FORM_MAPPINGS[normalized_with_spaces]
        result = session.exec(
            select(PokemonSpecies).where(PokemonSpecies.name == target_name)
        ).first()
        return result.id if result else None

    # Direct exact match
    result = session.exec(
        select(PokemonSpecies).where(PokemonSpecies.name == normalized)
    ).first()
    if result:
        return result.id

    return None


def _resolve_species_id(session: Session, dex_number: int | None) -> int | None:
    """Return the local PokemonSpecies.id for the given dex number."""
    if dex_number is None:
        return None
    result = session.exec(
        select(PokemonSpecies).where(
            PokemonSpecies.national_dex_number == dex_number
        )
    ).first()
    return result.id if result else None


def _resolve_species_for_tcgdex_card(
    session: Session, card_data: dict
) -> int | None:
    """Resolve species for a TCGdex card using dexId and name.

    Priority:
    1. dexId from TCGdex (more reliable than Pokémon TCG API)
    2. Name-based fallback
    """
    # Only resolve Pokémon cards
    category = card_data.get("category", "")
    if category and category.lower() != "pokemon":
        return None

    # Try dexId first
    dex_ids = card_data.get("dexId") or []
    if dex_ids:
        species_id = _resolve_species_id(session, dex_ids[0])
        if species_id:
            return species_id

    # Fallback to name
    name = card_data.get("name", "")
    if name:
        return _resolve_species_by_name(session, name)

    return None


def _get_card_image_url(card_data: dict) -> str | None:
    """Extract the image URL from a TCGdex card."""
    image = card_data.get("image")
    if image:
        # TCGdex provides base URL; append /high for high-res
        return f"{image}/high.webp"
    return None


def import_supplementary_set(
    session: Session,
    client: TCGdexClient,
    tcgdex_set_id: str,
    report: ImportReport,
) -> None:
    """Import a single supplementary set and its cards from TCGdex.

    Only imports cards that don't already exist in the local database.
    """
    # Check if set already exists
    existing_set = session.exec(
        select(Set).where(Set.api_set_id == tcgdex_set_id)
    ).first()

    if existing_set:
        report.sets_already_present.append(f"{tcgdex_set_id}")
        set_id = existing_set.id
    else:
        # Fetch set metadata from TCGdex
        set_data = client.get_set(tcgdex_set_id)
        new_set = Set(
            api_set_id=tcgdex_set_id,
            name=set_data.get("name", tcgdex_set_id),
            series="Mega Evolution" if tcgdex_set_id == "mep" else "Promo",
            release_date=None,
        )
        session.add(new_set)
        session.flush()
        set_id = new_set.id
        report.sets_added.append(f"{tcgdex_set_id} ({new_set.name})")

    # Fetch cards for this set
    set_data = client.get_set(tcgdex_set_id)
    cards = set_data.get("cards", [])

    for card_summary in cards:
        tcgdex_card_id = card_summary.get("id", "")
        local_id = card_summary.get("localId", "")
        card_name = card_summary.get("name", "")

        # Generate our api_card_id
        api_card_id = _tcgdex_card_id_to_api_format(tcgdex_set_id, local_id)

        # Check if card already exists
        existing = session.exec(
            select(Card).where(Card.api_card_id == api_card_id)
        ).first()

        if existing:
            report.cards_already_present.append(
                f"{api_card_id} ({card_name})"
            )
            continue

        # Fetch full card data for species resolution
        try:
            full_card = client.get_card(tcgdex_card_id)
        except Exception:
            # If we can't fetch the card, skip it
            report.cards_skipped.append(
                f"{api_card_id} ({card_name}) — fetch failed"
            )
            continue

        # Resolve species
        species_id = _resolve_species_for_tcgdex_card(session, full_card)

        # Determine rarity
        rarity = full_card.get("rarity")

        # Get image URL
        image_url = _get_card_image_url(full_card)

        # Create the card
        card = Card(
            api_card_id=api_card_id,
            set_id=set_id,
            pokemon_species_id=species_id,
            card_number=local_id.lstrip("0") or "0",
            rarity=rarity,
            image_url=image_url,
        )
        session.add(card)

        if species_id:
            report.cards_added.append(f"{api_card_id} ({card_name})")
        else:
            # Card added but no species match
            category = full_card.get("category", "")
            if category and category.lower() == "pokemon":
                report.cards_unmatched.append(f"{api_card_id} ({card_name})")
            else:
                # Non-Pokémon card (Trainer, Energy) — expected to have no species
                report.cards_added.append(
                    f"{api_card_id} ({card_name}) [non-Pokémon]"
                )


def import_missing_svp_cards(
    session: Session,
    client: TCGdexClient,
    report: ImportReport,
) -> None:
    """Import SVP cards that exist in TCGdex but not in our local database.

    Finds SVP cards in TCGdex that we don't have and adds them.
    """
    # Get SVP set from TCGdex
    try:
        set_data = client.get_set("svp")
    except Exception:
        print("WARNING: Could not fetch SVP set from TCGdex")
        return

    tcgdex_cards = set_data.get("cards", [])

    # Get our local SVP set
    local_set = session.exec(
        select(Set).where(Set.api_set_id == "svp")
    ).first()

    if not local_set:
        return

    # Find cards we're missing
    for card_summary in tcgdex_cards:
        local_id = card_summary.get("localId", "")
        card_name = card_summary.get("name", "")
        tcgdex_card_id = card_summary.get("id", "")

        # Generate our api_card_id format
        card_num = local_id.lstrip("0") or "0"
        api_card_id = f"svp-{card_num}"

        # Check if we already have it
        existing = session.exec(
            select(Card).where(Card.api_card_id == api_card_id)
        ).first()

        if existing:
            continue

        # This is a missing SVP card — fetch full data and import
        try:
            full_card = client.get_card(tcgdex_card_id)
        except Exception:
            report.cards_skipped.append(
                f"{api_card_id} ({card_name}) — fetch failed"
            )
            continue

        species_id = _resolve_species_for_tcgdex_card(session, full_card)
        rarity = full_card.get("rarity")
        image_url = _get_card_image_url(full_card)

        card = Card(
            api_card_id=api_card_id,
            set_id=local_set.id,
            pokemon_species_id=species_id,
            card_number=card_num,
            rarity=rarity,
            image_url=image_url,
        )
        session.add(card)

        if species_id:
            report.cards_added.append(f"{api_card_id} ({card_name}) [SVP gap-fill]")
        else:
            category = full_card.get("category", "")
            if category and category.lower() == "pokemon":
                report.cards_unmatched.append(f"{api_card_id} ({card_name}) [SVP]")
            else:
                report.cards_added.append(
                    f"{api_card_id} ({card_name}) [SVP, non-Pokémon]"
                )


def run_supplementary_import(
    sets_to_import: list[str] | None = None,
    include_svp_gaps: bool = True,
) -> ImportReport:
    """Run the full supplementary import from TCGdex.

    Args:
        sets_to_import: List of TCGdex set IDs to import. Defaults to
                       SUPPLEMENTARY_SETS if None.
        include_svp_gaps: Whether to also fill SVP card gaps.

    Returns:
        An ImportReport with full details of what was imported.
    """
    if sets_to_import is None:
        sets_to_import = SUPPLEMENTARY_SETS

    report = ImportReport()

    with TCGdexClient() as client, get_session_context() as session:
        # Import supplementary sets
        for set_id in sets_to_import:
            print(f"Importing supplementary set: {set_id}...")
            import_supplementary_set(session, client, set_id, report)
            session.commit()

        # Fill SVP gaps
        if include_svp_gaps:
            print("Checking for missing SVP cards...")
            import_missing_svp_cards(session, client, report)
            session.commit()

    return report


if __name__ == "__main__":
    report = run_supplementary_import()
    print(report.summary())
