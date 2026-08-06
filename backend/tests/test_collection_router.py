"""Tests for the /collection API routes.

Uses FastAPI's TestClient with the database session dependency overridden
to an in-memory SQLite database — no disk writes, no running server needed.
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
    """In-memory SQLite session with the full schema.

    Uses a single connection held open for the duration of the fixture so
    that the tables created by ``SQLModel.metadata.create_all`` remain
    visible to every query made within the same test.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    connection = engine.connect()
    SQLModel.metadata.create_all(connection)
    with Session(bind=connection) as session:
        yield session
    connection.close()


@pytest.fixture(name="client")
def client_fixture(session):
    """TestClient with the session dependency overridden.

    Instantiated directly (not as a context manager) so that Starlette's
    lifespan hooks never fire.
    """
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_card(session: Session, api_card_id: str = "sv1-1") -> Card:
    """Create and persist a card to use in collection tests."""
    tcg_set = Set(api_set_id=f"set-{api_card_id}", name="Test Set", series="Test")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)

    card = Card(api_card_id=api_card_id, set_id=tcg_set.id, rarity="Common")
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def _seed_collection_entry(session: Session, card: Card) -> Collection:
    """Add a card to the collection and return the entry."""
    entry = Collection(card_id=card.id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# GET /collection
# ---------------------------------------------------------------------------

class TestListCollection:
    def test_returns_empty_list_when_empty(self, client):
        response = client.get("/collection")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_collection_entries(self, client, session):
        card = _seed_card(session)
        _seed_collection_entry(session, card)

        response = client.get("/collection")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["card_id"] == card.id

    def test_returns_multiple_entries(self, client, session):
        card1 = _seed_card(session, "sv1-1")
        card2 = _seed_card(session, "sv1-2")
        _seed_collection_entry(session, card1)
        _seed_collection_entry(session, card2)

        response = client.get("/collection")

        assert len(response.json()) == 2

    def test_limit_is_respected(self, client, session):
        for i in range(5):
            card = _seed_card(session, f"sv1-{i}")
            _seed_collection_entry(session, card)

        response = client.get("/collection", params={"limit": 2})

        assert len(response.json()) == 2

    def test_offset_is_respected(self, client, session):
        for i in range(5):
            card = _seed_card(session, f"sv1-{i}")
            _seed_collection_entry(session, card)

        all_entries = client.get("/collection").json()
        offset_entries = client.get("/collection", params={"offset": 3}).json()

        assert len(offset_entries) == len(all_entries) - 3

    def test_limit_above_250_is_rejected(self, client):
        response = client.get("/collection", params={"limit": 251})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /collection/{entry_id}
# ---------------------------------------------------------------------------

class TestGetCollectionEntry:
    def test_returns_200_and_entry(self, client, session):
        card = _seed_card(session)
        entry = _seed_collection_entry(session, card)

        response = client.get(f"/collection/{entry.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == entry.id
        assert data["card_id"] == card.id

    def test_returns_404_when_not_found(self, client):
        response = client.get("/collection/99999")

        assert response.status_code == 404
        assert "99999" in response.json()["detail"]

    def test_response_contains_expected_fields(self, client, session):
        card = _seed_card(session)
        entry = _seed_collection_entry(session, card)

        data = client.get(f"/collection/{entry.id}").json()

        expected_fields = set(CollectionRead.model_fields)
        assert expected_fields == set(data.keys())

    def test_response_does_not_expose_orm_relationships(self, client, session):
        card = _seed_card(session)
        entry = _seed_collection_entry(session, card)

        data = client.get(f"/collection/{entry.id}").json()

        assert "card" not in data


# ---------------------------------------------------------------------------
# POST /collection
# ---------------------------------------------------------------------------

class TestAddToCollection:
    def test_adds_card_and_returns_201(self, client, session):
        card = _seed_card(session)

        response = client.post("/collection", json={"card_id": card.id})

        assert response.status_code == 201
        data = response.json()
        assert data["card_id"] == card.id
        assert "id" in data

    def test_entry_persists_in_database(self, client, session):
        card = _seed_card(session)

        client.post("/collection", json={"card_id": card.id})

        # Verify via GET
        response = client.get("/collection")
        assert len(response.json()) == 1

    def test_returns_404_for_nonexistent_card(self, client):
        response = client.post("/collection", json={"card_id": 99999})

        assert response.status_code == 404
        assert "99999" in response.json()["detail"]

    def test_requires_card_id(self, client):
        response = client.post("/collection", json={})

        assert response.status_code == 422

    def test_response_matches_schema(self, client, session):
        card = _seed_card(session)

        data = client.post("/collection", json={"card_id": card.id}).json()

        assert set(data.keys()) == set(CollectionRead.model_fields)

    def test_can_add_same_card_multiple_times(self, client, session):
        """Multiple collection entries for the same card are valid (multiple pulls)."""
        card = _seed_card(session)

        client.post("/collection", json={"card_id": card.id})
        client.post("/collection", json={"card_id": card.id})

        response = client.get("/collection")
        assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# DELETE /collection/{entry_id}
# ---------------------------------------------------------------------------

class TestDeleteFromCollection:
    def test_deletes_entry_and_returns_204(self, client, session):
        card = _seed_card(session)
        entry = _seed_collection_entry(session, card)

        response = client.delete(f"/collection/{entry.id}")

        assert response.status_code == 204

    def test_entry_is_removed_from_database(self, client, session):
        card = _seed_card(session)
        entry = _seed_collection_entry(session, card)

        client.delete(f"/collection/{entry.id}")

        response = client.get("/collection")
        assert response.json() == []

    def test_returns_404_for_nonexistent_entry(self, client):
        response = client.delete("/collection/99999")

        assert response.status_code == 404
        assert "99999" in response.json()["detail"]

    def test_deleting_does_not_affect_other_entries(self, client, session):
        card1 = _seed_card(session, "sv1-1")
        card2 = _seed_card(session, "sv1-2")
        entry1 = _seed_collection_entry(session, card1)
        _seed_collection_entry(session, card2)

        client.delete(f"/collection/{entry1.id}")

        remaining = client.get("/collection").json()
        assert len(remaining) == 1
        assert remaining[0]["card_id"] == card2.id


# ---------------------------------------------------------------------------
# CollectionRead schema
# ---------------------------------------------------------------------------

class TestCollectionReadSchema:
    """Unit tests for the CollectionRead schema itself."""

    def test_schema_fields_match_expected_set(self):
        expected = {"id", "card_id"}
        assert set(CollectionRead.model_fields) == expected

    def test_schema_does_not_include_relationship_fields(self):
        assert "card" not in CollectionRead.model_fields

    def test_schema_populates_from_orm_object(self, session):
        card = _seed_card(session)
        entry = _seed_collection_entry(session, card)

        schema = CollectionRead.model_validate(entry)

        assert schema.id == entry.id
        assert schema.card_id == card.id

    def test_list_endpoint_returns_schema_shaped_objects(self, client, session):
        card = _seed_card(session)
        _seed_collection_entry(session, card)

        data = client.get("/collection").json()

        assert len(data) == 1
        assert set(data[0].keys()) == set(CollectionRead.model_fields)
