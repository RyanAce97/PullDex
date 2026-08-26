"""Tests for the supplementary card seeding mechanism (_seed_supplementary_cards).

Verifies that:
- The bundled JSON data file is valid and contains 115 cards
- The seeder creates the MEP set when missing
- All 89 MEP cards are inserted correctly
- All 26 SVP gap-fill cards are inserted correctly
- Species mappings are resolved correctly via national_dex_number
- The operation is idempotent (safe to run repeatedly)
- Existing card records are never overwritten
- Collection, profiles, and binder data are never modified
- The mechanism works offline (no httpx/network)
"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_data_file_path() -> Path:
    """Get the path to the supplementary cards JSON file."""
    return Path(__file__).resolve().parents[1] / "app" / "data" / "supplementary_cards.json"


def _create_test_db(tmp_path: Path) -> str:
    """Create a minimal test database with species, sets, and collection tables."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE pokemon_species (
            id INTEGER PRIMARY KEY,
            national_dex_number INTEGER NOT NULL UNIQUE,
            name VARCHAR(100) NOT NULL,
            generation INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE sets (
            id INTEGER PRIMARY KEY,
            api_set_id VARCHAR(50) UNIQUE,
            name VARCHAR(150) NOT NULL,
            series VARCHAR(100) NOT NULL,
            release_date DATE
        )
    """)
    cur.execute("""
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY,
            api_card_id VARCHAR(50) UNIQUE,
            pokemon_species_id INTEGER,
            set_id INTEGER,
            card_number VARCHAR(20),
            rarity VARCHAR(50),
            variant VARCHAR(50),
            image_url VARCHAR(500)
        )
    """)
    cur.execute("""
        CREATE TABLE collection (
            id INTEGER PRIMARY KEY,
            card_id INTEGER,
            pokemon_species_id INTEGER,
            quantity INTEGER DEFAULT 1,
            profile_id INTEGER NOT NULL,
            is_binder_card BOOLEAN DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE profiles (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            binder_rows INTEGER DEFAULT 5,
            binder_columns INTEGER DEFAULT 4,
            binder_sort VARCHAR(50) DEFAULT 'dex_number'
        )
    """)

    # Insert the 1025 species (needed for dex number lookups)
    # For testing, we insert all species that appear in our supplementary data
    data_file = _get_data_file_path()
    with open(data_file) as f:
        data = json.load(f)

    dex_numbers_needed = set()
    for card in data["cards"]:
        if card.get("national_dex_number"):
            dex_numbers_needed.add(card["national_dex_number"])

    for dex in sorted(dex_numbers_needed):
        cur.execute(
            "INSERT INTO pokemon_species (id, national_dex_number, name, generation) VALUES (?, ?, ?, ?)",
            (dex, dex, f"species-{dex}", 1),
        )

    # Insert the SVP set (needed for SVP gap-fill cards)
    cur.execute(
        "INSERT INTO sets (api_set_id, name, series) VALUES (?, ?, ?)",
        ("svp", "Scarlet & Violet Black Star Promos", "Scarlet & Violet"),
    )

    # Insert a profile
    cur.execute("INSERT INTO profiles (name, is_active) VALUES ('Default', 1)")

    # Insert some collection data (to verify it's preserved)
    cur.execute("INSERT INTO collection (card_id, quantity, profile_id, is_binder_card) VALUES (99999, 3, 1, 1)")
    cur.execute("INSERT INTO collection (pokemon_species_id, quantity, profile_id, is_binder_card) VALUES (25, 1, 1, 0)")

    conn.commit()
    conn.close()
    return db_path


# ===========================================================================
# JSON Data File Tests
# ===========================================================================

class TestSupplementaryCardsJSON:
    """Tests for the bundled supplementary_cards.json file."""

    def test_json_file_exists(self):
        """The data file exists in the repository."""
        assert _get_data_file_path().is_file()

    def test_json_is_valid(self):
        """The data file is valid JSON."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_json_has_correct_structure(self):
        """The data file has version, sets, and cards keys."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        assert "version" in data
        assert "sets" in data
        assert "cards" in data
        assert data["version"] == 1

    def test_json_contains_115_cards(self):
        """The data file contains exactly 115 cards."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        assert len(data["cards"]) == 115

    def test_json_contains_89_mep_cards(self):
        """The data file contains exactly 89 MEP cards."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        mep_cards = [c for c in data["cards"] if c["set_api_id"] == "mep"]
        assert len(mep_cards) == 89

    def test_json_contains_26_svp_cards(self):
        """The data file contains exactly 26 SVP gap-fill cards."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        svp_cards = [c for c in data["cards"] if c["set_api_id"] == "svp"]
        assert len(svp_cards) == 26

    def test_json_contains_mep_set_definition(self):
        """The data file defines the MEP set."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        assert len(data["sets"]) == 1
        mep_set = data["sets"][0]
        assert mep_set["api_set_id"] == "mep"
        assert mep_set["name"] == "MEP Black Star Promos"
        assert mep_set["series"] == "Mega Evolution"

    def test_json_first_partner_cards_present(self):
        """All 27 First Partner Illustration Collection cards (#37-#63) are present."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        first_partner_ids = {f"mep-{n}" for n in range(37, 64)}
        actual_ids = {c["api_card_id"] for c in data["cards"] if c["set_api_id"] == "mep"}
        assert first_partner_ids.issubset(actual_ids)

    def test_json_card_fields_complete(self):
        """Every card has required fields."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        for card in data["cards"]:
            assert "api_card_id" in card
            assert "set_api_id" in card
            assert "card_number" in card
            assert "rarity" in card
            assert "national_dex_number" in card or card["national_dex_number"] is None

    def test_json_no_duplicate_card_ids(self):
        """No duplicate api_card_id values in the data file."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        ids = [c["api_card_id"] for c in data["cards"]]
        assert len(ids) == len(set(ids))

    def test_json_svp_cards_are_specific_gap_fills(self):
        """SVP gap-fill cards include known expected IDs."""
        with open(_get_data_file_path()) as f:
            data = json.load(f)
        svp_ids = {c["api_card_id"] for c in data["cards"] if c["set_api_id"] == "svp"}
        expected = {"svp-175", "svp-176", "svp-208", "svp-217", "svp-218", "svp-225", "svp-500"}
        assert expected.issubset(svp_ids)


# ===========================================================================
# Seeding Mechanism Tests
# ===========================================================================

class TestSeedSupplementaryCards:
    """Tests for the _seed_supplementary_cards() function."""

    def test_creates_mep_set(self, tmp_path):
        """The seeder creates the MEP set when it doesn't exist."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT api_set_id, name, series FROM sets WHERE api_set_id = 'mep'")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "mep"
        assert row[1] == "MEP Black Star Promos"
        assert row[2] == "Mega Evolution"
        conn.close()

    def test_inserts_all_89_mep_cards(self, tmp_path):
        """The seeder inserts all 89 MEP cards."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards WHERE api_card_id LIKE 'mep-%'")
        assert cur.fetchone()[0] == 89
        conn.close()

    def test_inserts_all_26_svp_cards(self, tmp_path):
        """The seeder inserts all 26 SVP gap-fill cards."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # SVP set already exists, so we just count newly inserted svp cards
        # The test DB has SVP set but no SVP cards
        cur.execute("SELECT COUNT(*) FROM cards WHERE api_card_id LIKE 'svp-%'")
        assert cur.fetchone()[0] == 26
        conn.close()

    def test_total_115_cards_inserted(self, tmp_path):
        """The seeder inserts exactly 115 cards total."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards")
        assert cur.fetchone()[0] == 115
        conn.close()

    def test_species_mapping_resolved(self, tmp_path):
        """Cards get correct pokemon_species_id from national_dex_number."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Check mep-37 (Bulbasaur, dex 1)
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'mep-37'")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1  # species id matches dex number in our test DB

        # Check svp-175 (Espeon, dex 196)
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'svp-175'")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 196

        conn.close()

    def test_idempotent_no_duplicates(self, tmp_path):
        """Running the seeder twice doesn't create duplicate cards."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards")
        assert cur.fetchone()[0] == 115  # Not 230
        cur.execute("SELECT COUNT(*) FROM sets WHERE api_set_id = 'mep'")
        assert cur.fetchone()[0] == 1  # Not 2
        conn.close()

    def test_preserves_existing_cards(self, tmp_path):
        """The seeder doesn't overwrite existing card records."""
        db_path = _create_test_db(tmp_path)

        # Pre-insert a card with custom rarity
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        mep_set_id = cur.execute("SELECT id FROM sets WHERE api_set_id = 'mep'").fetchone()
        if mep_set_id is None:
            cur.execute("INSERT INTO sets (api_set_id, name, series) VALUES ('mep', 'MEP', 'Mega Evolution')")
            mep_set_id = (cur.lastrowid,)
        cur.execute(
            "INSERT INTO cards (api_card_id, set_id, card_number, rarity) VALUES ('mep-37', ?, '37', 'CUSTOM_RARITY')",
            (mep_set_id[0],),
        )
        conn.commit()
        conn.close()

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT rarity FROM cards WHERE api_card_id = 'mep-37'")
        row = cur.fetchone()
        assert row[0] == "CUSTOM_RARITY"  # NOT overwritten with 'Promo'
        conn.close()

    def test_never_touches_collection(self, tmp_path):
        """Collection data is unchanged after seeding."""
        db_path = _create_test_db(tmp_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT id, card_id, pokemon_species_id, quantity, profile_id, is_binder_card FROM collection ORDER BY id")
        before = cur.fetchall()
        conn.close()

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT id, card_id, pokemon_species_id, quantity, profile_id, is_binder_card FROM collection ORDER BY id")
        after = cur.fetchall()
        conn.close()

        assert before == after

    def test_never_touches_profiles(self, tmp_path):
        """Profiles data is unchanged after seeding."""
        db_path = _create_test_db(tmp_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM profiles ORDER BY id")
        before = cur.fetchall()
        conn.close()

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM profiles ORDER BY id")
        after = cur.fetchall()
        conn.close()

        assert before == after

    def test_works_offline_no_httpx(self, tmp_path):
        """The seeder works without httpx (excluded from PyInstaller build)."""
        import sys

        db_path = _create_test_db(tmp_path)
        original_modules = sys.modules.copy()
        sys.modules["httpx"] = None  # type: ignore

        try:
            with patch("app.database.settings") as mock_settings:
                mock_settings.database_url = f"sqlite:///{db_path}"
                from app.database import _seed_supplementary_cards
                _seed_supplementary_cards()
        finally:
            sys.modules.update(original_modules)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards")
        assert cur.fetchone()[0] == 115
        conn.close()

    def test_first_partner_cards_mapped_correctly(self, tmp_path):
        """All 27 First Partner cards are mapped to their correct species."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        # Expected: card_id → dex_number
        expected = {
            "mep-37": 1, "mep-38": 4, "mep-39": 7,      # Gen 1
            "mep-40": 387, "mep-41": 390, "mep-42": 393, # Gen 4
            "mep-43": 722, "mep-44": 725, "mep-45": 728, # Gen 7
            "mep-46": 152, "mep-47": 155, "mep-48": 158, # Gen 2
            "mep-49": 495, "mep-50": 498, "mep-51": 501, # Gen 5
            "mep-52": 810, "mep-53": 813, "mep-54": 816, # Gen 8
            "mep-55": 252, "mep-56": 255, "mep-57": 258, # Gen 3
            "mep-58": 650, "mep-59": 653, "mep-60": 656, # Gen 6
            "mep-61": 906, "mep-62": 909, "mep-63": 912, # Gen 9
        }

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        for card_id, expected_dex in expected.items():
            cur.execute(
                "SELECT c.pokemon_species_id, ps.national_dex_number "
                "FROM cards c JOIN pokemon_species ps ON c.pokemon_species_id = ps.id "
                "WHERE c.api_card_id = ?",
                (card_id,),
            )
            row = cur.fetchone()
            assert row is not None, f"Card {card_id} not found"
            assert row[1] == expected_dex, f"Card {card_id}: expected dex {expected_dex}, got {row[1]}"

        conn.close()

    def test_svp_gap_fill_specific_cards(self, tmp_path):
        """Specific SVP gap-fill cards are present with correct species."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        expected = {
            "svp-175": 196,   # Espeon
            "svp-176": 197,   # Umbreon
            "svp-205": 150,   # Mewtwo (Team Rocket's Mewtwo ex)
            "svp-217": 34,    # Nidoking (Team Rocket's Nidoking ex)
            "svp-218": 53,    # Persian (Team Rocket's Persian ex)
            "svp-225": 25,    # Pikachu
            "svp-500": 1024,  # Terapagos
        }

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        for card_id, expected_dex in expected.items():
            cur.execute(
                "SELECT c.pokemon_species_id, ps.national_dex_number "
                "FROM cards c JOIN pokemon_species ps ON c.pokemon_species_id = ps.id "
                "WHERE c.api_card_id = ?",
                (card_id,),
            )
            row = cur.fetchone()
            assert row is not None, f"Card {card_id} not found"
            assert row[1] == expected_dex, f"Card {card_id}: expected dex {expected_dex}, got {row[1]}"

        conn.close()

    def test_trainer_cards_have_no_species(self, tmp_path):
        """Trainer cards (no national_dex_number) have NULL species."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # mep-28 is Celebratory Fanfare (Trainer card, no dex)
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'mep-28'")
        row = cur.fetchone()
        assert row is not None
        assert row[0] is None  # No species for trainer cards

        conn.close()

    def test_updates_null_image_urls_on_existing_cards(self, tmp_path):
        """Cards that already exist with NULL image_url get updated with new images."""
        db_path = _create_test_db(tmp_path)

        # First run: seed all cards (they'll get image_url from JSON)
        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        # Now simulate the upgrade scenario: set image_url to NULL for a card that has one
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE cards SET image_url = NULL WHERE api_card_id = 'mep-37'")
        conn.commit()
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'mep-37'")
        assert cur.fetchone()[0] is None  # Confirmed NULL
        conn.close()

        # Second run: should populate the image_url
        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'mep-37'")
        row = cur.fetchone()
        assert row[0] is not None
        assert "assets.tcgdex.net" in row[0]
        assert "mep/037" in row[0]
        conn.close()

    def test_does_not_overwrite_existing_image_url(self, tmp_path):
        """Cards that already have a non-NULL image_url are not overwritten."""
        db_path = _create_test_db(tmp_path)

        # First run: seed all cards
        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        # Set a custom image URL on a card
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE cards SET image_url = 'https://custom.example.com/card.png' WHERE api_card_id = 'mep-37'")
        conn.commit()
        conn.close()

        # Second run: should NOT overwrite the custom URL
        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'mep-37'")
        row = cur.fetchone()
        assert row[0] == "https://custom.example.com/card.png"  # NOT overwritten
        conn.close()

    def test_cards_with_images_get_tcgdex_urls(self, tmp_path):
        """The 53 cards with available images get proper TCGdex CDN URLs."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _seed_supplementary_cards
            _seed_supplementary_cards()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Count cards with image URLs
        cur.execute("SELECT COUNT(*) FROM cards WHERE image_url IS NOT NULL")
        with_img = cur.fetchone()[0]
        assert with_img == 53

        # Verify MEP image URL format
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'mep-1'")
        assert cur.fetchone()[0] == "https://assets.tcgdex.net/en/me/mep/001/high.webp"

        # Verify SVP image URL format
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'svp-225'")
        assert cur.fetchone()[0] == "https://assets.tcgdex.net/en/sv/svp/225/high.webp"

        # Verify cards without images remain NULL
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'mep-46'")
        assert cur.fetchone()[0] is None

        conn.close()
