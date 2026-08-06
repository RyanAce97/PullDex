"""Single entry point for populating the PullDex database.

Runs all importers in dependency order:

  1. Species  — PokéAPI  → pokemon_species table
  2. Sets     — TCG API  → sets table
  3. Cards    — TCG API  → cards table (links to sets and species)

Cards must be imported after both species and sets so that the foreign-key
lookups in the card importer can resolve correctly.

Usage::

    uv run python -m app.scripts.import_all
"""

from app.services.importers.card_importer import import_all_cards
from app.services.importers.set_importer import import_all_sets
from app.services.importers.species_importer import import_all_species


def main() -> None:
    """Run all importers in order and report progress."""

    print("=" * 60)
    print("PullDex — full database import")
    print("=" * 60)

    print("\n[1/3] Importing Pokémon species from PokéAPI...")
    import_all_species()
    print("[1/3] Species import complete.")

    print("\n[2/3] Importing TCG sets from Pokémon TCG API...")
    import_all_sets()
    print("[2/3] Set import complete.")

    print("\n[3/3] Importing TCG cards from Pokémon TCG API...")
    import_all_cards()
    print("[3/3] Card import complete.")

    print("\n" + "=" * 60)
    print("Import complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
