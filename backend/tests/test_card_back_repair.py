"""Tests for the card-back image repair mechanism (_repair_card_back_images).

Verifies that:
- 48 McDonald's cards get corrected from card-back to Scrydex front URLs
- mep-Museum gets set to NULL (no legitimate front image available)
- The operation is idempotent
- Existing correct images are not overwritten
- Collection/profile/binder data is never touched
"""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


def _create_test_db(tmp_path: Path) -> str:
    """Create a test database with the affected cards and collection data."""
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

    # Create sets
    cur.execute("INSERT INTO sets (id, api_set_id, name, series) VALUES (1, 'mcd14', 'McD 2014', 'Other')")
    cur.execute("INSERT INTO sets (id, api_set_id, name, series) VALUES (2, 'mcd15', 'McD 2015', 'Other')")
    cur.execute("INSERT INTO sets (id, api_set_id, name, series) VALUES (3, 'mcd17', 'McD 2017', 'Other')")
    cur.execute("INSERT INTO sets (id, api_set_id, name, series) VALUES (4, 'mcd18', 'McD 2018', 'Other')")
    cur.execute("INSERT INTO sets (id, api_set_id, name, series) VALUES (5, 'mep', 'MEP Black Star Promos', 'Mega Evolution')")

    # Create some species
    cur.execute("INSERT INTO pokemon_species (id, national_dex_number, name, generation) VALUES (25, 25, 'pikachu', 1)")
    cur.execute("INSERT INTO pokemon_species (id, national_dex_number, name, generation) VALUES (58, 58, 'growlithe', 1)")

    # Create the affected cards with known-bad URLs
    card_id = 1
    for set_id, set_api_id in [(1, 'mcd14'), (2, 'mcd15'), (3, 'mcd17'), (4, 'mcd18')]:
        for i in range(1, 13):
            cur.execute(
                "INSERT INTO cards (id, api_card_id, set_id, card_number, image_url) VALUES (?, ?, ?, ?, ?)",
                (card_id, f"{set_api_id}-{i}", set_id, str(i),
                 f"https://images.pokemontcg.io/{set_api_id}/{i}_hires.png"),
            )
            card_id += 1

    # mep-Museum with bad Scrydex URL
    cur.execute(
        "INSERT INTO cards (id, api_card_id, set_id, card_number, pokemon_species_id, image_url) VALUES (?, ?, ?, ?, ?, ?)",
        (card_id, "mep-Museum", 5, "Museum", 25, "https://images.scrydex.com/pokemon/mep-Museum/large"),
    )
    card_id += 1

    # A card with a GOOD image that should NOT be touched
    cur.execute(
        "INSERT INTO cards (id, api_card_id, set_id, card_number, image_url) VALUES (?, ?, ?, ?, ?)",
        (card_id, "sv1-1", 1, "1", "https://images.pokemontcg.io/sv1/1_hires.png"),
    )

    # Collection and profile data
    cur.execute("INSERT INTO profiles (id, name, is_active) VALUES (1, 'Default', 1)")
    cur.execute("INSERT INTO collection (id, card_id, quantity, profile_id, is_binder_card) VALUES (1, 1, 3, 1, 1)")
    cur.execute("INSERT INTO collection (id, card_id, quantity, profile_id, is_binder_card) VALUES (2, 2, 1, 1, 0)")

    conn.commit()
    conn.close()
    return db_path


