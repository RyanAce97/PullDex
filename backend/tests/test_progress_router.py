"""Tests for the /progress API routes.

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
from app.schemas.progress import MissingSpeciesRead, ProgressRead


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    connection = engine.connect()
    SQLModel.metadata.create_all(connection)
    with Session(bind=connection) as session:
        yield session
    connection.close()


@pytest.fixture(name="client")
def client_fixture(session):
    """TestClient with the session dependency overridden."""
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_species(session: Session, dex: int, name: str) -> PokemonSpecies:
    species = PokemonSpecies(national_dex_number=dex, name=name, generation=1)
    session.add(species)
    session.commit()
    session.refresh(species)
    return species


def _seed_card(session: Session, api_card_id: str, species: PokemonSpecies) -> Card:
    tcg_set = Set(api_set_id=f"set-{api_card_id}", name="Test Set", series="Test")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)

    card = Card(api_card_id=api_card_id, set_id=tcg_set.id, pokemon_species_id=species.id)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def _add_to_collection(session: Session, card: Card) -> Collection:
    entry = Collection(card_id=card.id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# GET /progress
# ---------------------------------------------------------------------------

class TestProgress:
    def test_empty_database_returns_zero_progress(self, client):
        """No species in DB = all zeros."""
        response = client.get("/progress")

        assert response.status_code == 200
        data = response.json()
        assert data["total_species"] == 0
        assert data["owned_species"] == 0
        assert data["missing_species"] == 0
        assert data["completion_percentage"] == 0.0

    def test_no_collection_entries_means_all_missing(self, client, session):
        """Species exist but nothing in collection = all missing."""
        _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")
        _seed_species(session, 7, "squirtle")

        data = client.get("/progress").json()

        assert data["total_species"] == 3
        assert data["owned_species"] == 0
        assert data["missing_species"] == 3
        assert data["completion_percentage"] == 0.0

    def test_owning_one_card_makes_species_owned(self, client, session):
        """Adding one card to collection makes that species owned."""
        bulbasaur = _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")
        card = _seed_card(session, "sv1-1", bulbasaur)
        _add_to_collection(session, card)

        data = client.get("/progress").json()

        assert data["total_species"] == 2
        assert data["owned_species"] == 1
        assert data["missing_species"] == 1
        assert data["completion_percentage"] == 50.0

    def test_multiple_cards_same_species_counts_once(self, client, session):
        """Two different cards for the same species = still 1 owned species."""
        bulbasaur = _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")

        card1 = _seed_card(session, "sv1-1", bulbasaur)
        card2 = _seed_card(session, "base1-1", bulbasaur)
        _add_to_collection(session, card1)
        _add_to_collection(session, card2)

        data = client.get("/progress").json()

        assert data["owned_species"] == 1
        assert data["missing_species"] == 1

    def test_duplicate_copies_do_not_change_percentage(self, client, session):
        """Owning 3 copies of the same card = same completion as 1 copy."""
        bulbasaur = _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")
        card = _seed_card(session, "sv1-1", bulbasaur)

        _add_to_collection(session, card)
        _add_to_collection(session, card)
        _add_to_collection(session, card)

        data = client.get("/progress").json()

        assert data["owned_species"] == 1
        assert data["completion_percentage"] == 50.0

    def test_full_completion(self, client, session):
        """Owning a card for every species = 100%."""
        bulbasaur = _seed_species(session, 1, "bulbasaur")
        charmander = _seed_species(session, 4, "charmander")

        card1 = _seed_card(session, "sv1-1", bulbasaur)
        card2 = _seed_card(session, "sv1-4", charmander)
        _add_to_collection(session, card1)
        _add_to_collection(session, card2)

        data = client.get("/progress").json()

        assert data["owned_species"] == 2
        assert data["missing_species"] == 0
        assert data["completion_percentage"] == 100.0

    def test_percentage_calculation_precision(self, client, session):
        """1 owned out of 3 total = 33.3%."""
        bulbasaur = _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")
        _seed_species(session, 7, "squirtle")

        card = _seed_card(session, "sv1-1", bulbasaur)
        _add_to_collection(session, card)

        data = client.get("/progress").json()

        assert data["completion_percentage"] == 33.3

    def test_response_matches_schema_fields(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        data = client.get("/progress").json()

        expected_fields = set(ProgressRead.model_fields)
        assert set(data.keys()) == expected_fields


# ---------------------------------------------------------------------------
# GET /progress/missing
# ---------------------------------------------------------------------------

class TestMissingSpecies:
    def test_all_species_missing_when_collection_empty(self, client, session):
        _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")
        _seed_species(session, 7, "squirtle")

        response = client.get("/progress/missing")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_missing_list_excludes_owned_species(self, client, session):
        bulbasaur = _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")
        _seed_species(session, 7, "squirtle")

        card = _seed_card(session, "sv1-1", bulbasaur)
        _add_to_collection(session, card)

        data = client.get("/progress/missing").json()

        names = [s["name"] for s in data]
        assert "bulbasaur" not in names
        assert "charmander" in names
        assert "squirtle" in names
        assert len(data) == 2

    def test_missing_list_empty_when_all_owned(self, client, session):
        bulbasaur = _seed_species(session, 1, "bulbasaur")
        charmander = _seed_species(session, 4, "charmander")

        card1 = _seed_card(session, "sv1-1", bulbasaur)
        card2 = _seed_card(session, "sv1-4", charmander)
        _add_to_collection(session, card1)
        _add_to_collection(session, card2)

        data = client.get("/progress/missing").json()

        assert data == []

    def test_duplicate_cards_do_not_affect_missing_list(self, client, session):
        """Owning multiple copies of one card still removes its species from missing."""
        bulbasaur = _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")

        card = _seed_card(session, "sv1-1", bulbasaur)
        _add_to_collection(session, card)
        _add_to_collection(session, card)
        _add_to_collection(session, card)

        data = client.get("/progress/missing").json()

        names = [s["name"] for s in data]
        assert "bulbasaur" not in names
        assert len(data) == 1

    def test_missing_list_ordered_by_dex_number(self, client, session):
        _seed_species(session, 7, "squirtle")
        _seed_species(session, 1, "bulbasaur")
        _seed_species(session, 4, "charmander")

        data = client.get("/progress/missing").json()

        dex_numbers = [s["national_dex_number"] for s in data]
        assert dex_numbers == [1, 4, 7]

    def test_limit_is_respected(self, client, session):
        for i in range(10):
            _seed_species(session, i + 1, f"species-{i}")

        response = client.get("/progress/missing", params={"limit": 3})

        assert len(response.json()) == 3

    def test_offset_is_respected(self, client, session):
        for i in range(10):
            _seed_species(session, i + 1, f"species-{i}")

        all_missing = client.get("/progress/missing").json()
        offset_missing = client.get("/progress/missing", params={"offset": 7}).json()

        assert len(offset_missing) == len(all_missing) - 7

    def test_response_matches_schema_fields(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        data = client.get("/progress/missing").json()

        assert len(data) == 1
        assert set(data[0].keys()) == set(MissingSpeciesRead.model_fields)

    def test_response_does_not_expose_orm_relationships(self, client, session):
        _seed_species(session, 1, "bulbasaur")

        data = client.get("/progress/missing").json()

        assert "cards" not in data[0]
