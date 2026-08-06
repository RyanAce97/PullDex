"""Tests for the /cards API routes.

Uses FastAPI's TestClient with the database session dependency overridden
to an in-memory SQLite database — no disk writes, no running server needed.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.schemas.card import CardRead


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    """In-memory SQLite session with the full schema.

    Uses a single connection held open for the duration of the fixture so
    that the tables created by ``SQLModel.metadata.create_all`` remain
    visible to every query made within the same test.  Plain
    ``sqlite://`` (no filename) creates a per-connection database; without
    pinning to one connection the tables would disappear between calls.
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
    lifespan hooks never fire.  This prevents ``create_db_and_tables()``
    from touching the real on-disk SQLite database.  The in-memory schema
    is already created by ``session_fixture``.
    """
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

@pytest.fixture(name="sv1_set")
def sv1_set_fixture(session):
    tcg_set = Set(api_set_id="sv1", name="Scarlet & Violet", series="Scarlet & Violet")
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


def _seed_card(
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
# GET /cards/{card_id}
# ---------------------------------------------------------------------------

class TestGetCardById:
    def test_returns_200_and_card(self, client, session, sv1_set, bulbasaur):
        card = _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)

        response = client.get(f"/cards/{card.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == card.id
        assert data["api_card_id"] == "sv1-1"
        assert data["rarity"] == "Common"

    def test_returns_404_when_not_found(self, client):
        response = client.get("/cards/99999")
        assert response.status_code == 404
        assert "99999" in response.json()["detail"]

    def test_response_contains_expected_fields(self, client, session, sv1_set, bulbasaur):
        card = _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)

        data = client.get(f"/cards/{card.id}").json()

        # Verify every field declared in CardRead is present.
        expected_fields = set(CardRead.model_fields)
        assert expected_fields == set(data.keys())

    def test_response_does_not_expose_orm_relationships(self, client, session, sv1_set, bulbasaur):
        """SQLModel relationship attributes must not leak into the response."""
        card = _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)

        data = client.get(f"/cards/{card.id}").json()

        assert "pokemon_species" not in data
        assert "set" not in data
        assert "collection_entries" not in data


# ---------------------------------------------------------------------------
# GET /cards?name=...
# ---------------------------------------------------------------------------

class TestSearchCards:
    def test_returns_matches(self, client, session, sv1_set, bulbasaur):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)

        response = client.get("/cards", params={"name": "bulbasaur"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["api_card_id"] == "sv1-1"

    def test_search_is_case_insensitive(self, client, session, sv1_set, bulbasaur):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)

        assert client.get("/cards", params={"name": "BULBASAUR"}).status_code == 200
        assert len(client.get("/cards", params={"name": "BULBASAUR"}).json()) == 1

    def test_returns_empty_list_when_no_match(self, client, session, sv1_set, bulbasaur):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)

        response = client.get("/cards", params={"name": "charizard"})

        assert response.status_code == 200
        assert response.json() == []

    def test_requires_name_parameter(self, client):
        response = client.get("/cards")
        assert response.status_code == 422

    def test_name_must_not_be_empty(self, client):
        response = client.get("/cards", params={"name": ""})
        assert response.status_code == 422

    def test_limit_param_is_respected(self, client, session, sv1_set, bulbasaur, pikachu):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _seed_card(session, "sv1-25", set_id=sv1_set.id, species_id=pikachu.id)

        response = client.get("/cards", params={"name": "a", "limit": 1})

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_offset_param_is_respected(self, client, session, sv1_set, bulbasaur, pikachu):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _seed_card(session, "sv1-25", set_id=sv1_set.id, species_id=pikachu.id)

        all_results = client.get("/cards", params={"name": "a"}).json()
        offset_results = client.get("/cards", params={"name": "a", "offset": 1}).json()

        assert len(offset_results) == len(all_results) - 1

    def test_limit_above_250_is_rejected(self, client):
        response = client.get("/cards", params={"name": "a", "limit": 251})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /cards/by-dex/{national_dex_number}
# ---------------------------------------------------------------------------

class TestGetCardsByDex:
    def test_returns_cards_for_dex_number(self, client, session, sv1_set, bulbasaur):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _seed_card(session, "sv1-2", set_id=sv1_set.id, species_id=bulbasaur.id)

        response = client.get("/cards/by-dex/1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(c["pokemon_species_id"] == bulbasaur.id for c in data)

    def test_returns_empty_list_for_unknown_dex_number(self, client):
        response = client.get("/cards/by-dex/999")

        assert response.status_code == 200
        assert response.json() == []

    def test_does_not_return_other_species_cards(self, client, session, sv1_set, bulbasaur, pikachu):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)
        _seed_card(session, "sv1-25", set_id=sv1_set.id, species_id=pikachu.id)

        response = client.get("/cards/by-dex/1")

        assert len(response.json()) == 1
        assert response.json()[0]["api_card_id"] == "sv1-1"

    def test_limit_param_is_respected(self, client, session, sv1_set, bulbasaur):
        for i in range(5):
            _seed_card(session, f"sv1-bulb-{i}", set_id=sv1_set.id, species_id=bulbasaur.id)

        response = client.get("/cards/by-dex/1", params={"limit": 2})

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_offset_param_is_respected(self, client, session, sv1_set, bulbasaur):
        for i in range(4):
            _seed_card(session, f"sv1-bulb-{i}", set_id=sv1_set.id, species_id=bulbasaur.id)

        all_results = client.get("/cards/by-dex/1").json()
        offset_results = client.get("/cards/by-dex/1", params={"offset": 2}).json()

        assert len(offset_results) == len(all_results) - 2


# ---------------------------------------------------------------------------
# CardRead schema
# ---------------------------------------------------------------------------

class TestCardReadSchema:
    """Unit tests for the CardRead schema itself — no HTTP involved."""

    def test_schema_fields_match_expected_set(self):
        expected = {
            "id",
            "api_card_id",
            "set_id",
            "pokemon_species_id",
            "card_number",
            "rarity",
            "variant",
            "image_url",
        }
        assert set(CardRead.model_fields) == expected

    def test_schema_does_not_include_relationship_fields(self):
        field_names = set(CardRead.model_fields)
        assert "pokemon_species" not in field_names
        assert "set" not in field_names
        assert "collection_entries" not in field_names

    def test_schema_populates_from_card_orm_object(self, session, sv1_set, bulbasaur):
        card = _seed_card(
            session,
            "sv1-1",
            set_id=sv1_set.id,
            species_id=bulbasaur.id,
            card_number="001/198",
            rarity="Rare Holo",
        )

        schema = CardRead.model_validate(card)

        assert schema.id == card.id
        assert schema.api_card_id == "sv1-1"
        assert schema.set_id == sv1_set.id
        assert schema.pokemon_species_id == bulbasaur.id
        assert schema.card_number == "001/198"
        assert schema.rarity == "Rare Holo"
        assert schema.variant is None
        assert schema.image_url is None

    def test_schema_accepts_all_none_optional_fields(self):
        schema = CardRead(id=1, api_card_id=None, set_id=None, pokemon_species_id=None,
                          card_number=None, rarity=None, variant=None, image_url=None)
        assert schema.id == 1
        assert schema.rarity is None

    def test_list_endpoint_returns_carread_shaped_objects(self, client, session, sv1_set, bulbasaur):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)

        data = client.get("/cards", params={"name": "bulbasaur"}).json()

        assert len(data) == 1
        assert set(data[0].keys()) == set(CardRead.model_fields)

    def test_by_dex_endpoint_returns_carread_shaped_objects(self, client, session, sv1_set, bulbasaur):
        _seed_card(session, "sv1-1", set_id=sv1_set.id, species_id=bulbasaur.id)

        data = client.get("/cards/by-dex/1").json()

        assert len(data) == 1
        assert set(data[0].keys()) == set(CardRead.model_fields)
