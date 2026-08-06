"""Tests for the /sets API routes.

Uses FastAPI's TestClient with the database session dependency overridden
to an in-memory SQLite database — no disk writes, no running server needed.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.set import Set
from app.schemas.set import SetRead


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

def _seed_set(
    session: Session,
    api_set_id: str = "sv1",
    name: str = "Scarlet & Violet",
    series: str = "Scarlet & Violet",
    release_date: date | None = date(2023, 3, 31),
) -> Set:
    tcg_set = Set(
        api_set_id=api_set_id,
        name=name,
        series=series,
        release_date=release_date,
    )
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)
    return tcg_set


# ---------------------------------------------------------------------------
# GET /sets (list / search)
# ---------------------------------------------------------------------------

class TestListSets:
    def test_returns_all_sets(self, client, session):
        _seed_set(session, api_set_id="sv1", name="Scarlet & Violet")
        _seed_set(session, api_set_id="base1", name="Base Set", series="Base")

        response = client.get("/sets")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_returns_empty_list_when_no_sets(self, client):
        response = client.get("/sets")

        assert response.status_code == 200
        assert response.json() == []

    def test_search_by_name(self, client, session):
        _seed_set(session, api_set_id="sv1", name="Scarlet & Violet")
        _seed_set(session, api_set_id="base1", name="Base Set", series="Base")

        response = client.get("/sets", params={"name": "Scarlet"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Scarlet & Violet"

    def test_search_is_case_insensitive(self, client, session):
        _seed_set(session, api_set_id="sv1", name="Scarlet & Violet")

        assert len(client.get("/sets", params={"name": "scarlet"}).json()) == 1
        assert len(client.get("/sets", params={"name": "SCARLET"}).json()) == 1

    def test_search_partial_match(self, client, session):
        _seed_set(session, api_set_id="sv1", name="Scarlet & Violet")

        response = client.get("/sets", params={"name": "let"})

        assert len(response.json()) == 1

    def test_search_returns_empty_for_no_match(self, client, session):
        _seed_set(session, api_set_id="sv1", name="Scarlet & Violet")

        response = client.get("/sets", params={"name": "Fossil"})

        assert response.status_code == 200
        assert response.json() == []

    def test_limit_is_respected(self, client, session):
        for i in range(5):
            _seed_set(session, api_set_id=f"sv{i}", name=f"Set {i}")

        response = client.get("/sets", params={"limit": 2})

        assert len(response.json()) == 2

    def test_offset_is_respected(self, client, session):
        for i in range(5):
            _seed_set(session, api_set_id=f"sv{i}", name=f"Set {i}")

        all_sets = client.get("/sets").json()
        offset_sets = client.get("/sets", params={"offset": 3}).json()

        assert len(offset_sets) == len(all_sets) - 3

    def test_limit_above_250_is_rejected(self, client):
        response = client.get("/sets", params={"limit": 251})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /sets/{set_id}
# ---------------------------------------------------------------------------

class TestGetSetById:
    def test_returns_200_and_set(self, client, session):
        tcg_set = _seed_set(session)

        response = client.get(f"/sets/{tcg_set.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tcg_set.id
        assert data["api_set_id"] == "sv1"
        assert data["name"] == "Scarlet & Violet"
        assert data["series"] == "Scarlet & Violet"
        assert data["release_date"] == "2023-03-31"

    def test_returns_404_when_not_found(self, client):
        response = client.get("/sets/99999")

        assert response.status_code == 404
        assert "99999" in response.json()["detail"]

    def test_response_contains_expected_fields(self, client, session):
        tcg_set = _seed_set(session)

        data = client.get(f"/sets/{tcg_set.id}").json()

        expected_fields = set(SetRead.model_fields)
        assert expected_fields == set(data.keys())

    def test_response_does_not_expose_orm_relationships(self, client, session):
        tcg_set = _seed_set(session)

        data = client.get(f"/sets/{tcg_set.id}").json()

        assert "cards" not in data


# ---------------------------------------------------------------------------
# GET /sets/api/{api_set_id}
# ---------------------------------------------------------------------------

class TestGetSetByApiId:
    def test_returns_200_and_set(self, client, session):
        _seed_set(session, api_set_id="base1", name="Base Set", series="Base")

        response = client.get("/sets/api/base1")

        assert response.status_code == 200
        data = response.json()
        assert data["api_set_id"] == "base1"
        assert data["name"] == "Base Set"

    def test_returns_404_when_not_found(self, client):
        response = client.get("/sets/api/unknown-set")

        assert response.status_code == 404
        assert "unknown-set" in response.json()["detail"]


# ---------------------------------------------------------------------------
# SetRead schema
# ---------------------------------------------------------------------------

class TestSetReadSchema:
    """Unit tests for the SetRead schema itself — no HTTP involved."""

    def test_schema_fields_match_expected_set(self):
        expected = {"id", "api_set_id", "name", "series", "release_date"}
        assert set(SetRead.model_fields) == expected

    def test_schema_does_not_include_relationship_fields(self):
        assert "cards" not in SetRead.model_fields

    def test_schema_populates_from_set_orm_object(self, session):
        tcg_set = _seed_set(session)

        schema = SetRead.model_validate(tcg_set)

        assert schema.id == tcg_set.id
        assert schema.api_set_id == "sv1"
        assert schema.name == "Scarlet & Violet"
        assert schema.series == "Scarlet & Violet"
        assert schema.release_date == date(2023, 3, 31)

    def test_schema_accepts_none_release_date(self):
        schema = SetRead(id=1, api_set_id="sv1", name="Test", series="Test", release_date=None)
        assert schema.release_date is None

    def test_list_endpoint_returns_set_read_shaped_objects(self, client, session):
        _seed_set(session)

        data = client.get("/sets").json()

        assert len(data) == 1
        assert set(data[0].keys()) == set(SetRead.model_fields)
