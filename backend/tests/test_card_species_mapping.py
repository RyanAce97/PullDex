"""Tests for card-to-species name-based fallback matching.

Tests the normalize_card_name function, _resolve_species_by_name,
and the full upsert_card flow with and without nationalPokedexNumbers.
"""

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.profile import Profile
from app.models.set import Set
from app.services.importers.card_importer import (
    normalize_card_name,
    _resolve_species_by_name,
    upsert_card,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    connection = engine.connect()
    SQLModel.metadata.create_all(connection)
    with Session(bind=connection) as session:
        yield session
    connection.close()


@pytest.fixture(name="species")
def species_fixture(session):
    """Create species for testing name matching."""
    species_data = [
        (25, "pikachu", 1),
        (6, "charizard", 1),
        (1014, "okidogi", 9),
        (1015, "munkidori", 9),
        (1016, "fezandipiti", 9),
        (1017, "ogerpon", 9),
        (1018, "archaludon", 9),
        (1019, "hydrapple", 9),
        (1020, "gouging-fire", 9),
        (1021, "raging-bolt", 9),
        (1022, "iron-boulder", 9),
        (1023, "iron-crown", 9),
        (1024, "terapagos", 9),
        (1025, "pecharunt", 9),
        (1011, "dipplin", 9),
        (1012, "poltchageist", 9),
        (1013, "sinistcha", 9),
        (787, "tapu-bulu", 7),
        (984, "great-tusk", 9),
        (987, "flutter-mane", 9),
        (1009, "walking-wake", 9),
    ]
    result = {}
    for dex, name, gen in species_data:
        s = PokemonSpecies(national_dex_number=dex, name=name, generation=gen)
        session.add(s)
        result[name] = s
    session.commit()
    for s in result.values():
        session.refresh(s)
    return result


@pytest.fixture(name="test_set")
def test_set_fixture(session):
    s = Set(api_set_id="sv6", name="Twilight Masquerade", series="Scarlet & Violet")
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


# ===========================================================================
# normalize_card_name tests
# ===========================================================================

class TestNormalizeCardName:
    def test_simple_name(self):
        assert normalize_card_name("Pikachu") == "pikachu"

    def test_ex_suffix(self):
        assert normalize_card_name("Iron Boulder ex") == "iron-boulder"

    def test_EX_suffix(self):
        assert normalize_card_name("Charizard EX") == "charizard"

    def test_V_suffix(self):
        assert normalize_card_name("Pikachu V") == "pikachu"

    def test_VMAX_suffix(self):
        assert normalize_card_name("Pikachu VMAX") == "pikachu"

    def test_VSTAR_suffix(self):
        assert normalize_card_name("Charizard VSTAR") == "charizard"

    def test_GX_suffix(self):
        assert normalize_card_name("Pikachu GX") == "pikachu"

    def test_hyphen_EX_suffix(self):
        assert normalize_card_name("Charizard-EX") == "charizard"

    def test_multi_word_pokemon(self):
        assert normalize_card_name("Raging Bolt ex") == "raging-bolt"

    def test_multi_word_no_suffix(self):
        assert normalize_card_name("Iron Boulder") == "iron-boulder"

    def test_three_word_name(self):
        assert normalize_card_name("Teal Mask Ogerpon") == "teal-mask-ogerpon"

    def test_three_word_with_suffix(self):
        assert normalize_card_name("Teal Mask Ogerpon ex") == "teal-mask-ogerpon"

    def test_preserves_already_normalized(self):
        assert normalize_card_name("okidogi") == "okidogi"


# ===========================================================================
# _resolve_species_by_name tests
# ===========================================================================

class TestResolveSpeciesByName:
    def test_exact_match(self, session, species):
        result = _resolve_species_by_name(session, "Okidogi")
        assert result == species["okidogi"].id

    def test_ex_suffix(self, session, species):
        result = _resolve_species_by_name(session, "Iron Boulder ex")
        assert result == species["iron-boulder"].id

    def test_multi_word_pokemon(self, session, species):
        result = _resolve_species_by_name(session, "Raging Bolt")
        assert result == species["raging-bolt"].id

    def test_ogerpon_form_teal(self, session, species):
        result = _resolve_species_by_name(session, "Teal Mask Ogerpon ex")
        assert result == species["ogerpon"].id

    def test_ogerpon_form_hearthflame(self, session, species):
        result = _resolve_species_by_name(session, "Hearthflame Mask Ogerpon ex")
        assert result == species["ogerpon"].id

    def test_ogerpon_form_cornerstone(self, session, species):
        result = _resolve_species_by_name(session, "Cornerstone Mask Ogerpon ex")
        assert result == species["ogerpon"].id

    def test_ogerpon_form_wellspring(self, session, species):
        result = _resolve_species_by_name(session, "Wellspring Mask Ogerpon ex")
        assert result == species["ogerpon"].id

    def test_tapu_bulu(self, session, species):
        result = _resolve_species_by_name(session, "Tapu Bulu")
        assert result == species["tapu-bulu"].id

    def test_buried_fossil_excluded(self, session, species):
        """Buried Fossil should NOT match any species."""
        result = _resolve_species_by_name(session, "Buried Fossil")
        assert result is None

    def test_unknown_pokemon_returns_none(self, session, species):
        """Completely unknown name returns None."""
        result = _resolve_species_by_name(session, "Totally Fake Pokemon")
        assert result is None

    def test_walking_wake(self, session, species):
        result = _resolve_species_by_name(session, "Walking Wake")
        assert result == species["walking-wake"].id

    def test_flutter_mane(self, session, species):
        result = _resolve_species_by_name(session, "Flutter Mane")
        assert result == species["flutter-mane"].id


# ===========================================================================
# upsert_card integration tests
# ===========================================================================

class TestUpsertCardSpeciesResolution:
    def test_dex_number_takes_priority(self, session, species, test_set):
        """When nationalPokedexNumbers is present, it takes priority."""
        data = {
            "id": "test-1",
            "name": "Pikachu",
            "supertype": "Pokémon",
            "nationalPokedexNumbers": [25],
            "set": {"id": "sv6"},
            "number": "1",
            "rarity": "Common",
            "images": None,
        }
        card = upsert_card(session, data)
        session.commit()
        assert card.pokemon_species_id == species["pikachu"].id

    def test_name_fallback_when_no_dex(self, session, species, test_set):
        """When nationalPokedexNumbers is empty, falls back to name matching."""
        data = {
            "id": "test-2",
            "name": "Okidogi",
            "supertype": "Pokémon",
            "nationalPokedexNumbers": [],
            "set": {"id": "sv6"},
            "number": "111",
            "rarity": "Rare",
            "images": None,
        }
        card = upsert_card(session, data)
        session.commit()
        assert card.pokemon_species_id == species["okidogi"].id

    def test_name_fallback_with_ex_suffix(self, session, species, test_set):
        """Name matching works with ex suffix."""
        data = {
            "id": "test-3",
            "name": "Iron Boulder ex",
            "supertype": "Pokémon",
            "set": {"id": "sv6"},
            "number": "99",
            "rarity": "Double Rare",
            "images": None,
        }
        card = upsert_card(session, data)
        session.commit()
        assert card.pokemon_species_id == species["iron-boulder"].id

    def test_trainer_never_matched_by_name(self, session, species, test_set):
        """Trainer cards are never matched by name even if name looks like a Pokémon."""
        data = {
            "id": "test-4",
            "name": "Pikachu's Friend",
            "supertype": "Trainer",
            "set": {"id": "sv6"},
            "number": "200",
            "rarity": "Uncommon",
            "images": None,
        }
        card = upsert_card(session, data)
        session.commit()
        assert card.pokemon_species_id is None

    def test_energy_never_matched_by_name(self, session, species, test_set):
        """Energy cards are never matched by name."""
        data = {
            "id": "test-5",
            "name": "Fire Energy",
            "supertype": "Energy",
            "set": {"id": "sv6"},
            "number": "201",
            "rarity": None,
            "images": None,
        }
        card = upsert_card(session, data)
        session.commit()
        assert card.pokemon_species_id is None

    def test_buried_fossil_not_matched(self, session, species, test_set):
        """Buried Fossil is excluded even with supertype=Pokémon."""
        data = {
            "id": "ecard3-47",
            "name": "Buried Fossil",
            "supertype": "Pokémon",
            "set": {"id": "sv6"},
            "number": "47",
            "rarity": "Common",
            "images": None,
        }
        card = upsert_card(session, data)
        session.commit()
        assert card.pokemon_species_id is None

    def test_rerun_is_idempotent(self, session, species, test_set):
        """Running upsert_card twice produces the same result."""
        data = {
            "id": "test-6",
            "name": "Okidogi",
            "supertype": "Pokémon",
            "nationalPokedexNumbers": [],
            "set": {"id": "sv6"},
            "number": "111",
            "rarity": "Rare",
            "images": None,
        }
        card1 = upsert_card(session, data)
        session.commit()
        card2 = upsert_card(session, data)
        session.commit()
        assert card1.id == card2.id
        assert card2.pokemon_species_id == species["okidogi"].id

    def test_collection_entries_unchanged(self, session, species, test_set):
        """Re-running upsert doesn't affect existing collection entries."""
        # Create profile and collection entry
        profile = Profile(name="Test", is_active=True)
        session.add(profile)
        session.commit()
        session.refresh(profile)

        # Create a card and collection entry
        data = {
            "id": "test-7",
            "name": "Pikachu",
            "supertype": "Pokémon",
            "nationalPokedexNumbers": [25],
            "set": {"id": "sv6"},
            "number": "25",
            "rarity": "Common",
            "images": None,
        }
        card = upsert_card(session, data)
        session.commit()

        entry = Collection(profile_id=profile.id, card_id=card.id, quantity=3)
        session.add(entry)
        session.commit()
        session.refresh(entry)

        # Re-run upsert
        upsert_card(session, data)
        session.commit()

        # Collection entry unchanged
        refreshed = session.get(Collection, entry.id)
        assert refreshed is not None
        assert refreshed.quantity == 3
        assert refreshed.card_id == card.id

    def test_unresolved_pokemon_remains_null(self, session, species, test_set):
        """A Pokémon card that can't be matched stays NULL."""
        data = {
            "id": "test-8",
            "name": "Completely Unknown Monster",
            "supertype": "Pokémon",
            "set": {"id": "sv6"},
            "number": "999",
            "rarity": "Rare",
            "images": None,
        }
        card = upsert_card(session, data)
        session.commit()
        assert card.pokemon_species_id is None
