"""Tests for the /recommendations API routes.

Uses FastAPI's TestClient with the database session dependency overridden
to an in-memory SQLite database — no disk writes, no running server needed.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.schemas.recommendation import RecommendationResponse, SetRecommendation


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

def _species(session: Session, dex: int, name: str) -> PokemonSpecies:
    s = PokemonSpecies(national_dex_number=dex, name=name, generation=1)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _set(
    session: Session,
    api_set_id: str,
    name: str,
    release_date: date | None = None,
) -> Set:
    s = Set(api_set_id=api_set_id, name=name, series="Test", release_date=release_date)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _card(
    session: Session,
    api_card_id: str,
    tcg_set: Set,
    species: PokemonSpecies | None = None,
) -> Card:
    c = Card(
        api_card_id=api_card_id,
        set_id=tcg_set.id,
        pokemon_species_id=species.id if species else None,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _collect(session: Session, card: Card) -> Collection:
    from sqlmodel import select as _select
    from app.models.profile import Profile
    profile = session.exec(_select(Profile).where(Profile.is_active == True)).first()  # noqa: E712
    e = Collection(card_id=card.id, profile_id=profile.id)
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


# ---------------------------------------------------------------------------
# GET /recommendations
# ---------------------------------------------------------------------------

class TestRecommendations:
    def test_empty_database_returns_empty_recommendations(self, client):
        response = client.get("/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert data["total_species"] == 0
        assert data["owned_species"] == 0
        assert data["total_missing_species"] == 0
        assert data["recommendations"] == []

    def test_all_species_missing_recommends_sets_with_pokemon_cards(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)

        data = client.get("/recommendations").json()

        assert data["total_species"] == 2
        assert data["owned_species"] == 0
        assert data["total_missing_species"] == 2
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["missing_species_count"] == 2

    def test_owned_species_reduces_set_score(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        card_b = _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)

        _collect(session, card_b)

        data = client.get("/recommendations").json()

        assert data["total_species"] == 2
        assert data["owned_species"] == 1
        assert data["total_missing_species"] == 1
        assert data["recommendations"][0]["missing_species_count"] == 1

    def test_set_with_zero_missing_species_excluded(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        set_b = _set(session, "base1", "Set B")

        card_a1 = _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "base1-4", set_b, charmander)

        _collect(session, card_a1)

        data = client.get("/recommendations").json()

        set_ids = [r["set_id"] for r in data["recommendations"]]
        assert set_a.id not in set_ids
        assert set_b.id in set_ids

    def test_trainer_only_set_not_recommended(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        trainer_set = _set(session, "trainer1", "Trainer Set")
        _card(session, "trainer1-1", trainer_set, species=None)
        _card(session, "trainer1-2", trainer_set, species=None)

        pokemon_set = _set(session, "sv1", "Pokémon Set")
        _card(session, "sv1-1", pokemon_set, bulbasaur)

        data = client.get("/recommendations").json()

        set_ids = [r["set_id"] for r in data["recommendations"]]
        assert trainer_set.id not in set_ids
        assert pokemon_set.id in set_ids

    def test_tie_break_fewer_total_cards_first(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        # Set A: 1 Pokémon card + 2 trainer cards = 3 total
        set_a = _set(session, "sv1", "Set A", release_date=date(2023, 1, 1))
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-t1", set_a, species=None)
        _card(session, "sv1-t2", set_a, species=None)

        # Set B: 1 Pokémon card only = 1 total
        set_b = _set(session, "base1", "Set B", release_date=date(2023, 1, 1))
        _card(session, "base1-1", set_b, bulbasaur)

        data = client.get("/recommendations").json()

        recs = data["recommendations"]
        assert len(recs) == 2
        assert recs[0]["set_id"] == set_b.id
        assert recs[1]["set_id"] == set_a.id

    def test_tie_break_newest_release_date_second(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        set_old = _set(session, "old1", "Old Set", release_date=date(2000, 1, 1))
        _card(session, "old1-1", set_old, bulbasaur)

        set_new = _set(session, "new1", "New Set", release_date=date(2024, 6, 1))
        _card(session, "new1-1", set_new, bulbasaur)

        data = client.get("/recommendations").json()

        recs = data["recommendations"]
        assert recs[0]["set_id"] == set_new.id
        assert recs[1]["set_id"] == set_old.id

    def test_duplicate_cards_same_species_dont_inflate_score(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-2", set_a, bulbasaur)
        _card(session, "sv1-3", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, bulbasaur)
        _card(session, "sv1-5", set_a, bulbasaur)

        data = client.get("/recommendations").json()

        assert data["recommendations"][0]["missing_species_count"] == 1

    def test_duplicate_collection_entries_dont_affect_recommendations(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        card_b = _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)

        _collect(session, card_b)
        _collect(session, card_b)
        _collect(session, card_b)

        data = client.get("/recommendations").json()

        assert data["total_missing_species"] == 1
        assert data["recommendations"][0]["missing_species_count"] == 1

    def test_full_completion_returns_empty_recommendations(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        set_a = _set(session, "sv1", "Set A")
        card = _card(session, "sv1-1", set_a, bulbasaur)
        _collect(session, card)

        data = client.get("/recommendations").json()

        assert data["total_missing_species"] == 0
        assert data["recommendations"] == []

    def test_limit_param_is_respected(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        for i in range(5):
            s = _set(session, f"set{i}", f"Set {i}")
            _card(session, f"set{i}-1", s, bulbasaur)

        data = client.get("/recommendations", params={"limit": 2}).json()

        assert len(data["recommendations"]) == 2

    # ------------------------------------------------------------------
    # New computed fields
    # ------------------------------------------------------------------

    def test_rank_is_sequential_starting_at_one(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")
        squirtle = _species(session, 7, "squirtle")

        # Set A has 3 missing species, Set B has 1
        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)
        _card(session, "sv1-7", set_a, squirtle)

        set_b = _set(session, "base1", "Set B")
        _card(session, "base1-1", set_b, bulbasaur)

        data = client.get("/recommendations").json()

        recs = data["recommendations"]
        assert recs[0]["rank"] == 1
        assert recs[1]["rank"] == 2

    def test_coverage_percentage_calculation(self, client, session):
        """2 missing species in set / 4 total missing = 50.0%"""
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")
        squirtle = _species(session, 7, "squirtle")
        pikachu = _species(session, 25, "pikachu")

        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)

        data = client.get("/recommendations").json()

        assert data["total_missing_species"] == 4
        assert data["recommendations"][0]["missing_species_count"] == 2
        assert data["recommendations"][0]["coverage_percentage"] == 50.0

    def test_coverage_percentage_with_partial_ownership(self, client, session):
        """1 missing in set / 2 total missing = 50.0%"""
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")
        squirtle = _species(session, 7, "squirtle")

        set_a = _set(session, "sv1", "Set A")
        card_b = _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)
        _card(session, "sv1-7", set_a, squirtle)

        _collect(session, card_b)

        data = client.get("/recommendations").json()

        # Total missing = 2 (charmander, squirtle). Set A has both.
        assert data["total_missing_species"] == 2
        assert data["recommendations"][0]["coverage_percentage"] == 100.0

    def test_missing_species_density_percentage_calculation(self, client, session):
        """1 missing species / 4 total cards in set = 25.0%"""
        bulbasaur = _species(session, 1, "bulbasaur")

        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-t1", set_a, species=None)
        _card(session, "sv1-t2", set_a, species=None)
        _card(session, "sv1-t3", set_a, species=None)

        data = client.get("/recommendations").json()

        rec = data["recommendations"][0]
        assert rec["missing_species_count"] == 1
        assert rec["total_cards_in_set"] == 4
        assert rec["missing_species_density_percentage"] == 25.0

    def test_missing_species_density_percentage_high_density(self, client, session):
        """3 missing species / 3 total cards = 100.0%"""
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")
        squirtle = _species(session, 7, "squirtle")

        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)
        _card(session, "sv1-7", set_a, squirtle)

        data = client.get("/recommendations").json()

        assert data["recommendations"][0]["missing_species_density_percentage"] == 100.0

    def test_total_species_in_set_includes_owned(self, client, session):
        """total_species_in_set counts ALL species in the set, including owned ones."""
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        card_b = _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)

        # Own bulbasaur — but total_species_in_set should still be 2
        _collect(session, card_b)

        data = client.get("/recommendations").json()

        rec = data["recommendations"][0]
        assert rec["total_species_in_set"] == 2
        assert rec["missing_species_count"] == 1

    def test_response_matches_schema_fields(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", set_a, bulbasaur)

        data = client.get("/recommendations").json()

        assert set(data.keys()) == set(RecommendationResponse.model_fields)
        rec = data["recommendations"][0]
        assert set(rec.keys()) == set(SetRecommendation.model_fields)


# ---------------------------------------------------------------------------
# GET /recommendations/{set_id}/species
# ---------------------------------------------------------------------------

class TestMissingSpeciesInSet:
    def test_returns_missing_species_in_set(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)

        response = client.get(f"/recommendations/{set_a.id}/species")

        assert response.status_code == 200
        names = [s["name"] for s in response.json()]
        assert "bulbasaur" in names
        assert "charmander" in names

    def test_excludes_owned_species(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        card_b = _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)

        _collect(session, card_b)

        data = client.get(f"/recommendations/{set_a.id}/species").json()

        names = [s["name"] for s in data]
        assert "bulbasaur" not in names
        assert "charmander" in names

    def test_returns_empty_list_when_all_owned(self, client, session):
        bulbasaur = _species(session, 1, "bulbasaur")

        set_a = _set(session, "sv1", "Set A")
        card = _card(session, "sv1-1", set_a, bulbasaur)
        _collect(session, card)

        data = client.get(f"/recommendations/{set_a.id}/species").json()

        assert data == []

    def test_returns_empty_list_for_unknown_set(self, client):
        data = client.get("/recommendations/99999/species").json()
        assert data == []

    def test_ordered_by_dex_number(self, client, session):
        squirtle = _species(session, 7, "squirtle")
        bulbasaur = _species(session, 1, "bulbasaur")
        charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-7", set_a, squirtle)
        _card(session, "sv1-1", set_a, bulbasaur)
        _card(session, "sv1-4", set_a, charmander)

        data = client.get(f"/recommendations/{set_a.id}/species").json()

        dex_numbers = [s["national_dex_number"] for s in data]
        assert dex_numbers == [1, 4, 7]
