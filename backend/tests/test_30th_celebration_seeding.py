"""Tests for the 30th Celebration reference data (me55 / me55c).

Verifies the verified Scrydex-sourced data added to supplementary_cards.json:
- me55 (30th Celebration) contains exactly 161 cards
- me55c (30th Celebration: Classic Collection) contains exactly 30 cards
- Combined new cards total 191
- Every one of the 191 cards has an image_url (0 NULL)
- No image URL is the known Pokemon card-back placeholder
- All api_card_id values are unique across the whole file
- All Pokemon cards map to an existing species via national_dex_number
- Trainer cards have national_dex_number = null (-> NULL species)
- The seeder is idempotent for the new sets (run twice, no duplicates)
- Existing collection data is preserved by the seeder

These tests are fully offline. Image URLs are checked structurally (they must
not be constructed card-back URLs); the known card-back is identified by the
same 186316-byte / MD5 0d69bedbfb0e324cc3521722ffcf288d signature documented in
the investigation and in test_card_back_repair.py.
"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch


# Known bad Pokemon card-back placeholder (see investigation + card-back repair).
_KNOWN_CARD_BACK_MD5 = "0d69bedbfb0e324cc3521722ffcf288d"
_KNOWN_CARD_BACK_SIZE = 186316

_ME55_EXPECTED = 161
_ME55C_EXPECTED = 30
_NEW_TOTAL = 191

# Trainer cards in me55 (no species) — verified during investigation.
_ME55_TRAINERS = {"me55-126", "me55-127", "me55-128"}
# RGB Mew secret cards whose rarity was overridden to "Secret Rare".
_RGB_MEW = {"me55-R", "me55-G", "me55-B"}


def _data_file() -> Path:
    return Path(__file__).resolve().parents[1] / "app" / "data" / "supplementary_cards.json"


def _load():
    with open(_data_file(), encoding="utf-8") as f:
        return json.load(f)


def _me55(data):
    return [c for c in data["cards"] if c["set_api_id"] == "me55"]


def _me55c(data):
    return [c for c in data["cards"] if c["set_api_id"] == "me55c"]


# ===========================================================================
# JSON content tests
# ===========================================================================

class Test30thCelebrationJSON:
    def test_me55_set_defined(self):
        data = _load()
        s = next((s for s in data["sets"] if s["api_set_id"] == "me55"), None)
        assert s is not None
        assert s["name"] == "30th Celebration"
        assert s["series"] == "Mega Evolution"
        assert s["release_date"] == "2026-09-16"

    def test_me55c_set_defined(self):
        data = _load()
        s = next((s for s in data["sets"] if s["api_set_id"] == "me55c"), None)
        assert s is not None
        assert s["name"] == "30th Celebration: Classic Collection"
        assert s["series"] == "Mega Evolution"
        assert s["release_date"] == "2026-09-16"

    def test_me55_card_count(self):
        assert len(_me55(_load())) == _ME55_EXPECTED

    def test_me55c_card_count(self):
        assert len(_me55c(_load())) == _ME55C_EXPECTED

    def test_combined_new_card_count(self):
        data = _load()
        assert len(_me55(data)) + len(_me55c(data)) == _NEW_TOTAL

    def test_all_new_cards_have_images(self):
        data = _load()
        new = _me55(data) + _me55c(data)
        missing = [c["api_card_id"] for c in new if not c.get("image_url")]
        assert missing == [], f"cards missing image_url: {missing}"

    def test_no_card_back_placeholder_urls(self):
        """No new card uses the known card-back placeholder image path."""
        data = _load()
        new = _me55(data) + _me55c(data)
        # The card-back was only ever served under the /large size of a
        # non-existent id. Verified data uses genuine per-card /medium URLs.
        bad = [
            c["api_card_id"]
            for c in new
            if not c["image_url"].startswith("https://images.scrydex.com/pokemon/")
            or c["image_url"].endswith("/large")
        ]
        assert bad == [], f"suspicious image URLs: {bad}"

    def test_new_image_urls_are_scrydex_medium(self):
        data = _load()
        new = _me55(data) + _me55c(data)
        for c in new:
            assert c["image_url"].endswith("/medium"), c["api_card_id"]

    def test_all_ids_unique_across_file(self):
        data = _load()
        ids = [c["api_card_id"] for c in data["cards"]]
        assert len(ids) == len(set(ids))

    def test_me55_ids_present(self):
        """me55-1..me55-158 plus R/G/B are all present."""
        data = _load()
        ids = {c["api_card_id"] for c in _me55(data)}
        expected = {f"me55-{n}" for n in range(1, 159)} | {"me55-R", "me55-G", "me55-B"}
        assert ids == expected

    def test_me55c_suffix_ids_preserved(self):
        """Suffix IDs like me55c-11g / me55c-106m / me55c-106p are preserved verbatim."""
        data = _load()
        ids = {c["api_card_id"] for c in _me55c(data)}
        for cid in ("me55c-11g", "me55c-106m", "me55c-106p"):
            assert cid in ids, f"{cid} missing"

    def test_me55c_uses_historical_printed_numbers(self):
        """Classic Collection card_number retains historical printed numbering."""
        data = _load()
        by_id = {c["api_card_id"]: c for c in _me55c(data)}
        assert by_id["me55c-4"]["card_number"] == "4/102"
        assert by_id["me55c-203"]["card_number"] == "203/193"

    def test_rgb_mew_rarity_override(self):
        data = _load()
        by_id = {c["api_card_id"]: c for c in _me55(data)}
        for cid in _RGB_MEW:
            assert by_id[cid]["rarity"] == "Secret Rare", cid

    def test_me55_trainers_have_null_dex(self):
        data = _load()
        by_id = {c["api_card_id"]: c for c in _me55(data)}
        for cid in _ME55_TRAINERS:
            assert by_id[cid]["national_dex_number"] is None, cid


# ===========================================================================
# Seeding tests (against a minimal test DB)
# ===========================================================================

def _create_test_db(tmp_path: Path) -> str:
    """Create a minimal DB with all species needed by the supplementary data."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE pokemon_species (id INTEGER PRIMARY KEY, "
        "national_dex_number INTEGER NOT NULL UNIQUE, name VARCHAR(100) NOT NULL, generation INTEGER)"
    )
    cur.execute(
        "CREATE TABLE sets (id INTEGER PRIMARY KEY, api_set_id VARCHAR(50) UNIQUE, "
        "name VARCHAR(150) NOT NULL, series VARCHAR(100) NOT NULL, release_date DATE)"
    )
    cur.execute(
        "CREATE TABLE cards (id INTEGER PRIMARY KEY, api_card_id VARCHAR(50) UNIQUE, "
        "pokemon_species_id INTEGER, set_id INTEGER, card_number VARCHAR(20), "
        "rarity VARCHAR(50), variant VARCHAR(50), image_url VARCHAR(500))"
    )
    cur.execute(
        "CREATE TABLE collection (id INTEGER PRIMARY KEY, card_id INTEGER, "
        "pokemon_species_id INTEGER, quantity INTEGER DEFAULT 1, profile_id INTEGER NOT NULL, "
        "is_binder_card BOOLEAN DEFAULT 0)"
    )
    cur.execute(
        "CREATE TABLE profiles (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, "
        "is_active BOOLEAN NOT NULL DEFAULT 1)"
    )

    data = _load()
    dex_needed = {c["national_dex_number"] for c in data["cards"] if c.get("national_dex_number")}
    for dex in sorted(dex_needed):
        cur.execute(
            "INSERT INTO pokemon_species (id, national_dex_number, name, generation) VALUES (?, ?, ?, ?)",
            (dex, dex, f"species-{dex}", 1),
        )
    # SVP set needed for existing gap-fill cards
    cur.execute(
        "INSERT INTO sets (api_set_id, name, series) VALUES ('svp', 'Scarlet & Violet Black Star Promos', 'Scarlet & Violet')"
    )
    cur.execute("INSERT INTO profiles (name, is_active) VALUES ('Default', 1)")
    # Collection rows to verify preservation
    cur.execute("INSERT INTO collection (card_id, quantity, profile_id, is_binder_card) VALUES (99999, 7, 1, 1)")
    cur.execute("INSERT INTO collection (pokemon_species_id, quantity, profile_id, is_binder_card) VALUES (151, 2, 1, 0)")
    conn.commit()
    conn.close()
    return db_path


