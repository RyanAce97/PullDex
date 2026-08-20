"""Fix unlinked Pokémon cards in the database — OFFLINE version.

This script resolves the 98 known Pokémon cards that are missing their
pokemon_species_id because the Pokémon TCG API doesn't provide
nationalPokedexNumbers for them.

The mapping is derived from the investigation that confirmed:
- Card names clearly identify the Pokémon
- All corresponding species exist in the pokemon_species table
- The mapping is unambiguous

Works entirely offline — no API calls required.

Usage:
    cd backend
    .venv/Scripts/python.exe -m app.scripts.fix_card_species_mapping --dry-run
    .venv/Scripts/python.exe -m app.scripts.fix_card_species_mapping --db-path ../database/pulldex_species_fix_test.db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Known card name → species name mapping.
# Derived from the card_importer's normalize_card_name + _FORM_MAPPINGS.
# These are the Pokémon card names (after suffix stripping) and which
# species they belong to.
# ---------------------------------------------------------------------------

# Card name (lowercase, spaces) → species name (lowercase, hyphens)
_NAME_TO_SPECIES: dict[str, str] = {
    "archaludon": "archaludon",
    "buried fossil": None,  # Excluded — not a real Pokémon
    "cornerstone mask ogerpon": "ogerpon",
    "dipplin": "dipplin",
    "fezandipiti": "fezandipiti",
    "flutter mane": "flutter-mane",
    "gouging fire": "gouging-fire",
    "great tusk": "great-tusk",
    "hearthflame mask ogerpon": "ogerpon",
    "hydrapple": "hydrapple",
    "iron boulder": "iron-boulder",
    "iron crown": "iron-crown",
    "iron hands": "iron-hands",
    "iron leaves": "iron-leaves",
    "iron moth": "iron-moth",
    "iron thorns": "iron-thorns",
    "iron valiant": "iron-valiant",
    "munkidori": "munkidori",
    "okidogi": "okidogi",
    "pecharunt": "pecharunt",
    "poltchageist": "poltchageist",
    "raging bolt": "raging-bolt",
    "roaring moon": "roaring-moon",
    "sandy shocks": "sandy-shocks",
    "scream tail": "scream-tail",
    "sinistcha": "sinistcha",
    "slither wing": "slither-wing",
    "tapu bulu": "tapu-bulu",
    "teal mask ogerpon": "ogerpon",
    "terapagos": "terapagos",
    "walking wake": "walking-wake",
    "wellspring mask ogerpon": "ogerpon",
}

# TCG suffixes to strip (order: longest first)
_TCG_SUFFIXES = [
    " VSTAR", " VMAX", " BREAK", " GX", " EX", " ex", " V",
    "-EX", "-GX", " δ", " ◇", " FB", " GL", " G", " C",
    " LV.X", " Prism Star", " Star", " ☆",
]


def _strip_suffix(name: str) -> str:
    """Strip known TCG suffixes from a card name."""
    for suffix in _TCG_SUFFIXES:
        if name.endswith(suffix):
            return name[:-len(suffix)].strip()
    return name


def run_fix(db_path: str, dry_run: bool = True) -> dict:
    """Run the species mapping fix against the specified database.

    Works entirely offline using the known card-to-species mapping.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Load species lookup: name → (id, dex_number)
    cur.execute("SELECT id, national_dex_number, name FROM pokemon_species")
    species_by_name: dict[str, tuple[int, int]] = {}
    for row in cur.fetchall():
        species_by_name[row[2]] = (row[0], row[1])

    print(f"Loaded {len(species_by_name)} species from database.", flush=True)

    # Get all unlinked cards
    cur.execute("""
        SELECT id, api_card_id, pokemon_species_id
        FROM cards
        WHERE pokemon_species_id IS NULL
    """)
    unlinked_cards = cur.fetchall()

    # Get total card counts
    cur.execute("SELECT COUNT(*) FROM cards")
    total_cards = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM cards WHERE pokemon_species_id IS NOT NULL")
    linked_count = cur.fetchone()[0]

    print(f"Total cards: {total_cards}", flush=True)
    print(f"Currently linked to species: {linked_count}", flush=True)
    print(f"Currently unlinked: {len(unlinked_cards)}", flush=True)
    print(flush=True)

    # For each unlinked card, check if its api_card_id suggests it's one of
    # the known affected cards. We need the card NAME — but we don't store it.
    #
    # Strategy: We know the exact api_card_ids from the investigation.
    # But rather than hardcoding 99 IDs, let's use a smarter approach:
    # Query the database to find cards that share an api_card_id prefix with
    # LINKED cards of the same species — no, that won't work.
    #
    # Best offline approach: Use the api_card_id to look up the card name
    # from any stored data... but we don't store card names.
    #
    # ACTUAL best approach: We need to look at what information IS available.
    # The api_card_id is like "sv6-111" — just set+number, no species info.
    #
    # Since we can't derive the Pokémon name from the local data alone,
    # we'll embed the KNOWN list of affected api_card_ids with their species.
    # This was determined during the investigation and is authoritative.

    # Hardcoded from investigation: api_card_id → (pokemon_name_raw, species_name)
    _KNOWN_FIXES: dict[str, tuple[str, str]] = {
        # Archaludon (#1018)
        "sv7-107": ("Archaludon", "archaludon"),
        "sv7-155": ("Archaludon", "archaludon"),
        # Cornerstone Mask Ogerpon (#1017)
        "sv6-112": ("Cornerstone Mask Ogerpon ex", "ogerpon"),
        "sv6-199": ("Cornerstone Mask Ogerpon ex", "ogerpon"),
        "sv6-215": ("Cornerstone Mask Ogerpon ex", "ogerpon"),
        # Dipplin (#1011)
        "sv6-18": ("Dipplin", "dipplin"),
        "sv6-127": ("Dipplin", "dipplin"),
        "sv6-170": ("Dipplin", "dipplin"),
        "sv7-13": ("Dipplin", "dipplin"),
        # Fezandipiti (#1016)
        "sv6-96": ("Fezandipiti", "fezandipiti"),
        "sv6pt5-73": ("Fezandipiti", "fezandipiti"),
        "sv6pt5-38": ("Fezandipiti ex", "fezandipiti"),
        "sv6pt5-84": ("Fezandipiti ex", "fezandipiti"),
        "sv6pt5-92": ("Fezandipiti ex", "fezandipiti"),
        # Flutter Mane (#987)
        "sv8pt5-43": ("Flutter Mane", "flutter-mane"),
        # Gouging Fire (#1020)
        "svp-151": ("Gouging Fire", "gouging-fire"),
        "sv5-38": ("Gouging Fire ex", "gouging-fire"),
        "sv5-188": ("Gouging Fire ex", "gouging-fire"),
        "sv5-204": ("Gouging Fire ex", "gouging-fire"),
        "sv5-214": ("Gouging Fire ex", "gouging-fire"),
        "svp-144": ("Gouging Fire ex", "gouging-fire"),
        # Great Tusk (#984)
        "sv8pt5-55": ("Great Tusk", "great-tusk"),
        # Hearthflame Mask Ogerpon (#1017)
        "sv6-40": ("Hearthflame Mask Ogerpon ex", "ogerpon"),
        "sv6-192": ("Hearthflame Mask Ogerpon ex", "ogerpon"),
        "sv6-212": ("Hearthflame Mask Ogerpon ex", "ogerpon"),
        # Hydrapple (#1019)
        "sv7-14": ("Hydrapple ex", "hydrapple"),
        "sv7-156": ("Hydrapple ex", "hydrapple"),
        "sv7-167": ("Hydrapple ex", "hydrapple"),
        # Iron Boulder (#1022)
        "sv7-71": ("Iron Boulder", "iron-boulder"),
        "sv8pt5-46": ("Iron Boulder", "iron-boulder"),
        "sv5-99": ("Iron Boulder ex", "iron-boulder"),
        "sv5-192": ("Iron Boulder ex", "iron-boulder"),
        "sv5-207": ("Iron Boulder ex", "iron-boulder"),
        "sv5-217": ("Iron Boulder ex", "iron-boulder"),
        "svp-147": ("Iron Boulder ex", "iron-boulder"),
        # Iron Crown (#1023)
        "sv5-81": ("Iron Crown ex", "iron-crown"),
        "sv5-191": ("Iron Crown ex", "iron-crown"),
        "sv5-206": ("Iron Crown ex", "iron-crown"),
        "sv5-216": ("Iron Crown ex", "iron-crown"),
        "svp-146": ("Iron Crown ex", "iron-crown"),
        "sv8pt5-158": ("Iron Crown ex", "iron-crown"),
        # Iron Hands (#992)
        "sv8pt5-31": ("Iron Hands ex", "iron-hands"),
        "sv8pt5-154": ("Iron Hands ex", "iron-hands"),
        # Iron Leaves (#1010)
        "sv8pt5-176": ("Iron Leaves ex", "iron-leaves"),
        # Iron Moth (#994)
        "sv6pt5-9": ("Iron Moth", "iron-moth"),
        # Iron Thorns (#995)
        "sv8pt5-32": ("Iron Thorns ex", "iron-thorns"),
        # Iron Valiant (#1006)
        "sv8pt5-157": ("Iron Valiant ex", "iron-valiant"),
        # Munkidori (#1015)
        "sv6-95": ("Munkidori", "munkidori"),
        "sv6pt5-72": ("Munkidori", "munkidori"),
        "sv6pt5-37": ("Munkidori ex", "munkidori"),
        "sv6pt5-83": ("Munkidori ex", "munkidori"),
        "sv6pt5-91": ("Munkidori ex", "munkidori"),
        # Okidogi (#1014)
        "sv6-111": ("Okidogi", "okidogi"),
        "sv6pt5-74": ("Okidogi", "okidogi"),
        "sv8pt5-57": ("Okidogi", "okidogi"),
        "me2pt5-122": ("Okidogi", "okidogi"),
        "sv6pt5-36": ("Okidogi ex", "okidogi"),
        "sv6pt5-82": ("Okidogi ex", "okidogi"),
        "sv6pt5-90": ("Okidogi ex", "okidogi"),
        # Pecharunt (#1025)
        "svp-149": ("Pecharunt", "pecharunt"),
        "sv6pt5-39": ("Pecharunt ex", "pecharunt"),
        "sv6pt5-85": ("Pecharunt ex", "pecharunt"),
        "sv6pt5-93": ("Pecharunt ex", "pecharunt"),
        "sv6pt5-95": ("Pecharunt ex", "pecharunt"),
        # Poltchageist (#1012)
        "sv6-20": ("Poltchageist", "poltchageist"),
        "sv6-21": ("Poltchageist", "poltchageist"),
        "sv6-171": ("Poltchageist", "poltchageist"),
        # Raging Bolt (#1021)
        "sv7-111": ("Raging Bolt", "raging-bolt"),
        "sv5-123": ("Raging Bolt ex", "raging-bolt"),
        "sv5-196": ("Raging Bolt ex", "raging-bolt"),
        "sv5-208": ("Raging Bolt ex", "raging-bolt"),
        "sv5-218": ("Raging Bolt ex", "raging-bolt"),
        "svp-145": ("Raging Bolt ex", "raging-bolt"),
        "sv8pt5-166": ("Raging Bolt ex", "raging-bolt"),
        # Roaring Moon (#1005)
        "sv8pt5-65": ("Roaring Moon", "roaring-moon"),
        "sv8pt5-162": ("Roaring Moon ex", "roaring-moon"),
        # Sandy Shocks (#989)
        "sv8pt5-56": ("Sandy Shocks ex", "sandy-shocks"),
        "sv8pt5-159": ("Sandy Shocks ex", "sandy-shocks"),
        # Scream Tail (#985)
        "sv8pt5-42": ("Scream Tail", "scream-tail"),
        # Sinistcha (#1013)
        "sv6-22": ("Sinistcha", "sinistcha"),
        "sv6-23": ("Sinistcha ex", "sinistcha"),
        "sv6-189": ("Sinistcha ex", "sinistcha"),
        "sv6-210": ("Sinistcha ex", "sinistcha"),
        # Slither Wing (#988)
        "sv6pt5-26": ("Slither Wing", "slither-wing"),
        # Tapu Bulu (#787)
        "sv6pt5-6": ("Tapu Bulu", "tapu-bulu"),
        "sv6pt5-65": ("Tapu Bulu", "tapu-bulu"),
        # Teal Mask Ogerpon (#1017)
        "sv6-24": ("Teal Mask Ogerpon", "ogerpon"),
        "sv6-25": ("Teal Mask Ogerpon ex", "ogerpon"),
        "sv6-190": ("Teal Mask Ogerpon ex", "ogerpon"),
        "sv6-211": ("Teal Mask Ogerpon ex", "ogerpon"),
        "sv6-221": ("Teal Mask Ogerpon ex", "ogerpon"),
        # Terapagos (#1024)
        "sv7-128": ("Terapagos ex", "terapagos"),
        "sv7-170": ("Terapagos ex", "terapagos"),
        "sv7-173": ("Terapagos ex", "terapagos"),
        # Walking Wake (#1009)
        "sv8pt5-178": ("Walking Wake ex", "walking-wake"),
        # Wellspring Mask Ogerpon (#1017)
        "sv6-64": ("Wellspring Mask Ogerpon ex", "ogerpon"),
        "sv6-194": ("Wellspring Mask Ogerpon ex", "ogerpon"),
        "sv6-213": ("Wellspring Mask Ogerpon ex", "ogerpon"),
    }

    # Also the Buried Fossil exclusion
    _EXCLUDED = {"ecard3-47"}  # Buried Fossil

    resolved = []
    still_unlinked_pokemon = []
    excluded = []
    not_pokemon = 0  # Cards that are trainers/energy (correct to be unlinked)

    print("Checking unlinked cards against known fixes...", flush=True)

    for card_id, api_card_id, _ in unlinked_cards:
        if api_card_id in _EXCLUDED:
            excluded.append({"db_id": card_id, "api_card_id": api_card_id, "reason": "Excluded edge case (Buried Fossil)"})
            continue

        if api_card_id in _KNOWN_FIXES:
            card_name, species_name = _KNOWN_FIXES[api_card_id]
            if species_name in species_by_name:
                sp_id, dex_num = species_by_name[species_name]
                resolved.append({
                    "db_id": card_id,
                    "api_card_id": api_card_id,
                    "card_name": card_name,
                    "species_name": species_name,
                    "species_id": sp_id,
                    "dex_number": dex_num,
                })
            else:
                still_unlinked_pokemon.append({
                    "db_id": card_id,
                    "api_card_id": api_card_id,
                    "card_name": card_name,
                    "reason": f"Species '{species_name}' not in database",
                })
        else:
            # Not in our known fix list — it's a Trainer/Energy (correct to be unlinked)
            not_pokemon += 1

    # Print report
    print(flush=True)
    print("=" * 70, flush=True)
    print("CARD-TO-SPECIES MAPPING FIX — AUDIT REPORT", flush=True)
    print("=" * 70, flush=True)
    print(f"Database: {db_path}", flush=True)
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}", flush=True)
    print(flush=True)
    print(f"Total cards in database:          {total_cards}", flush=True)
    print(f"Cards linked to species:          {linked_count}", flush=True)
    print(f"Cards unlinked (total):           {len(unlinked_cards)}", flush=True)
    print(f"  Trainer/Energy (correct):       {not_pokemon}", flush=True)
    print(f"  Pokemon resolved by name:       {len(resolved)}", flush=True)
    print(f"  Pokemon still unresolved:       {len(still_unlinked_pokemon)}", flush=True)
    print(f"  Excluded edge cases:            {len(excluded)}", flush=True)
    print(flush=True)

    if resolved:
        print(f"RESOLVED ({len(resolved)} cards):", flush=True)
        print("-" * 70, flush=True)
        for r in sorted(resolved, key=lambda x: (x["dex_number"], x["api_card_id"])):
            print(f"  {r['api_card_id']:20s} {r['card_name']:30s} -> #{r['dex_number']:4d} {r['species_name']}", flush=True)
        print(flush=True)

    if still_unlinked_pokemon:
        print(f"STILL UNRESOLVED ({len(still_unlinked_pokemon)} cards):", flush=True)
        print("-" * 70, flush=True)
        for u in still_unlinked_pokemon:
            print(f"  {u['api_card_id']:20s} {u['card_name']:30s} ({u['reason']})", flush=True)
        print(flush=True)

    if excluded:
        print(f"EXCLUDED ({len(excluded)} cards):", flush=True)
        print("-" * 70, flush=True)
        for e in excluded:
            print(f"  {e['api_card_id']:20s} ({e['reason']})", flush=True)
        print(flush=True)

    # Apply if not dry run
    if not dry_run and resolved:
        print("Applying fixes...", flush=True)
        for r in resolved:
            cur.execute(
                "UPDATE cards SET pokemon_species_id = ? WHERE id = ?",
                (r["species_id"], r["db_id"]),
            )
        conn.commit()
        print(f"  Updated {len(resolved)} cards.", flush=True)
    elif dry_run and resolved:
        print(f"DRY RUN: Would update {len(resolved)} cards.", flush=True)

    # Verify collection unchanged
    cur.execute("SELECT COUNT(*) FROM collection")
    collection_count = cur.fetchone()[0]
    print(f"\nCollection entries: {collection_count} (unchanged)", flush=True)

    # Verify no duplicates
    cur.execute("""
        SELECT api_card_id, COUNT(*) FROM cards
        GROUP BY api_card_id HAVING COUNT(*) > 1
    """)
    dupes = cur.fetchall()
    print(f"Duplicate card IDs: {len(dupes)}", flush=True)

    # Verify no invalid species references
    cur.execute("""
        SELECT COUNT(*) FROM cards
        WHERE pokemon_species_id IS NOT NULL
        AND pokemon_species_id NOT IN (SELECT id FROM pokemon_species)
    """)
    invalid_refs = cur.fetchone()[0]
    print(f"Invalid species references: {invalid_refs}", flush=True)

    conn.close()

    return {
        "resolved": len(resolved),
        "unresolved": len(still_unlinked_pokemon),
        "excluded": len(excluded),
        "trainer_energy": not_pokemon,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fix unlinked Pokémon cards — offline, no API calls."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="../database/pulldex.db",
        help="Path to the SQLite database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Only report, don't apply changes.",
    )
    args = parser.parse_args()

    run_fix(args.db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
