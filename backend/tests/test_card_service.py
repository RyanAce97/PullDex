"""Unit tests for app.services.card_service.

All tests use an in-memory SQLite database — no network calls, no disk writes.
"""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.card_service import (
    get_card_by_id,
    get_cards_by_national_dex_number,
    get_cards_by_set,
    get_cards_by_set_api_id,
    get_cards_by_species,
    search_cards_by_name,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    """In-memory SQLite session with the full schema created."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="sv1_set")
def sv1_set_fixture(session):
    tcg_set = Set(api_set_id="sv1", name="Scarlet & Violet", series="Scarlet & Violet")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)
    return tcg_set


@pytest.fixture(name="base1_set")
def base1_set_fixture(session):
    tcg_set = Set(api_set_id="base1", name="Base Set", series="Base")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)
    return tcg_set


@pytest.fixture(name="bulbasaur")
def bulbasaur_fixture(session):
    species = PokemonSpecies(national_dex_number=1, name="bulbasaur", generation=1)
    session.add(species)
    session.commit()
    session.refresh(species)
    return species


@pytest.fixture(name="pikachu")
def pikachu_fixture(session):
    species = PokemonSpecies(national_dex_number=25, name="pikachu", generation=1)
    session.add(species)
    session.commit()
    session.refresh(species)
    return species


def _make_card(
    session: Session,
    api_card_id: str,
    set_id: int | None = None,
    species_id: int | None = None,
    card_number: str = "001/198",
    rarity: str = "Common",
) -> Card:
    card = Card(
        api_card_id=api_card_id,
        set_id=set_id,
        pokemon_species_id=species_id,
        card_number=card_number,
        rarity=rarity,
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


# ---------------------------------------------------------------------------
# get_card_by_id
# ---------------------------------------------------------------------------

class TestGetCardById:
    def test_returns_card_when_found(self, session, sv1_set):
        card = _make_card(session, "sv1-1", set_id=sv1_set.id)
        result = get_card_by_id(session, card.id)
        assert result is not None
        assert result.id == card.id
        assert result.api_card_id == "sv1-1"

    def test_returns_none_when_not_found(self, session):
        result = get_card_by_id(session, 99999)
        assert result is None


# ---------------------------------------------------------------------------
# search_cards_by_name
# ---------------------------------------------------------------------------

class TestSearchCardsByName:
    def test_finds_card_by_species_name(self, session, sv1_set, bulbasaur):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        results = search_cards_by_name(session, "bulbasaur")
        assert len(results) == 1
        assert results[0].api_card_id == "sv1-1"

    def test_search_is_case_insensitive(self, session, sv1_set, bulbasaur):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        assert len(search_cards_by_name(session, "BULBASAUR")) == 1
        assert len(search_cards_by_name(session, "Bulbasaur")) == 1

    def test_partial_name_match(self, session, sv1_set, bulbasaur):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        results = search_cards_by_name(session, "bulb")
        assert len(results) == 1

    def test_finds_card_by_api_card_id(self, session, sv1_set):
        """Trainer cards (no species) should be found by api_card_id substring."""
        _make_card(session, "sv1-trainer-99", set_id=sv1_set.id, species_id=None)
        results = search_cards_by_name(session, "sv1-trainer")
        assert len(results) == 1
        assert results[0].api_card_id == "sv1-trainer-99"

    def test_returns_empty_for_no_match(self, session, sv1_set, bulbasaur):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        assert search_cards_by_name(session, "charizard") == []

    def test_returns_multiple_matches(self, session, sv1_set, bulbasaur, pikachu):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _make_card(session, "sv1-25", set_id=sv1_set.id, species_id=pikachu.id)
        # Both species names contain "a" — broad match to get both
        results = search_cards_by_name(session, "a")
        assert len(results) == 2

    def test_limit_is_respected(self, session, sv1_set, bulbasaur, pikachu):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _make_card(session, "sv1-25", set_id=sv1_set.id, species_id=pikachu.id)
        results = search_cards_by_name(session, "a", limit=1)
        assert len(results) == 1

    def test_offset_is_respected(self, session, sv1_set, bulbasaur, pikachu):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _make_card(session, "sv1-25", set_id=sv1_set.id, species_id=pikachu.id)
        all_results = search_cards_by_name(session, "a")
        offset_results = search_cards_by_name(session, "a", offset=1)
        assert len(offset_results) == len(all_results) - 1


# ---------------------------------------------------------------------------
# get_cards_by_set / get_cards_by_set_api_id
# ---------------------------------------------------------------------------

class TestGetCardsBySet:
    def test_returns_cards_for_set(self, session, sv1_set, base1_set, bulbasaur):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _make_card(session, "sv1-2", set_id=sv1_set.id)
        _make_card(session, "base1-1", set_id=base1_set.id)

        results = get_cards_by_set(session, sv1_set.id)
        assert len(results) == 2
        assert all(c.set_id == sv1_set.id for c in results)

    def test_returns_empty_for_unknown_set_id(self, session):
        assert get_cards_by_set(session, 99999) == []

    def test_returns_cards_by_api_set_id(self, session, sv1_set):
        _make_card(session, "sv1-1", set_id=sv1_set.id)
        _make_card(session, "sv1-2", set_id=sv1_set.id)

        results = get_cards_by_set_api_id(session, "sv1")
        assert len(results) == 2

    def test_returns_empty_for_unknown_api_set_id(self, session):
        assert get_cards_by_set_api_id(session, "unknown-set") == []

    def test_set_limit_is_respected(self, session, sv1_set):
        for i in range(5):
            _make_card(session, f"sv1-{i}", set_id=sv1_set.id)
        assert len(get_cards_by_set(session, sv1_set.id, limit=3)) == 3

    def test_set_offset_is_respected(self, session, sv1_set):
        for i in range(5):
            _make_card(session, f"sv1-{i}", set_id=sv1_set.id)
        all_cards = get_cards_by_set(session, sv1_set.id)
        offset_cards = get_cards_by_set(session, sv1_set.id, offset=2)
        assert len(offset_cards) == len(all_cards) - 2


# ---------------------------------------------------------------------------
# get_cards_by_species / get_cards_by_national_dex_number
# ---------------------------------------------------------------------------

class TestGetCardsBySpecies:
    def test_returns_all_cards_for_species(self, session, sv1_set, base1_set, bulbasaur, pikachu):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _make_card(session, "base1-1", set_id=base1_set.id, species_id=bulbasaur.id)
        _make_card(session, "sv1-25", set_id=sv1_set.id, species_id=pikachu.id)

        results = get_cards_by_species(session, bulbasaur.id)
        assert len(results) == 2
        assert all(c.pokemon_species_id == bulbasaur.id for c in results)

    def test_returns_empty_for_unknown_species_id(self, session):
        assert get_cards_by_species(session, 99999) == []

    def test_returns_cards_by_national_dex_number(self, session, sv1_set, bulbasaur):
        _make_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _make_card(session, "sv1-2", set_id=sv1_set.id, species_id=bulbasaur.id)

        results = get_cards_by_national_dex_number(session, 1)
        assert len(results) == 2

    def test_returns_empty_for_unknown_dex_number(self, session):
        assert get_cards_by_national_dex_number(session, 999) == []

    def test_species_limit_is_respected(self, session, sv1_set, bulbasaur):
        for i in range(5):
            _make_card(session, f"sv1-bulb-{i}", set_id=sv1_set.id, species_id=bulbasaur.id)
        assert len(get_cards_by_species(session, bulbasaur.id, limit=2)) == 2

    def test_species_offset_is_respected(self, session, sv1_set, bulbasaur):
        for i in range(4):
            _make_card(session, f"sv1-bulb-{i}", set_id=sv1_set.id, species_id=bulbasaur.id)
        all_cards = get_cards_by_species(session, bulbasaur.id)
        offset_cards = get_cards_by_species(session, bulbasaur.id, offset=2)
        assert len(offset_cards) == len(all_cards) - 2
