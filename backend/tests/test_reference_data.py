"""Tests for reference-data improvements: TCGdex client, supplementary importer,
species validator, and repair mechanism enhancement.

All tests use in-memory SQLite databases and mocked API responses — no network
calls and no disk writes.
"""

from unittest.mock import MagicMock, patch, PropertyMock
from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    """Provide an in-memory SQLite session with the full schema created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="mep_set")
def mep_set_fixture(session):
    """A persisted Set row for MEP Black Star Promos."""
    tcg_set = Set(api_set_id="mep", name="MEP Black Star Promos", series="Mega Evolution")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)
    return tcg_set


@pytest.fixture(name="svp_set")
def svp_set_fixture(session):
    """A persisted Set row for SVP."""
    tcg_set = Set(api_set_id="svp", name="Scarlet & Violet Black Star Promos", series="Scarlet & Violet")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)
    return tcg_set


@pytest.fixture(name="me2pt5_set")
def me2pt5_set_fixture(session):
    """A persisted Set row for Ascended Heroes."""
    tcg_set = Set(api_set_id="me2pt5", name="Ascended Heroes", series="Mega Evolution")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)
    return tcg_set


@pytest.fixture(name="starter_species")
def starter_species_fixture(session):
    """Create starter species for testing First Partner cards."""
    species_data = [
        (1, "bulbasaur", 1),
        (4, "charmander", 1),
        (7, "squirtle", 1),
        (25, "pikachu", 1),
        (183, "marill", 2),
        (184, "azumarill", 2),
        (252, "treecko", 3),
        (387, "turtwig", 4),
        (390, "chimchar", 4),
        (393, "piplup", 4),
    ]
    species = []
    for dex, name, gen in species_data:
        s = PokemonSpecies(national_dex_number=dex, name=name, generation=gen)
        session.add(s)
        species.append(s)
    session.commit()
    for s in species:
        session.refresh(s)
    return species


# ===========================================================================
# TCGdex Client Tests
# ===========================================================================

class TestTCGdexClient:
    """Tests for the TCGdex API client."""

    def test_client_initializes(self):
        """Client can be instantiated."""
        from app.services.api.tcgdex_client import TCGdexClient
        client = TCGdexClient(timeout=5.0)
        client.close()

    def test_client_context_manager(self):
        """Client works as a context manager."""
        from app.services.api.tcgdex_client import TCGdexClient
        with TCGdexClient(timeout=5.0) as client:
            assert client is not None

    @patch("app.services.api.tcgdex_client.TCGdexClient._get_with_retry")
    def test_get_sets(self, mock_get):
        """get_sets returns parsed JSON."""
        from app.services.api.tcgdex_client import TCGdexClient

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "mep", "name": "MEP Black Star Promos"},
            {"id": "svp", "name": "SVP Black Star Promos"},
        ]
        mock_get.return_value = mock_response

        with TCGdexClient() as client:
            result = client.get_sets()
            assert len(result) == 2
            assert result[0]["id"] == "mep"

    @patch("app.services.api.tcgdex_client.TCGdexClient._get_with_retry")
    def test_get_set(self, mock_get):
        """get_set returns set with cards."""
        from app.services.api.tcgdex_client import TCGdexClient

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "mep",
            "name": "MEP Black Star Promos",
            "cards": [
                {"id": "mep-037", "localId": "037", "name": "Bulbasaur"},
            ],
        }
        mock_get.return_value = mock_response

        with TCGdexClient() as client:
            result = client.get_set("mep")
            assert result["name"] == "MEP Black Star Promos"
            assert len(result["cards"]) == 1

    @patch("app.services.api.tcgdex_client.TCGdexClient._get_with_retry")
    def test_get_card(self, mock_get):
        """get_card returns full card data."""
        from app.services.api.tcgdex_client import TCGdexClient

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "me02.5-084",
            "name": "Azumarill ex",
            "dexId": [184],
            "category": "Pokemon",
            "evolveFrom": "Marill",
            "stage": "Stage1",
        }
        mock_get.return_value = mock_response

        with TCGdexClient() as client:
            result = client.get_card("me02.5-084")
            assert result["name"] == "Azumarill ex"
            assert result["dexId"] == [184]


# ===========================================================================
# TCGdex Importer Tests
# ===========================================================================

class TestTCGdexImporter:
    """Tests for the supplementary importer."""

    def test_tcgdex_card_id_to_api_format_new_set(self):
        """Cards in new sets use TCGdex set ID directly."""
        from app.services.importers.tcgdex_importer import _tcgdex_card_id_to_api_format

        assert _tcgdex_card_id_to_api_format("mep", "037") == "mep-37"
        assert _tcgdex_card_id_to_api_format("mep", "001") == "mep-1"
        assert _tcgdex_card_id_to_api_format("mep", "Museum") == "mep-Museum"

    def test_tcgdex_card_id_to_api_format_existing_set(self):
        """Cards in known sets use the Pokémon TCG API format."""
        from app.services.importers.tcgdex_importer import _tcgdex_card_id_to_api_format

        assert _tcgdex_card_id_to_api_format("svp", "208") == "svp-208"
        assert _tcgdex_card_id_to_api_format("me02.5", "084") == "me2pt5-84"

    def test_resolve_species_for_pokemon_card(self, session, starter_species):
        """Species resolution works for Pokémon cards with dexId."""
        from app.services.importers.tcgdex_importer import _resolve_species_for_tcgdex_card

        card_data = {
            "category": "Pokemon",
            "name": "Bulbasaur",
            "dexId": [1],
        }
        result = _resolve_species_for_tcgdex_card(session, card_data)
        assert result is not None
        # Should resolve to bulbasaur (id depends on insert order)
        species = session.get(PokemonSpecies, result)
        assert species.name == "bulbasaur"

    def test_resolve_species_for_trainer_card(self, session, starter_species):
        """Trainer cards return None for species."""
        from app.services.importers.tcgdex_importer import _resolve_species_for_tcgdex_card

        card_data = {
            "category": "Trainer",
            "name": "Professor's Research",
        }
        result = _resolve_species_for_tcgdex_card(session, card_data)
        assert result is None

    def test_resolve_species_by_name_fallback(self, session, starter_species):
        """Name-based fallback works when dexId is missing."""
        from app.services.importers.tcgdex_importer import _resolve_species_for_tcgdex_card

        card_data = {
            "category": "Pokemon",
            "name": "Pikachu",
            "dexId": [],
        }
        result = _resolve_species_for_tcgdex_card(session, card_data)
        assert result is not None
        species = session.get(PokemonSpecies, result)
        assert species.name == "pikachu"

    def test_import_does_not_duplicate_existing_cards(self, session, mep_set, starter_species):
        """Importing a card that already exists skips it."""
        from app.services.importers.tcgdex_importer import (
            import_supplementary_set,
            ImportReport,
        )

        # Pre-create a card that will be "imported"
        existing_card = Card(
            api_card_id="mep-37",
            set_id=mep_set.id,
            pokemon_species_id=None,
            card_number="37",
        )
        session.add(existing_card)
        session.commit()

        # Mock the TCGdex client
        mock_client = MagicMock()
        mock_client.get_set.return_value = {
            "id": "mep",
            "name": "MEP Black Star Promos",
            "cards": [
                {"id": "mep-037", "localId": "037", "name": "Bulbasaur"},
            ],
        }

        report = ImportReport()
        import_supplementary_set(session, mock_client, "mep", report)

        assert len(report.cards_already_present) == 1
        assert len(report.cards_added) == 0
        assert "mep-37" in report.cards_already_present[0]

    def test_import_adds_new_cards(self, session, starter_species):
        """Importing a new set creates set and card records."""
        from app.services.importers.tcgdex_importer import (
            import_supplementary_set,
            ImportReport,
        )

        mock_client = MagicMock()
        mock_client.get_set.return_value = {
            "id": "mep",
            "name": "MEP Black Star Promos",
            "cards": [
                {"id": "mep-037", "localId": "037", "name": "Bulbasaur"},
            ],
        }
        mock_client.get_card.return_value = {
            "id": "mep-037",
            "name": "Bulbasaur",
            "category": "Pokemon",
            "dexId": [1],
            "rarity": "Illustration Rare",
            "image": "https://assets.tcgdex.net/en/me/mep/037",
        }

        report = ImportReport()
        import_supplementary_set(session, mock_client, "mep", report)
        session.commit()

        # Set should be created
        assert len(report.sets_added) == 1
        new_set = session.exec(select(Set).where(Set.api_set_id == "mep")).first()
        assert new_set is not None
        assert new_set.name == "MEP Black Star Promos"

        # Card should be created
        assert len(report.cards_added) == 1
        new_card = session.exec(select(Card).where(Card.api_card_id == "mep-37")).first()
        assert new_card is not None
        assert new_card.pokemon_species_id is not None

    def test_import_report_summary(self):
        """ImportReport.summary() produces readable output."""
        from app.services.importers.tcgdex_importer import ImportReport

        report = ImportReport(
            sets_added=["mep (MEP Black Star Promos)"],
            cards_added=["mep-37 (Bulbasaur)", "mep-38 (Charmander)"],
            cards_already_present=["svp-200 (Eevee)"],
            cards_unmatched=["mep-28 (Celebratory Fanfare)"],
        )
        summary = report.summary()
        assert "Sets added: 1" in summary
        assert "Cards added: 2" in summary
        assert "Cards already present: 1" in summary
        assert "Bulbasaur" in summary

    def test_import_is_idempotent(self, session, starter_species):
        """Running the same import twice doesn't create duplicates."""
        from app.services.importers.tcgdex_importer import (
            import_supplementary_set,
            ImportReport,
        )

        mock_client = MagicMock()
        mock_client.get_set.return_value = {
            "id": "mep",
            "name": "MEP Black Star Promos",
            "cards": [
                {"id": "mep-037", "localId": "037", "name": "Bulbasaur"},
            ],
        }
        mock_client.get_card.return_value = {
            "id": "mep-037",
            "name": "Bulbasaur",
            "category": "Pokemon",
            "dexId": [1],
            "rarity": "Illustration Rare",
            "image": "https://assets.tcgdex.net/en/me/mep/037",
        }

        # First import
        report1 = ImportReport()
        import_supplementary_set(session, mock_client, "mep", report1)
        session.commit()

        # Second import
        report2 = ImportReport()
        import_supplementary_set(session, mock_client, "mep", report2)
        session.commit()

        # First time: 1 card added
        assert len(report1.cards_added) == 1
        # Second time: card already present
        assert len(report2.cards_already_present) == 1
        assert len(report2.cards_added) == 0

        # Only 1 card in DB
        all_cards = session.exec(select(Card)).all()
        assert len(all_cards) == 1


