"""Tests for the /species API routes.

Uses FastAPI's TestClient with the database session dependency overridden
to an in-memory SQLite database — no disk writes, no running server needed.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.pokemon_species import PokemonSpecies
from app.schemas.pokemon_species import PokemonSpeciesRead


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

def _seed_species(
    session: Session,
    national_dex_number: int = 1,
    name: str = "bulbasaur",
    generation: int | None = 1,
) -> PokemonSpecies:
    species = PokemonSpecies(
        national_dex_number=national_dex_number,
        name=name,
        generation=generation,
    )
    session.add(species)
    session.commit()
    session.refresh(species)
    return species


# ---------------------------------------------------------------------------
# GET /species (list / search)
# ---------------------------------------------------------------------------

class TestListSpecies:
    def test_returns_all_species(self, client, session):
        _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 25, "pikachu")

        response = client.get("/species")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_returns_empty_list_when_no_species(self, client):
        response = client.get("/species")

        assert response.status_code == 200
        assert response.json() == []

    def test_search_by_name(self, client, session):
        _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 25, "pikachu")

        response = client.get("/species", params={"name": "pika"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "pikachu"

    def test_search_is_case_insensitive(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        assert len(client.get("/species", params={"name": "BULBA"}).json()) == 1
        assert len(client.get("/species", params={"name": "Bulba"}).json()) == 1

    def test_search_partial_match(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        response = client.get("/species", params={"name": "saur"})

        assert len(response.json()) == 1

    def test_search_returns_empty_for_no_match(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        response = client.get("/species", params={"name": "charizard"})

        assert response.status_code == 200
        assert response.json() == []

    def test_limit_is_respected(self, client, session):
        for i in range(5):
            _seed_species(session, i + 1, f"species-{i}")

        response = client.get("/species", params={"limit": 2})

        assert len(response.json()) == 2

    def test_offset_is_respected(self, client, session):
        for i in range(5):
            _seed_species(session, i + 1, f"species-{i}")

        all_species = client.get("/species").json()
        offset_species = client.get("/species", params={"offset": 3}).json()

        assert len(offset_species) == len(all_species) - 3

    def test_limit_above_1025_is_rejected(self, client):
        response = client.get("/species", params={"limit": 1026})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /species/{national_dex_number}
# ---------------------------------------------------------------------------

class TestGetSpecies:
    def test_returns_200_and_species(self, client, session):
        _seed_species(session, 25, "pikachu", generation=1)

        response = client.get("/species/25")

        assert response.status_code == 200
        data = response.json()
        assert data["national_dex_number"] == 25
        assert data["name"] == "pikachu"
        assert data["generation"] == 1

    def test_returns_404_when_not_found(self, client):
        response = client.get("/species/9999")

        assert response.status_code == 404
        assert "9999" in response.json()["detail"]

    def test_response_contains_expected_fields(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        data = client.get("/species/1").json()

        expected_fields = set(PokemonSpeciesRead.model_fields)
        assert expected_fields == set(data.keys())

    def test_response_does_not_expose_orm_relationships(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        data = client.get("/species/1").json()

        assert "cards" not in data

    def test_handles_none_generation(self, client, session):
        _seed_species(session, 1000, "unknown-species", generation=None)

        data = client.get("/species/1000").json()

        assert data["generation"] is None


# ---------------------------------------------------------------------------
# PokemonSpeciesRead schema
# ---------------------------------------------------------------------------

class TestPokemonSpeciesReadSchema:
    """Unit tests for the PokemonSpeciesRead schema itself."""

    def test_schema_fields_match_expected_set(self):
        expected = {"id", "national_dex_number", "name", "generation"}
        assert set(PokemonSpeciesRead.model_fields) == expected

    def test_schema_does_not_include_relationship_fields(self):
        assert "cards" not in PokemonSpeciesRead.model_fields

    def test_schema_populates_from_orm_object(self, session):
        species = _seed_species(session, 25, "pikachu", generation=1)

        schema = PokemonSpeciesRead.model_validate(species)

        assert schema.id == species.id
        assert schema.national_dex_number == 25
        assert schema.name == "pikachu"
        assert schema.generation == 1

    def test_schema_accepts_none_generation(self):
        schema = PokemonSpeciesRead(id=1, national_dex_number=1, name="test", generation=None)
        assert schema.generation is None

    def test_list_endpoint_returns_schema_shaped_objects(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        data = client.get("/species").json()

        assert len(data) == 1
        assert set(data[0].keys()) == set(PokemonSpeciesRead.model_fields)
