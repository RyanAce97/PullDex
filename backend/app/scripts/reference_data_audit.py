"""Reference-data audit and supplementary import script.

This script:
1. Creates a pre-change backup
2. Records collection state (row count, quantities)
3. Runs the species repair (Azumarill ex fix)
4. Runs the supplementary import from TCGdex
5. Runs species-mapping validation
6. Verifies collection is unchanged
7. Produces a comprehensive audit report

Usage:
    cd backend
    uv run python -m app.scripts.reference_data_audit [--dry-run] [--skip-import]
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# Ensure app modules are importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _get_db_path() -> Path:
    """Get the database path from settings."""
    from app.config import settings
    return Path(settings.database_url.removeprefix("sqlite:///"))


def _backup_database(db_path: Path) -> Path:
    """Create a timestamped backup of the database.

    Returns the path to the backup file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = db_path.parent.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"pulldex_pre_refdata_{timestamp}.db"

    # Use sqlite3 backup API for safety
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    dst.close()
    src.close()

    return backup_path


def _get_collection_state(db_path: Path) -> dict:
    """Snapshot the collection state for verification."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM collection")
    row_count = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM collection")
    total_quantity = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM profiles")
    profile_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM collection WHERE is_binder_card = 1")
    binder_count = cur.fetchone()[0]

    conn.close()
    return {
        "row_count": row_count,
        "total_quantity": total_quantity,
        "profile_count": profile_count,
        "binder_card_count": binder_count,
    }


def _get_reference_data_state(db_path: Path) -> dict:
    """Snapshot the reference data state."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM pokemon_species")
    species_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM sets")
    set_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM cards")
    card_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM cards WHERE pokemon_species_id IS NOT NULL")
    cards_with_species = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM cards WHERE pokemon_species_id IS NULL")
    cards_without_species = cur.fetchone()[0]

    conn.close()
    return {
        "species_count": species_count,
        "set_count": set_count,
        "card_count": card_count,
        "cards_with_species": cards_with_species,
        "cards_without_species": cards_without_species,
    }


