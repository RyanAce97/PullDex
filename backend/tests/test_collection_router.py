"""Tests for the /collection API routes.

Tests both species-level and card-level collection management.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.schemas.collection import CollectionRead


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


def _card(session: Session, api_card_id: str, species: PokemonSpecies) -> Card:
    tcg_set = Set(api_set_id=f"set-{api_card_id}", name="Test", series="Test")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)
    card = Card(api_card_id=api_card_id, set_id=tcg_set.id, pokemon_species_id=species.id)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


# ---------------------------------------------------------------------------
# GET /collection
# ---------------------------------------------------------------------------

class TestListCollection:
    def test_returns_empty_list(self, client):
        assert client.get("/collection").json() == []

    def test_returns_species_entries(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        client.post("/collection/species", json={"pokemon_species_id": bulbasaur.id})

        data = client.get("/collection").json()
        assert len(data) == 1
        assert data[0]["pokemon_species_id"] == bulbasaur.id
        assert data[0]["card_id"] is None

    def test_returns_card_entries(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        card = _card(session, "sv1-1", bulbasaur)
        client.post("/collection/cards", json={"card_id": card.id})

        data = client.get("/collection").json()
        assert len(data) == 1
        assert data[0]["card_id"] == card.id


# ---------------------------------------------------------------------------
# POST /collection/species — species-level ownership
# ---------------------------------------------------------------------------

class TestAddSpecies:
    def test_adds_species_returns_201(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        response = client.post("/collection/species", json={"pokemon_species_id": bulbasaur.id})

        assert response.status_code == 201
        data = response.json()
        assert data["pokemon_species_id"] == bulbasaur.id
        assert data["card_id"] is None
        assert data["quantity"] == 1

    def test_idempotent_returns_existing(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        r1 = client.post("/collection/species", json={"pokemon_species_id": bulbasaur.id})
        r2 = client.post("/collection/species", json={"pokemon_species_id": bulbasaur.id})

        assert r1.json()["id"] == r2.json()["id"]

    def test_404_for_nonexistent_species(self, client):
        response = client.post("/collection/species", json={"pokemon_species_id": 99999})
        assert response.status_code == 404

    def test_species_appears_in_progress_as_owned(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        _species(session, 4, "charmander")

        client.post("/collection/species", json={"pokemon_species_id": bulbasaur.id})

        progress = client.get("/progress").json()
        assert progress["owned_species"] == 1
        assert progress["missing_species"] == 1


# ---------------------------------------------------------------------------
# DELETE /collection/species/{species_id}
# ---------------------------------------------------------------------------

class TestRemoveSpecies:
    def test_removes_species_entry(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        client.post("/collection/species", json={"pokemon_species_id": bulbasaur.id})

        response = client.delete(f"/collection/species/{bulbasaur.id}")
        assert response.status_code == 204

        data = client.get("/collection").json()
        assert len(data) == 0

    def test_404_if_no_entry(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        response = client.delete(f"/collection/species/{bulbasaur.id}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /collection/cards — card-level ownership
# ---------------------------------------------------------------------------

class TestAddCard:
    def test_adds_card_returns_201(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        card = _card(session, "sv1-1", bulbasaur)

        response = client.post("/collection/cards", json={"card_id": card.id})

        assert response.status_code == 201
        data = response.json()
        assert data["card_id"] == card.id
        assert data["quantity"] == 1

    def test_adding_same_card_increments_quantity(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        card = _card(session, "sv1-1", bulbasaur)

        client.post("/collection/cards", json={"card_id": card.id, "quantity": 1})
        response = client.post("/collection/cards", json={"card_id": card.id, "quantity": 2})

        assert response.json()["quantity"] == 3

    def test_404_for_nonexistent_card(self, client):
        response = client.post("/collection/cards", json={"card_id": 99999})
        assert response.status_code == 404

    def test_custom_quantity(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        card = _card(session, "sv1-1", bulbasaur)

        response = client.post("/collection/cards", json={"card_id": card.id, "quantity": 3})
        assert response.json()["quantity"] == 3


# ---------------------------------------------------------------------------
# PATCH /collection/cards/{entry_id} — update quantity
# ---------------------------------------------------------------------------

class TestUpdateCardQuantity:
    def test_updates_quantity(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        card = _card(session, "sv1-1", bulbasaur)
        create_resp = client.post("/collection/cards", json={"card_id": card.id})
        entry_id = create_resp.json()["id"]

        response = client.patch(f"/collection/cards/{entry_id}", json={"quantity": 5})
        assert response.status_code == 200
        assert response.json()["quantity"] == 5

    def test_setting_zero_removes_entry(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        card = _card(session, "sv1-1", bulbasaur)
        create_resp = client.post("/collection/cards", json={"card_id": card.id})
        entry_id = create_resp.json()["id"]

        client.patch(f"/collection/cards/{entry_id}", json={"quantity": 0})

        data = client.get("/collection").json()
        assert len(data) == 0


# ---------------------------------------------------------------------------
# GET /collection/species/{species_id}/cards
# ---------------------------------------------------------------------------

class TestGetSpeciesCards:
    def test_returns_card_entries_for_species(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        card1 = _card(session, "sv1-1", bulbasaur)
        card2 = _card(session, "sv1-2", bulbasaur)
        client.post("/collection/cards", json={"card_id": card1.id})
        client.post("/collection/cards", json={"card_id": card2.id, "quantity": 2})

        response = client.get(f"/collection/species/{bulbasaur.id}/cards")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_returns_empty_if_no_cards_tracked(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        response = client.get(f"/collection/species/{bulbasaur.id}/cards")
        assert response.json() == []


# ---------------------------------------------------------------------------
# Integration: species + card ownership both count
# ---------------------------------------------------------------------------

class TestOwnershipIntegration:
    def test_species_only_counts_as_owned(self, client, session):
        """Adding just a species (no card) makes it owned in progress."""
        pikachu = _species(session, 25, "pikachu")
        client.post("/collection/species", json={"pokemon_species_id": pikachu.id})

        missing = client.get("/progress/missing").json()
        names = [s["name"] for s in missing]
        assert "pikachu" not in names

    def test_card_only_counts_as_owned(self, client, session):
        """Adding just a card (no species entry) makes the species owned."""
        pikachu = _species(session, 25, "pikachu")
        card = _card(session, "sv1-25", pikachu)
        client.post("/collection/cards", json={"card_id": card.id})

        missing = client.get("/progress/missing").json()
        names = [s["name"] for s in missing]
        assert "pikachu" not in names

    def test_both_species_and_card_still_one_owned(self, client, session):
        """Having both entry types doesn't double-count."""
        pikachu = _species(session, 25, "pikachu")
        _species(session, 1, "bulbasaur")
        card = _card(session, "sv1-25", pikachu)

        client.post("/collection/species", json={"pokemon_species_id": pikachu.id})
        client.post("/collection/cards", json={"card_id": card.id})

        progress = client.get("/progress").json()
        assert progress["owned_species"] == 1
        assert progress["total_species"] == 2


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestCollectionReadSchema:
    def test_schema_fields(self):
        expected = {"id", "pokemon_species_id", "card_id", "quantity"}
        assert set(CollectionRead.model_fields) == expected

    def test_schema_does_not_expose_relationships(self):
        assert "card" not in CollectionRead.model_fields
        assert "pokemon_species" not in CollectionRead.model_fields