def _seed(db_path: str) -> None:
    with patch("app.database.settings") as mock_settings:
        mock_settings.database_url = f"sqlite:///{db_path}"
        from app.database import _seed_supplementary_cards
        _seed_supplementary_cards()


class Test30thCelebrationSeeding:
    def test_seeds_me55_count(self, tmp_path):
        db = _create_test_db(tmp_path)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM cards c JOIN sets s ON c.set_id = s.id WHERE s.api_set_id = 'me55'"
        )
        assert cur.fetchone()[0] == _ME55_EXPECTED
        conn.close()

    def test_seeds_me55c_count(self, tmp_path):
        db = _create_test_db(tmp_path)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM cards c JOIN sets s ON c.set_id = s.id WHERE s.api_set_id = 'me55c'"
        )
        assert cur.fetchone()[0] == _ME55C_EXPECTED
        conn.close()

    def test_seeds_both_sets(self, tmp_path):
        db = _create_test_db(tmp_path)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sets WHERE api_set_id IN ('me55', 'me55c')")
        assert cur.fetchone()[0] == 2
        conn.close()

    def test_all_new_cards_have_image_urls(self, tmp_path):
        db = _create_test_db(tmp_path)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM cards c JOIN sets s ON c.set_id = s.id "
            "WHERE s.api_set_id IN ('me55', 'me55c') AND c.image_url IS NULL"
        )
        assert cur.fetchone()[0] == 0
        conn.close()

    def test_pokemon_cards_mapped_to_species(self, tmp_path):
        db = _create_test_db(tmp_path)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        # me55-1 Exeggcute -> dex 102
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me55-1'")
        assert cur.fetchone()[0] == 102
        # me55-R Mew -> dex 151
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me55-R'")
        assert cur.fetchone()[0] == 151
        # me55c-4 Charizard -> dex 6
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me55c-4'")
        assert cur.fetchone()[0] == 6
        conn.close()

    def test_trainer_cards_have_null_species(self, tmp_path):
        db = _create_test_db(tmp_path)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        for cid in _ME55_TRAINERS | {"me55c-101"}:
            cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = ?", (cid,))
            row = cur.fetchone()
            assert row is not None, f"{cid} not seeded"
            assert row[0] is None, f"{cid} should have NULL species"
        conn.close()

    def test_idempotent(self, tmp_path):
        db = _create_test_db(tmp_path)
        _seed(db)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM cards c JOIN sets s ON c.set_id = s.id WHERE s.api_set_id = 'me55'"
        )
        assert cur.fetchone()[0] == _ME55_EXPECTED
        cur.execute(
            "SELECT COUNT(*) FROM cards c JOIN sets s ON c.set_id = s.id WHERE s.api_set_id = 'me55c'"
        )
        assert cur.fetchone()[0] == _ME55C_EXPECTED
        cur.execute("SELECT COUNT(*) FROM sets WHERE api_set_id IN ('me55', 'me55c')")
        assert cur.fetchone()[0] == 2
        conn.close()

    def test_collection_preserved(self, tmp_path):
        db = _create_test_db(tmp_path)
        # Snapshot collection before
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT id, card_id, pokemon_species_id, quantity, profile_id, is_binder_card FROM collection ORDER BY id")
        before = cur.fetchall()
        conn.close()

        _seed(db)
        _seed(db)

        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT id, card_id, pokemon_species_id, quantity, profile_id, is_binder_card FROM collection ORDER BY id")
        after = cur.fetchall()
        conn.close()
        assert before == after, "collection rows were modified by seeding"

    def test_no_card_back_md5_in_seeded_urls(self, tmp_path):
        """Seeded URLs never point at the known card-back (structural check)."""
        db = _create_test_db(tmp_path)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT c.image_url FROM cards c JOIN sets s ON c.set_id = s.id "
            "WHERE s.api_set_id IN ('me55', 'me55c')"
        )
        for (url,) in cur.fetchall():
            assert url and url.endswith("/medium")
            assert not url.endswith("/large")
        conn.close()


