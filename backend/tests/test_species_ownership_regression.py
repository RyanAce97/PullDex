"""Regression tests: species-level ownership consistency.

These tests verify the core product rule across all systems:
"A species is owned if the user has at least one card for that species."

This rule must be consistent in:
  - /progress
  - /progress/missing
  - /species/summary
  - /recommendations
  - /recommendations/{set_id}/species
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


def _set(session: Session, api_set_id: str, name: str = "Test Set") -> Set:
    s = Set(api_set_id=api_set_id, name=name, series="Test")
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


def _collect(session: Session, card: Card) -> None:
    session.add(Collection(card_id=card.id))
    session.commit()


# ---------------------------------------------------------------------------
# Scenario: Pikachu has many card variants, user owns just one
# ---------------------------------------------------------------------------

class TestSpeciesOwnershipWithManyVariants:
    """Pikachu has 5 card variants across 3 sets.
    User owns exactly 1 Pikachu card.
    Pikachu must be considered OWNED everywhere.
    """

    @pytest.fixture(autouse=True)
    def setup(self, session):
        self.pikachu = _species(session, 25, "pikachu")
        self.charmander = _species(session, 4, "charmander")

        set_a = _set(session, "sv1", "Set A")
        set_b = _set(session, "base1", "Set B")
        set_c = _set(session, "xy1", "Set C")

        # 5 Pikachu cards across 3 sets
        self.pika_card_1 = _card(session, "sv1-25", set_a, self.pikachu)
        _card(session, "sv1-25-rh", set_a, self.pikachu)
        _card(session, "base1-25", set_b, self.pikachu)
        _card(session, "base1-25-holo", set_b, self.pikachu)
        _card(session, "xy1-25", set_c, self.pikachu)

        # 2 Charmander cards (not owned)
        _card(session, "sv1-4", set_a, self.charmander)
        _card(session, "base1-4", set_b, self.charmander)

        # User owns exactly 1 Pikachu card
        _collect(session, self.pika_card_1)

    def test_progress_counts_pikachu_as_owned(self, client):
        data = client.get("/progress").json()

        assert data["total_species"] == 2
        assert data["owned_species"] == 1
        assert data["missing_species"] == 1

    def test_pikachu_not_in_missing_species_list(self, client):
        data = client.get("/progress/missing").json()

        names = [s["name"] for s in data]
        assert "pikachu" not in names
        assert "charmander" in names

    def test_species_summary_shows_pikachu_owned(self, client):
        data = client.get("/species/summary").json()

        pikachu_row = next(r for r in data if r["name"] == "pikachu")
        charmander_row = next(r for r in data if r["name"] == "charmander")

        assert pikachu_row["owned"] is True
        assert charmander_row["owned"] is False

    def test_recommendations_exclude_pikachu_from_missing_count(self, client):
        """Sets should only count Charmander as missing, not Pikachu."""
        data = client.get("/recommendations").json()

        assert data["total_missing_species"] == 1

        for rec in data["recommendations"]:
            # No set should recommend Pikachu — it's already owned
            assert rec["missing_species_count"] <= 1

    def test_recommendation_drilldown_excludes_pikachu(self, client, session):
        """Drilling into any set should never list Pikachu as missing."""
        # Get all sets
        sets_data = client.get("/sets").json()

        for s in sets_data:
            species_data = client.get(f"/recommendations/{s['id']}/species").json()
            names = [sp["name"] for sp in species_data]
            assert "pikachu" not in names


# ---------------------------------------------------------------------------
# Scenario: User owns multiple variants of the same species
# ---------------------------------------------------------------------------

class TestMultipleVariantsStillOneSpecies:
    """User owns 3 different Pikachu cards.
    Pikachu should still count as exactly 1 owned species.
    """

    @pytest.fixture(autouse=True)
    def setup(self, session):
        self.pikachu = _species(session, 25, "pikachu")
        self.bulbasaur = _species(session, 1, "bulbasaur")

        set_a = _set(session, "sv1", "Set A")

        card1 = _card(session, "sv1-25a", set_a, self.pikachu)
        card2 = _card(session, "sv1-25b", set_a, self.pikachu)
        card3 = _card(session, "sv1-25c", set_a, self.pikachu)
        _card(session, "sv1-1", set_a, self.bulbasaur)

        _collect(session, card1)
        _collect(session, card2)
        _collect(session, card3)

    def test_progress_counts_one_owned_species(self, client):
        data = client.get("/progress").json()

        assert data["owned_species"] == 1
        assert data["missing_species"] == 1

    def test_completion_percentage_is_50(self, client):
        """1 owned / 2 total = 50%"""
        data = client.get("/progress").json()
        assert data["completion_percentage"] == 50.0

    def test_missing_list_only_shows_bulbasaur(self, client):
        data = client.get("/progress/missing").json()

        assert len(data) == 1
        assert data[0]["name"] == "bulbasaur"

    def test_species_summary_pikachu_owned_bulbasaur_missing(self, client):
        data = client.get("/species/summary").json()

        pikachu = next(r for r in data if r["name"] == "pikachu")
        bulbasaur = next(r for r in data if r["name"] == "bulbasaur")

        assert pikachu["owned"] is True
        assert bulbasaur["owned"] is False


# ---------------------------------------------------------------------------
# Scenario: User owns zero cards for a species
# ---------------------------------------------------------------------------

class TestNoCardsOwnedMeansSpeciesMissing:
    """Pikachu has cards in the DB but user owns none.
    Pikachu must appear as missing everywhere.
    """

    @pytest.fixture(autouse=True)
    def setup(self, session):
        self.pikachu = _species(session, 25, "pikachu")

        set_a = _set(session, "sv1", "Set A")
        _card(session, "sv1-25a", set_a, self.pikachu)
        _card(session, "sv1-25b", set_a, self.pikachu)
        _card(session, "sv1-25c", set_a, self.pikachu)

    def test_progress_shows_zero_owned(self, client):
        data = client.get("/progress").json()

        assert data["owned_species"] == 0
        assert data["missing_species"] == 1

    def test_pikachu_in_missing_list(self, client):
        data = client.get("/progress/missing").json()

        assert len(data) == 1
        assert data[0]["name"] == "pikachu"

    def test_species_summary_shows_pikachu_not_owned(self, client):
        data = client.get("/species/summary").json()

        assert data[0]["owned"] is False

    def test_recommendations_include_pikachu_as_missing(self, client):
        data = client.get("/recommendations").json()

        assert data["total_missing_species"] == 1
        assert data["recommendations"][0]["missing_species_count"] == 1

    def test_recommendation_drilldown_shows_pikachu(self, client, session):
        sets_data = client.get("/sets").json()

        for s in sets_data:
            species_data = client.get(f"/recommendations/{s['id']}/species").json()
            if species_data:
                names = [sp["name"] for sp in species_data]
                assert "pikachu" in names
