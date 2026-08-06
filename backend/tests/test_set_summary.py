"""Tests for the GET /sets/summary endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.schemas.set_summary import SetSummaryRead


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


def _species(session, dex, name):
    s = PokemonSpecies(national_dex_number=dex, name=name, generation=1)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _set(session, api_set_id, name):
    s = Set(api_set_id=api_set_id, name=name, series="Test")
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _card(session, api_card_id, tcg_set, species):
    c = Card(api_card_id=api_card_id, set_id=tcg_set.id, pokemon_species_id=species.id)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _collect(session, card):
    session.add(Collection(card_id=card.id))
    session.commit()


class TestSetSummary:
    def test_empty_database(self, client):
        data = client.get("/sets/summary").json()
        assert data == []

    def test_set_with_pokemon_cards(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        pikachu = _species(session, 25, "pikachu")
        sv1 = _set(session, "sv1", "Scarlet & Violet")
        _card(session, "sv1-1", sv1, bulbasaur)
        _card(session, "sv1-25", sv1, pikachu)

        data = client.get("/sets/summary").json()

        assert len(data) == 1
        assert data[0]["total_species_in_set"] == 2
        assert data[0]["owned_species_in_set"] == 0
        assert data[0]["missing_species_in_set"] == 2

    def test_owned_species_counted(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        pikachu = _species(session, 25, "pikachu")
        sv1 = _set(session, "sv1", "Scarlet & Violet")
        card_b = _card(session, "sv1-1", sv1, bulbasaur)
        _card(session, "sv1-25", sv1, pikachu)
        _collect(session, card_b)

        data = client.get("/sets/summary").json()

        assert data[0]["owned_species_in_set"] == 1
        assert data[0]["missing_species_in_set"] == 1

    def test_trainer_only_set_excluded(self, client, session):
        _species(session, 1, "bulbasaur")
        trainer_set = _set(session, "t1", "Trainer Set")
        # Card with no species (trainer)
        c = Card(api_card_id="t1-1", set_id=trainer_set.id, pokemon_species_id=None)
        session.add(c)
        session.commit()

        data = client.get("/sets/summary").json()

        assert len(data) == 0

    def test_multiple_cards_same_species_counts_once(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        sv1 = _set(session, "sv1", "Set A")
        _card(session, "sv1-1a", sv1, bulbasaur)
        _card(session, "sv1-1b", sv1, bulbasaur)
        _card(session, "sv1-1c", sv1, bulbasaur)

        data = client.get("/sets/summary").json()

        assert data[0]["total_species_in_set"] == 1

    def test_response_matches_schema(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        sv1 = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", sv1, bulbasaur)

        data = client.get("/sets/summary").json()

        assert set(data[0].keys()) == set(SetSummaryRead.model_fields)

    def test_all_species_owned_in_set(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        sv1 = _set(session, "sv1", "Set A")
        card = _card(session, "sv1-1", sv1, bulbasaur)
        _collect(session, card)

        data = client.get("/sets/summary").json()

        assert data[0]["owned_species_in_set"] == 1
        assert data[0]["missing_species_in_set"] == 0