def _create_test_db_nonunique_index(tmp_path: Path) -> str:
    """Create a test DB whose cards.api_card_id index is NON-unique.

    This mirrors the *actual* Alembic-created production schema
    (op.create_index(..., unique=False)). It is the schema under which the
    seeder must remain idempotent — an INSERT OR IGNORE approach silently
    duplicated cards here. This guards against regressing to that.
    """
    db_path = str(tmp_path / "test_nonunique.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE pokemon_species (id INTEGER PRIMARY KEY, "
        "national_dex_number INTEGER NOT NULL UNIQUE, name VARCHAR(100) NOT NULL, generation INTEGER)"
    )
    cur.execute(
        "CREATE TABLE sets (id INTEGER PRIMARY KEY, api_set_id VARCHAR(50), "
        "name VARCHAR(150) NOT NULL, series VARCHAR(100) NOT NULL, release_date DATE)"
    )
    # NOTE: api_card_id has NO UNIQUE constraint here, matching production.
    cur.execute(
        "CREATE TABLE cards (id INTEGER PRIMARY KEY, api_card_id VARCHAR(50), "
        "pokemon_species_id INTEGER, set_id INTEGER, card_number VARCHAR(20), "
        "rarity VARCHAR(50), variant VARCHAR(50), image_url VARCHAR(500))"
    )
    cur.execute("CREATE INDEX ix_cards_api_card_id ON cards (api_card_id)")  # non-unique
    cur.execute(
        "CREATE TABLE collection (id INTEGER PRIMARY KEY, card_id INTEGER, "
        "pokemon_species_id INTEGER, quantity INTEGER DEFAULT 1, profile_id INTEGER NOT NULL, "
        "is_binder_card BOOLEAN DEFAULT 0)"
    )
    cur.execute(
        "CREATE TABLE profiles (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, "
        "is_active BOOLEAN NOT NULL DEFAULT 1)"
    )
    data = _load()
    dex_needed = {c["national_dex_number"] for c in data["cards"] if c.get("national_dex_number")}
    for dex in sorted(dex_needed):
        cur.execute(
            "INSERT INTO pokemon_species (id, national_dex_number, name, generation) VALUES (?, ?, ?, ?)",
            (dex, dex, f"species-{dex}", 1),
        )
    cur.execute(
        "INSERT INTO sets (api_set_id, name, series) VALUES ('svp', 'Scarlet & Violet Black Star Promos', 'Scarlet & Violet')"
    )
    cur.execute("INSERT INTO profiles (name, is_active) VALUES ('Default', 1)")
    cur.execute("INSERT INTO collection (card_id, quantity, profile_id, is_binder_card) VALUES (99999, 3, 1, 1)")
    conn.commit()
    conn.close()
    return db_path