class TestRepairCardBackImages:
    """Tests for the card-back image repair function."""

    def test_corrects_48_mcdonalds_cards(self, tmp_path):
        """All 48 McDonald's cards get Scrydex front URLs."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        for set_id in ['mcd14', 'mcd15', 'mcd17', 'mcd18']:
            for i in range(1, 13):
                card_id = f"{set_id}-{i}"
                cur.execute("SELECT image_url FROM cards WHERE api_card_id = ?", (card_id,))
                row = cur.fetchone()
                expected = f"https://images.scrydex.com/pokemon/{card_id}/large"
                assert row[0] == expected, f"{card_id}: got {row[0]}"

        conn.close()

    def test_sets_mep_museum_to_null(self, tmp_path):
        """mep-Museum is removed (oversized card) when no collection references exist."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards WHERE api_card_id = 'mep-Museum'")
        assert cur.fetchone()[0] == 0  # Deleted as oversized
        conn.close()

    def test_idempotent(self, tmp_path):
        """Running the repair twice produces the same result."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'mcd18-1'")
        assert cur.fetchone()[0] == "https://images.scrydex.com/pokemon/mcd18-1/large"
        cur.execute("SELECT COUNT(*) FROM cards WHERE api_card_id = 'mep-Museum'")
        assert cur.fetchone()[0] == 0  # Deleted as oversized
        conn.close()

    def test_preserves_correct_images(self, tmp_path):
        """Cards with correct (non-card-back) images are not modified."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'sv1-1'")
        row = cur.fetchone()
        assert row[0] == "https://images.pokemontcg.io/sv1/1_hires.png"
        conn.close()

    def test_does_not_overwrite_already_correct_scrydex_url(self, tmp_path):
        """If a McDonald's card already has the correct Scrydex URL, don't touch it."""
        db_path = _create_test_db(tmp_path)

        # Pre-fix one card manually
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "UPDATE cards SET image_url = 'https://images.scrydex.com/pokemon/mcd18-1/large' WHERE api_card_id = 'mcd18-1'"
        )
        conn.commit()
        conn.close()

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'mcd18-1'")
        assert cur.fetchone()[0] == "https://images.scrydex.com/pokemon/mcd18-1/large"
        conn.close()

    def test_never_touches_collection(self, tmp_path):
        """Collection data is unchanged after repair."""
        db_path = _create_test_db(tmp_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM collection ORDER BY id")
        before = cur.fetchall()
        conn.close()

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM collection ORDER BY id")
        after = cur.fetchall()
        conn.close()

        assert before == after

    def test_never_touches_profiles(self, tmp_path):
        """Profile data is unchanged after repair."""
        db_path = _create_test_db(tmp_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM profiles ORDER BY id")
        before = cur.fetchall()
        conn.close()

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM profiles ORDER BY id")
        after = cur.fetchall()
        conn.close()

        assert before == after

    def test_corrected_urls_use_scrydex(self, tmp_path):
        """All corrected URLs use the Scrydex CDN pattern."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT image_url FROM cards
            WHERE api_card_id LIKE 'mcd14-%' OR api_card_id LIKE 'mcd15-%'
            OR api_card_id LIKE 'mcd17-%' OR api_card_id LIKE 'mcd18-%'
        """)
        for row in cur.fetchall():
            assert row[0].startswith("https://images.scrydex.com/pokemon/")
            assert row[0].endswith("/large")
        conn.close()

    def test_mep_museum_not_card_back_after_repair(self, tmp_path):
        """mep-Museum does not contain the known card-back URL after repair."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM cards WHERE api_card_id = 'mep-Museum'")
        row = cur.fetchone()
        # Should be deleted (no collection refs) or NULL
        assert row is None or row[0] is None or row[0] != "https://images.scrydex.com/pokemon/mep-Museum/large"
        conn.close()

    def test_removes_oversized_mep_museum(self, tmp_path):
        """mep-Museum is removed if no collection references exist."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards WHERE api_card_id = 'mep-Museum'")
        assert cur.fetchone()[0] == 0
        conn.close()

    def test_removes_oversized_svp_500(self, tmp_path):
        """svp-500 is removed if no collection references exist."""
        db_path = _create_test_db(tmp_path)

        # Add svp-500 to the test DB
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO cards (api_card_id, set_id, card_number, image_url) VALUES ('svp-500', 1, '500', 'https://example.com/img.png')"
        )
        conn.commit()
        conn.close()

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards WHERE api_card_id = 'svp-500'")
        assert cur.fetchone()[0] == 0
        conn.close()

    def test_preserves_oversized_card_with_collection_reference(self, tmp_path):
        """Oversized cards with collection references are NOT deleted."""
        db_path = _create_test_db(tmp_path)

        # Add a collection entry referencing mep-Museum
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT id FROM cards WHERE api_card_id = 'mep-Museum'")
        museum_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO collection (card_id, quantity, profile_id, is_binder_card) VALUES (?, 1, 1, 0)",
            (museum_id,),
        )
        conn.commit()
        conn.close()

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # Card should still exist because it has a collection reference
        cur.execute("SELECT COUNT(*) FROM cards WHERE api_card_id = 'mep-Museum'")
        assert cur.fetchone()[0] == 1
        # Collection entry should be unchanged
        cur.execute("SELECT quantity FROM collection WHERE card_id = ?", (museum_id,))
        assert cur.fetchone()[0] == 1
        conn.close()

    def test_oversized_cleanup_idempotent(self, tmp_path):
        """Running the cleanup twice doesn't cause errors."""
        db_path = _create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_back_images
            _repair_card_back_images()
            _repair_card_back_images()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards WHERE api_card_id = 'mep-Museum'")
        assert cur.fetchone()[0] == 0
        conn.close()