# ===========================================================================
# Species Validator Tests
# ===========================================================================

class TestSpeciesValidator:
    """Tests for species-mapping validation."""

    def test_confirmed_corrections_includes_azumarill(self):
        """The confirmed corrections dict includes the Azumarill fix."""
        from app.services.importers.species_validator import get_confirmed_corrections

        corrections = get_confirmed_corrections()
        assert "me2pt5-84" in corrections
        assert corrections["me2pt5-84"] == 184

    def test_validate_detects_azumarill_mismatch(self, session, me2pt5_set, starter_species):
        """Validation detects when Azumarill ex is mapped to Marill."""
        from app.services.importers.species_validator import validate_species_mappings

        # Create the incorrectly mapped card
        marill = session.exec(
            select(PokemonSpecies).where(PokemonSpecies.name == "marill")
        ).first()
        card = Card(
            api_card_id="me2pt5-84",
            set_id=me2pt5_set.id,
            pokemon_species_id=marill.id,
            card_number="84",
            rarity="Double Rare",
        )
        session.add(card)
        session.commit()

        # Validate with TCGdex override
        with patch("app.services.importers.species_validator.get_session_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            report = validate_species_mappings(
                tcgdex_overrides={"me2pt5-84": 184}
            )

        assert len(report.conflicts) == 1
        conflict = report.conflicts[0]
        assert conflict.api_card_id == "me2pt5-84"
        assert conflict.current_dex == 183
        assert conflict.expected_dex == 184
        assert conflict.confidence == "high"

    def test_validate_no_false_positives(self, session, me2pt5_set, starter_species):
        """Correctly mapped cards produce no conflicts."""
        from app.services.importers.species_validator import validate_species_mappings

        # Create a correctly mapped card
        azumarill = session.exec(
            select(PokemonSpecies).where(PokemonSpecies.name == "azumarill")
        ).first()
        card = Card(
            api_card_id="me2pt5-84",
            set_id=me2pt5_set.id,
            pokemon_species_id=azumarill.id,
            card_number="84",
        )
        session.add(card)
        session.commit()

        with patch("app.services.importers.species_validator.get_session_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            report = validate_species_mappings(
                tcgdex_overrides={"me2pt5-84": 184}
            )

        assert len(report.conflicts) == 0