def _check_specific_mappings(db_path: Path) -> dict:
    """Check specific species mappings for audit."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    results = {}

    # Check Azumarill ex (me2pt5-84)
    cur.execute("""
        SELECT c.api_card_id, ps.name, ps.national_dex_number
        FROM cards c
        LEFT JOIN pokemon_species ps ON c.pokemon_species_id = ps.id
        WHERE c.api_card_id = 'me2pt5-84'
    """)
    row = cur.fetchone()
    if row:
        results["me2pt5-84"] = {"species": row[1], "dex": row[2]}

    # Check Pikachu cards count
    cur.execute("""
        SELECT COUNT(*) FROM cards c
        JOIN pokemon_species ps ON c.pokemon_species_id = ps.id
        WHERE ps.name = 'pikachu'
    """)
    results["pikachu_card_count"] = cur.fetchone()[0]

    # Check Marill cards
    cur.execute("""
        SELECT COUNT(*) FROM cards c
        JOIN pokemon_species ps ON c.pokemon_species_id = ps.id
        WHERE ps.name = 'marill'
    """)
    results["marill_card_count"] = cur.fetchone()[0]

    # Check Azumarill cards
    cur.execute("""
        SELECT COUNT(*) FROM cards c
        JOIN pokemon_species ps ON c.pokemon_species_id = ps.id
        WHERE ps.name = 'azumarill'
    """)
    results["azumarill_card_count"] = cur.fetchone()[0]

    # Check First Partner cards (in mep set)
    cur.execute("""
        SELECT COUNT(*) FROM cards c
        JOIN sets s ON c.set_id = s.id
        WHERE s.api_set_id = 'mep'
    """)
    results["mep_card_count"] = cur.fetchone()[0]

    # Check First Partner starter species specifically
    starter_species = [
        'bulbasaur', 'charmander', 'squirtle',
        'chikorita', 'cyndaquil', 'totodile',
        'treecko', 'torchic', 'mudkip',
        'turtwig', 'chimchar', 'piplup',
        'snivy', 'tepig', 'oshawott',
        'chespin', 'fennekin', 'froakie',
        'rowlet', 'litten', 'popplio',
        'grookey', 'scorbunny', 'sobble',
        'sprigatito', 'fuecoco', 'quaxly',
    ]
    cur.execute(f"""
        SELECT ps.name, COUNT(c.id) as card_count
        FROM pokemon_species ps
        LEFT JOIN cards c ON c.pokemon_species_id = ps.id
        WHERE ps.name IN ({','.join('?' * len(starter_species))})
        GROUP BY ps.name
        ORDER BY ps.national_dex_number
    """, starter_species)
    results["starter_card_counts"] = {row[0]: row[1] for row in cur.fetchall()}

    # Check promo set card counts
    cur.execute("""
        SELECT s.api_set_id, s.name, COUNT(c.id) as card_count
        FROM sets s
        LEFT JOIN cards c ON c.set_id = s.id
        WHERE s.api_set_id IN ('svp', 'mep', 'swshp')
        GROUP BY s.id
    """)
    results["promo_set_counts"] = {row[0]: {"name": row[1], "cards": row[2]} for row in cur.fetchall()}

    # Check for duplicate api_card_ids
    cur.execute("""
        SELECT api_card_id, COUNT(*) as cnt
        FROM cards
        WHERE api_card_id IS NOT NULL
        GROUP BY api_card_id
        HAVING cnt > 1
    """)
    results["duplicate_card_ids"] = [row[0] for row in cur.fetchall()]

    conn.close()
    return results


def run_audit(dry_run: bool = False, skip_import: bool = False) -> str:
    """Run the full reference-data audit.

    Args:
        dry_run: If True, do not apply changes (report only)
        skip_import: If True, skip the TCGdex import step

    Returns:
        The full audit report as a string.
    """
    db_path = _get_db_path()
    lines: list[str] = []

    lines.append("=" * 70)
    lines.append("PULLDEX REFERENCE DATA AUDIT")
    lines.append(f"Date: {datetime.now().isoformat()}")
    lines.append(f"Database: {db_path}")
    lines.append(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    lines.append("=" * 70)

    # Step 1: Pre-change state
    lines.append("\n--- PRE-CHANGE STATE ---")
    pre_collection = _get_collection_state(db_path)
    pre_refdata = _get_reference_data_state(db_path)

    lines.append(f"Collection rows: {pre_collection['row_count']}")
    lines.append(f"Total quantity: {pre_collection['total_quantity']}")
    lines.append(f"Profiles: {pre_collection['profile_count']}")
    lines.append(f"Binder cards: {pre_collection['binder_card_count']}")
    lines.append(f"Species: {pre_refdata['species_count']}")
    lines.append(f"Sets: {pre_refdata['set_count']}")
    lines.append(f"Cards: {pre_refdata['card_count']}")
    lines.append(f"Cards with species: {pre_refdata['cards_with_species']}")
    lines.append(f"Cards without species: {pre_refdata['cards_without_species']}")

    # Step 2: Backup
    if not dry_run:
        lines.append("\n--- BACKUP ---")
        backup_path = _backup_database(db_path)
        lines.append(f"Backup created: {backup_path}")
    else:
        lines.append("\n--- BACKUP (skipped — dry run) ---")

    # Step 3: Run repair (Azumarill ex fix)
    if not dry_run:
        lines.append("\n--- SPECIES REPAIR ---")
        from app.database import _repair_card_species_mapping
        _repair_card_species_mapping()
        lines.append("Repair completed.")
    else:
        lines.append("\n--- SPECIES REPAIR (skipped — dry run) ---")
        lines.append("Would fix: me2pt5-84 Azumarill ex (Marill -> Azumarill)")

    # Step 4: Run supplementary import
    if not dry_run and not skip_import:
        lines.append("\n--- TCGDEX SUPPLEMENTARY IMPORT ---")
        from app.services.importers.tcgdex_importer import run_supplementary_import
        import_report = run_supplementary_import()
        lines.append(import_report.summary())
    else:
        reason = "dry run" if dry_run else "skipped by flag"
        lines.append(f"\n--- TCGDEX SUPPLEMENTARY IMPORT ({reason}) ---")
        lines.append("Would import: MEP Black Star Promos (89 cards)")
        lines.append("Would gap-fill: Missing SVP cards")

    # Step 5: Post-change state
    lines.append("\n--- POST-CHANGE STATE ---")
    post_collection = _get_collection_state(db_path)
    post_refdata = _get_reference_data_state(db_path)

    lines.append(f"Species: {post_refdata['species_count']}")
    lines.append(f"Sets: {post_refdata['set_count']}")
    lines.append(f"Cards: {post_refdata['card_count']}")
    lines.append(f"Cards with species: {post_refdata['cards_with_species']}")
    lines.append(f"Cards without species: {post_refdata['cards_without_species']}")

    # Step 6: Data safety verification
    lines.append("\n--- DATA SAFETY VERIFICATION ---")
    collection_safe = (
        pre_collection["row_count"] == post_collection["row_count"]
        and pre_collection["total_quantity"] == post_collection["total_quantity"]
        and pre_collection["profile_count"] == post_collection["profile_count"]
        and pre_collection["binder_card_count"] == post_collection["binder_card_count"]
    )

    if collection_safe:
        lines.append("[OK] Collection UNCHANGED")
        lines.append(f"   Rows: {post_collection['row_count']} (unchanged)")
        lines.append(f"   Quantities: {post_collection['total_quantity']} (unchanged)")
        lines.append(f"   Profiles: {post_collection['profile_count']} (unchanged)")
        lines.append(f"   Binder cards: {post_collection['binder_card_count']} (unchanged)")
    else:
        lines.append("[FAIL] COLLECTION CHANGED -- THIS IS A BUG!")
        lines.append(f"   Rows: {pre_collection['row_count']} -> {post_collection['row_count']}")
        lines.append(f"   Quantities: {pre_collection['total_quantity']} -> {post_collection['total_quantity']}")

    # Step 7: Specific mapping checks
    lines.append("\n--- SPECIFIC MAPPING CHECKS ---")
    checks = _check_specific_mappings(db_path)

    # Azumarill ex
    azumarill_card = checks.get("me2pt5-84", {})
    if azumarill_card:
        correct = azumarill_card.get("species") == "azumarill" and azumarill_card.get("dex") == 184
        status = "[OK]" if correct else "[FAIL]"
        lines.append(
            f"{status} me2pt5-84 (Azumarill ex): "
            f"{azumarill_card.get('species')} (dex {azumarill_card.get('dex')})"
        )
    else:
        lines.append("[WARN] me2pt5-84 not found in database")

    # Pikachu, Marill, Azumarill card counts
    lines.append(f"   Pikachu cards: {checks.get('pikachu_card_count', 0)}")
    lines.append(f"   Marill cards: {checks.get('marill_card_count', 0)}")
    lines.append(f"   Azumarill cards: {checks.get('azumarill_card_count', 0)}")

    # MEP / First Partner
    lines.append(f"   MEP set cards: {checks.get('mep_card_count', 0)}")

    # Promo sets
    lines.append("\n   Promo set card counts:")
    for set_id, info in checks.get("promo_set_counts", {}).items():
        lines.append(f"     {set_id}: {info['cards']} ({info['name']})")

    # Starter Pokémon card counts
    lines.append("\n   First Partner starter species card counts:")
    for species_name, count in sorted(
        checks.get("starter_card_counts", {}).items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        lines.append(f"     {species_name}: {count} cards")

    # Duplicates
    dupes = checks.get("duplicate_card_ids", [])
    if dupes:
        lines.append(f"\n[FAIL] DUPLICATE api_card_ids found: {dupes}")
    else:
        lines.append("\n[OK] No duplicate api_card_ids")

    # Step 8: Summary
    lines.append("\n--- SUMMARY ---")
    cards_added = post_refdata["card_count"] - pre_refdata["card_count"]
    sets_added = post_refdata["set_count"] - pre_refdata["set_count"]
    species_gained = post_refdata["cards_with_species"] - pre_refdata["cards_with_species"]

    lines.append(f"Sets added: {sets_added}")
    lines.append(f"Cards added: {cards_added}")
    lines.append(f"New species mappings: {species_gained}")
    lines.append(f"Collection safe: {'YES' if collection_safe else 'NO ⚠️'}")

    lines.append("\n" + "=" * 70)

    report = "\n".join(lines)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PullDex reference-data audit and supplementary import."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only, do not apply changes.",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Skip the TCGdex supplementary import step.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write report to file instead of stdout.",
    )
    args = parser.parse_args()

    report = run_audit(dry_run=args.dry_run, skip_import=args.skip_import)
    print(report)

    if args.output:
        Path(args.output).write_text(report)
        print(f"\nReport saved to: {args.output}")
