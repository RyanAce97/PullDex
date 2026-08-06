"""Tests for the GET /species/summary endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.schemas.species_summary import SpeciesSummaryRead


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


@pytest.fixture(name="client")
def client_fixture(session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _species(session: Session, dex: int, name: str) -> PokemonSpecies:
    s = PokemonSpecies(national_dex_number=dex, name=name, generation=1)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _set(session: Session, api_set_id: str) -> Set:
    s = Set(api_set_id=api_set_id, name="Test Set", series="Test")
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _card(session: Session, api_card_id: str, tcg_set: Set, species: PokemonSpecies) -> Card:
    c = Card(api_card_id=api_card_id, set_id=tcg_set.id, pokemon_species_id=species.id)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _collect(session: Session, card: Card) -> Collection:
    e = Collection(card_id=card.id)
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSpeciesSummary:
    def test_empty_database_returns_empty_list(self, client):
        response = client.get("/species/summary")
        assert response.status_code == 200
        assert response.json() == []

    def test_species_with_no_cards_is_not_owned(self, client, session):
        _species(session, 1, "bulbasaur")

        data = client.get("/species/summary").json()

        assert len(data) == 1
        assert data[0]["name"] == "bulbasaur"
        assert data[0]["owned"] is False

    def test_species_with_cards_but_none_collected_is_not_owned(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        tcg_set = _set(session, "sv1")
        _card(session, "sv1-1", tcg_set, bulbasaur)

        data = client.get("/species/summary").json()

        assert data[0]["owned"] is False

    def test_species_becomes_owned_when_any_card_collected(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        tcg_set = _set(session, "sv1")
        card = _card(session, "sv1-1", tcg_set, bulbasaur)
        _collect(session, card)

        data = client.get("/species/summary").json()

        assert data[0]["owned"] is True

    def test_multiple_cards_same_species_still_just_owned(self, client, session):
        """Owning multiple cards doesn't change the owned boolean."""
        bulbasaur = _species(session, 1, "bulbasaur")
        tcg_set = _set(session, "sv1")
        card1 = _card(session, "sv1-1", tcg_set, bulbasaur)
        card2 = _card(session, "sv1-2", tcg_set, bulbasaur)
        _collect(session, card1)
        _collect(session, card2)

        data = client.get("/species/summary").json()

        assert data[0]["owned"] is True

    def test_duplicate_collection_entries_still_just_owned(self, client, session):
        """Duplicate pulls of the same card don't change anything."""
        bulbasaur = _species(session, 1, "bulbasaur")
        tcg_set = _set(session, "sv1")
        card = _card(session, "sv1-1", tcg_set, bulbasaur)
        _collect(session, card)
        _collect(session, card)
        _collect(session, card)

        data = client.get("/species/summary").json()

        assert data[0]["owned"] is True

    def test_ordered_by_national_dex_number(self, client, session):
        _species(session, 25, "pikachu")
        _species(session, 1, "bulbasaur")
        _species(session, 4, "charmander")

        data = client.get("/species/summary").json()

        dex_numbers = [row["national_dex_number"] for row in data]
        assert dex_numbers == [1, 4, 25]

    def test_ownership_independent_per_species(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        pikachu = _species(session, 25, "pikachu")
        tcg_set = _set(session, "sv1")
        card_b = _card(session, "sv1-1", tcg_set, bulbasaur)
        _card(session, "sv1-25", tcg_set, pikachu)
        _collect(session, card_b)

        data = client.get("/species/summary").json()

        bulbasaur_row = next(r for r in data if r["name"] == "bulbasaur")
        pikachu_row = next(r for r in data if r["name"] == "pikachu")

        assert bulbasaur_row["owned"] is True
        assert pikachu_row["owned"] is False

    def test_response_matches_schema_fields(self, client, session):
        _species(session, 1, "bulbasaur")

        data = client.get("/species/summary").json()

        assert len(data) == 1
        assert set(data[0].keys()) == set(SpeciesSummaryRead.model_fields)
