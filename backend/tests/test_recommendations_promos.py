"""Stage B tests: promo filtering for pack recommendations.

Verifies the ``promos`` flag on GET /recommendations and the service:
  * default (omitted) == non-promo (original Sets behaviour)
  * promos=false excludes every is_promo=true set
  * promos=true excludes every is_promo=false set
  * both pools use identical ranking rules/order
  * limits apply independently per pool
  * no cross-contamination between the two result sets

In-memory SQLite, TestClient with the session dependency overridden.
No disk writes, no live DB, no network.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.recommendation_service import get_set_recommendations


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


def _seed(session):
    """Seed species (all missing — no collection) and a mix of promo/non-promo
    sets, each containing cards for distinct species.

    Non-promo pool: setA -> 3 species, setB -> 2, setC -> 1
    Promo pool:     promoX -> 2 species, promoY -> 1
    """
    species = []
    for dex in range(1, 9):
        s = PokemonSpecies(national_dex_number=dex, name=f"mon{dex}", generation=1)
        session.add(s)
        species.append(s)
    session.commit()
    for s in species:
        session.refresh(s)
    sid = [s.id for s in species]

    def mkset(api_set_id, name, is_promo, release_date):
        st = Set(api_set_id=api_set_id, name=name, series="Test",
                 is_promo=is_promo, release_date=release_date)
        session.add(st)
        session.commit()
        session.refresh(st)
        return st

    setA = mkset("setA", "Set A", False, datetime.date(2020, 1, 1))
    setB = mkset("setB", "Set B", False, datetime.date(2021, 1, 1))
    setC = mkset("setC", "Set C", False, datetime.date(2022, 1, 1))
    promoX = mkset("promoX", "Promo X", True, datetime.date(2023, 1, 1))
    promoY = mkset("promoY", "Promo Y", True, datetime.date(2024, 1, 1))

    def add_cards(st, species_indexes):
        for i, spi in enumerate(species_indexes, start=1):
            session.add(Card(
                api_card_id=f"{st.api_set_id}-{i}",
                set_id=st.id,
                pokemon_species_id=sid[spi],
                card_number=str(i),
            ))
    add_cards(setA, [0, 1, 2])
    add_cards(setB, [3, 4])
    add_cards(setC, [5])
    add_cards(promoX, [0, 1])
    add_cards(promoY, [6])
    session.commit()
    return {
        "setA": setA.id, "setB": setB.id, "setC": setC.id,
        "promoX": promoX.id, "promoY": promoY.id,
    }


class TestServicePromoFilter:
    def test_default_is_non_promo(self, session):
        _seed(session)
        recs = get_set_recommendations(session)
        names = {r["set_name"] for r in recs}
        assert names == {"Set A", "Set B", "Set C"}
        assert "Promo X" not in names and "Promo Y" not in names

    def test_promos_false_excludes_all_promos(self, session):
        ids = _seed(session)
        recs = get_set_recommendations(session, promos=False)
        result_ids = {r["set_id"] for r in recs}
        assert ids["promoX"] not in result_ids
        assert ids["promoY"] not in result_ids
        assert result_ids == {ids["setA"], ids["setB"], ids["setC"]}

    def test_promos_true_excludes_all_non_promos(self, session):
        ids = _seed(session)
        recs = get_set_recommendations(session, promos=True)
        result_ids = {r["set_id"] for r in recs}
        assert result_ids == {ids["promoX"], ids["promoY"]}
        for non_promo in ("setA", "setB", "setC"):
            assert ids[non_promo] not in result_ids

    def test_same_ranking_rules_both_pools(self, session):
        _seed(session)
        sets = get_set_recommendations(session, promos=False)
        promos = get_set_recommendations(session, promos=True)
        assert [r["set_name"] for r in sets] == ["Set A", "Set B", "Set C"]
        assert [r["rank"] for r in sets] == [1, 2, 3]
        assert [r["set_name"] for r in promos] == ["Promo X", "Promo Y"]
        assert [r["rank"] for r in promos] == [1, 2]
        assert sets[0]["missing_species_count"] == 3
        assert promos[0]["missing_species_count"] == 2

    def test_limits_apply_independently(self, session):
        _seed(session)
        sets = get_set_recommendations(session, promos=False, limit=1)
        promos = get_set_recommendations(session, promos=True, limit=1)
        assert len(sets) == 1 and sets[0]["set_name"] == "Set A"
        assert len(promos) == 1 and promos[0]["set_name"] == "Promo X"

    def test_no_cross_contamination(self, session):
        _seed(session)
        set_ids = {r["set_id"] for r in get_set_recommendations(session, promos=False)}
        promo_ids = {r["set_id"] for r in get_set_recommendations(session, promos=True)}
        assert set_ids.isdisjoint(promo_ids)


class TestRouterPromoFilter:
    def test_default_endpoint_is_non_promo(self, client, session):
        _seed(session)
        body = client.get("/recommendations").json()
        names = {r["set_name"] for r in body["recommendations"]}
        assert names == {"Set A", "Set B", "Set C"}

    def test_promos_false_query(self, client, session):
        _seed(session)
        body = client.get("/recommendations", params={"promos": "false"}).json()
        names = {r["set_name"] for r in body["recommendations"]}
        assert names == {"Set A", "Set B", "Set C"}

    def test_promos_true_query(self, client, session):
        _seed(session)
        body = client.get("/recommendations", params={"promos": "true"}).json()
        names = {r["set_name"] for r in body["recommendations"]}
        assert names == {"Promo X", "Promo Y"}

    def test_response_shape_unchanged(self, client, session):
        _seed(session)
        body = client.get("/recommendations", params={"promos": "true"}).json()
        assert set(body.keys()) == {
            "total_species", "owned_species", "total_missing_species", "recommendations",
        }
        rec = body["recommendations"][0]
        assert set(rec.keys()) == {
            "rank", "set_id", "api_set_id", "set_name", "series", "release_date",
            "missing_species_count", "total_species_in_set", "total_cards_in_set",
            "coverage_percentage", "missing_species_density_percentage",
        }

    def test_limit_respected_per_mode(self, client, session):
        _seed(session)
        sets = client.get("/recommendations", params={"promos": "false", "limit": 2}).json()
        promos = client.get("/recommendations", params={"promos": "true", "limit": 1}).json()
        assert len(sets["recommendations"]) == 2
        assert len(promos["recommendations"]) == 1

    def test_no_promo_recommendations_returns_empty_list(self, client, session):
        s = PokemonSpecies(national_dex_number=1, name="mon1", generation=1)
        session.add(s); session.commit(); session.refresh(s)
        st = Set(api_set_id="setA", name="Set A", series="Test", is_promo=False)
        session.add(st); session.commit(); session.refresh(st)
        session.add(Card(api_card_id="setA-1", set_id=st.id, pokemon_species_id=s.id, card_number="1"))
        session.commit()
        body = client.get("/recommendations", params={"promos": "true"}).json()
        assert body["recommendations"] == []