# ===========================================================================
# Repair Mechanism Tests
# ===========================================================================

class TestRepairMechanism:
    """Tests for the extended _repair_card_species_mapping() function."""

    def _create_test_db(self, tmp_path) -> str:
        """Create a test database with the minimal schema and test data."""
        import sqlite3

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        # Create tables
        cur.execute("""
            CREATE TABLE pokemon_species (
                id INTEGER PRIMARY KEY,
                national_dex_number INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                generation INTEGER
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

        # Insert species
        cur.execute("INSERT INTO pokemon_species VALUES (183, 183, 'marill', 2)")
        cur.execute("INSERT INTO pokemon_species VALUES (184, 184, 'azumarill', 2)")
        cur.execute("INSERT INTO pokemon_species VALUES (25, 25, 'pikachu', 1)")

        # Insert okidogi for Phase 1 test
        cur.execute("INSERT INTO pokemon_species VALUES (1014, 1014, 'okidogi', 9)")

        # Insert cards
        # Azumarill ex incorrectly mapped to Marill
        cur.execute("""
            INSERT INTO cards (id, api_card_id, pokemon_species_id, card_number, rarity)
            VALUES (1, 'me2pt5-84', 183, '84', 'Double Rare')
        """)
        # Okidogi with NULL mapping (Phase 1 test)
        cur.execute("""
            INSERT INTO cards (id, api_card_id, pokemon_species_id, card_number, rarity)
            VALUES (2, 'me2pt5-122', NULL, '122', 'Double Rare')
        """)
        # A correctly mapped Pikachu (should not be touched)
        cur.execute("""
            INSERT INTO cards (id, api_card_id, pokemon_species_id, card_number, rarity)
            VALUES (3, 'me2pt5-57', 25, '57', 'Double Rare')
        """)

        # Insert collection entries (should NEVER be modified)
        cur.execute("""
            INSERT INTO collection (id, card_id, quantity, profile_id, is_binder_card)
            VALUES (1, 1, 3, 1, 1)
        """)
        cur.execute("""
            INSERT INTO collection (id, card_id, quantity, profile_id, is_binder_card)
            VALUES (2, 3, 1, 1, 0)
        """)

        conn.commit()
        conn.close()
        return str(db_path)

    def test_phase1_repairs_null_mappings(self, tmp_path):
        """Phase 1 repairs cards with NULL pokemon_species_id."""
        import sqlite3

        db_path = self._create_test_db(tmp_path)

        # Patch settings to use our test DB
        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_species_mapping
            _repair_card_species_mapping()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me2pt5-122'")
        result = cur.fetchone()
        assert result[0] == 1014  # okidogi
        conn.close()

    def test_phase2_corrects_wrong_mappings(self, tmp_path):
        """Phase 2 corrects cards with wrong (non-NULL) species_id."""
        import sqlite3

        db_path = self._create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_species_mapping
            _repair_card_species_mapping()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me2pt5-84'")
        result = cur.fetchone()
        assert result[0] == 184  # azumarill (was 183 = marill)
        conn.close()

    def test_repair_does_not_touch_collection(self, tmp_path):
        """Repair never modifies collection entries."""
        import sqlite3

        db_path = self._create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_species_mapping
            _repair_card_species_mapping()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Check collection is unchanged
        cur.execute("SELECT COUNT(*) FROM collection")
        assert cur.fetchone()[0] == 2

        cur.execute("SELECT card_id, quantity, is_binder_card FROM collection ORDER BY id")
        rows = cur.fetchall()
        assert rows[0] == (1, 3, 1)  # Azumarill ex card, 3 copies, binder card
        assert rows[1] == (3, 1, 0)  # Pikachu, 1 copy, not binder

        conn.close()

    def test_repair_does_not_touch_correct_mappings(self, tmp_path):
        """Repair leaves correctly mapped cards unchanged."""
        import sqlite3

        db_path = self._create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_species_mapping
            _repair_card_species_mapping()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me2pt5-57'")
        result = cur.fetchone()
        assert result[0] == 25  # pikachu — unchanged
        conn.close()

    def test_repair_is_idempotent(self, tmp_path):
        """Running repair twice produces the same result."""
        import sqlite3

        db_path = self._create_test_db(tmp_path)

        with patch("app.database.settings") as mock_settings:
            mock_settings.database_url = f"sqlite:///{db_path}"
            from app.database import _repair_card_species_mapping
            _repair_card_species_mapping()
            _repair_card_species_mapping()

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me2pt5-84'")
        assert cur.fetchone()[0] == 184
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me2pt5-122'")
        assert cur.fetchone()[0] == 1014
        conn.close()

    def test_repair_requires_no_network(self, tmp_path):
        """Repair runs without any network imports (no httpx)."""
        import sqlite3

        db_path = self._create_test_db(tmp_path)

        # Block httpx import to prove it's not used
        import sys
        original_modules = sys.modules.copy()
        sys.modules["httpx"] = None  # type: ignore

        try:
            with patch("app.database.settings") as mock_settings:
                mock_settings.database_url = f"sqlite:///{db_path}"
                from app.database import _repair_card_species_mapping
                _repair_card_species_mapping()
        finally:
            sys.modules.update(original_modules)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT pokemon_species_id FROM cards WHERE api_card_id = 'me2pt5-84'")
        assert cur.fetchone()[0] == 184
        conn.close()


# ===========================================================================
# Data Safety Tests
# ===========================================================================

class TestDataSafety:
    """Tests for backup and collection verification."""

    def test_backup_creates_copy(self, tmp_path):
        """Backup creates a valid copy of the database."""
        import sqlite3

        # Create a source database
        src_path = tmp_path / "source.db"
        conn = sqlite3.connect(str(src_path))
        cur = conn.cursor()
        cur.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        cur.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()
        conn.close()

        # Backup using sqlite3 backup API
        src = sqlite3.connect(str(src_path))
        dst_path = tmp_path / "backup.db"
        dst = sqlite3.connect(str(dst_path))
        src.backup(dst)
        dst.close()
        src.close()

        # Verify backup
        conn = sqlite3.connect(str(dst_path))
        cur = conn.cursor()
        cur.execute("SELECT value FROM test WHERE id = 1")
        assert cur.fetchone()[0] == "hello"
        conn.close()

    def test_collection_state_detection(self, tmp_path):
        """Collection state changes are detected."""
        import sqlite3

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
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
        cur.execute("CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT, is_active BOOLEAN, created_at TEXT, binder_rows INTEGER, binder_columns INTEGER, binder_sort TEXT)")
        cur.execute("INSERT INTO profiles VALUES (1, 'Default', 1, '2026-01-01', 5, 4, 'dex_number')")
        cur.execute("INSERT INTO collection VALUES (1, 10, NULL, 3, 1, 1)")
        cur.execute("INSERT INTO collection VALUES (2, 20, NULL, 1, 1, 0)")
        conn.commit()
        conn.close()

        from app.scripts.reference_data_audit import _get_collection_state
        state = _get_collection_state(db_path)

        assert state["row_count"] == 2
        assert state["total_quantity"] == 4
        assert state["profile_count"] == 1
        assert state["binder_card_count"] == 1