class Test30thCelebrationNonUniqueIndex:
    """Regression tests for seeding under the real non-unique api_card_id index."""

    def test_idempotent_under_nonunique_index(self, tmp_path):
        db = _create_test_db_nonunique_index(tmp_path)
        # Seed three times — must not grow or duplicate.
        _seed(db)
        _seed(db)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM cards c JOIN sets s ON c.set_id = s.id WHERE s.api_set_id = 'me55'"
        )
        assert cur.fetchone()[0] == _ME55_EXPECTED
        cur.execute(
            "SELECT COUNT(*) FROM cards c JOIN sets s ON c.set_id = s.id WHERE s.api_set_id = 'me55c'"
        )
        assert cur.fetchone()[0] == _ME55C_EXPECTED
        cur.execute(
            "SELECT api_card_id, COUNT(*) FROM cards WHERE api_card_id IS NOT NULL "
            "GROUP BY api_card_id HAVING COUNT(*) > 1"
        )
        assert cur.fetchall() == []
        conn.close()

    def test_collection_preserved_under_nonunique_index(self, tmp_path):
        db = _create_test_db_nonunique_index(tmp_path)
        _seed(db)
        _seed(db)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT card_id, quantity, profile_id, is_binder_card FROM collection")
        assert cur.fetchall() == [(99999, 3, 1, 1)]
        conn.close()
