"""Export the PullDex card catalogue to a bundled JSON snapshot for the mobile app.

Reads the READ-ONLY seed database (backups/pulldex_backup_initial_import.db)
and writes apps/mobile/assets/catalogue/catalogue.json — the offline snapshot
the Expo app seeds into its local SQLite database on first run.

This NEVER writes to any database. It opens the seed DB read-only (file: URI
with mode=ro) and only reads. It does not touch the dev or live databases.

Run from the repo root:
    backend/.venv/Scripts/python.exe apps/mobile/scripts/export_catalogue.py

Output shape (compact columnar-ish records, one card model shared with desktop):
{
  "schema_version": 1,
  "generated_at": "<iso>",
  "source_alembic": "<rev>",
  "counts": { "species": N, "sets": N, "cards": N },
  "species": [{ "id", "national_dex_number", "name", "generation" }, ...],
  "sets": [{ "id", "api_set_id", "name", "series", "release_date", "is_promo" }, ...],
  "cards": [{ "id","api_card_id","pokemon_species_id","set_id","card_number","rarity","variant","image_url" }, ...]
}
"""

import datetime as _dt
import json
import os
import sqlite3
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SEED_DB = os.path.join(REPO_ROOT, "backups", "pulldex_backup_initial_import.db")
OUT_DIR = os.path.join(REPO_ROOT, "apps", "mobile", "assets", "catalogue")
OUT_FILE = os.path.join(OUT_DIR, "catalogue.json")


def main() -> int:
    if not os.path.exists(SEED_DB):
        print(f"ERROR: seed DB not found at {SEED_DB}", file=sys.stderr)
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)

    # Open READ-ONLY — never mutate the seed DB.
    conn = sqlite3.connect(f"file:{SEED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    species = [
        {
            "id": r["id"],
            "national_dex_number": r["national_dex_number"],
            "name": r["name"],
            "generation": r["generation"],
        }
        for r in conn.execute(
            "SELECT id, national_dex_number, name, generation FROM pokemon_species "
            "ORDER BY national_dex_number"
        )
    ]

    sets = [
        {
            "id": r["id"],
            "api_set_id": r["api_set_id"],
            "name": r["name"],
            "series": r["series"],
            "release_date": r["release_date"],
            "is_promo": bool(r["is_promo"]),
        }
        for r in conn.execute(
            "SELECT id, api_set_id, name, series, release_date, is_promo FROM sets ORDER BY id"
        )
    ]

    cards = [
        {
            "id": r["id"],
            "api_card_id": r["api_card_id"],
            "pokemon_species_id": r["pokemon_species_id"],
            "set_id": r["set_id"],
            "card_number": r["card_number"],
            "rarity": r["rarity"],
            "variant": r["variant"],
            "image_url": r["image_url"],
        }
        for r in conn.execute(
            "SELECT id, api_card_id, pokemon_species_id, set_id, card_number, rarity, "
            "variant, image_url FROM cards ORDER BY id"
        )
    ]

    source_alembic = None
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        source_alembic = row[0] if row else None
    except sqlite3.Error:
        pass

    conn.close()

    payload = {
        "schema_version": 1,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source_alembic": source_alembic,
        "counts": {"species": len(species), "sets": len(sets), "cards": len(cards)},
        "species": species,
        "sets": sets,
        "cards": cards,
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(OUT_FILE) / (1024 * 1024)
    print(f"Wrote {OUT_FILE}")
    print(f"  species={len(species)} sets={len(sets)} cards={len(cards)}")
    print(f"  size={size_mb:.2f} MB source_alembic={source_alembic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
