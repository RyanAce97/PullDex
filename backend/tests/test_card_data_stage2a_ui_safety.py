"""Stage 2A database-safety tests for the card-data update UI.

Stage 2A adds a UI that *displays* the read-only card-data update status. The
only backend endpoint that UI touches is ``GET /card-data/update-check`` (the
Stage 1 endpoint). These tests prove, at the router level, that exercising
that endpoint — for every possible status, and including the case the UI cares
about most (UPDATE_AVAILABLE, which drives the "Update Card Data" button) —
modifies NONE of the card or user data:

    * cards
    * sets
    * collection (ownership / quantities / binder selection)
    * profiles
    * pokemon_species
    * the local card-data version (app_metadata)

The remote manifest fetch is monkeypatched, so no network access occurs.

Stage 2A explicitly does NOT download set files, import/merge cards, or write
to the database. The "Update Card Data" button in the UI is non-functional
(it opens an informational dialog only) and never calls this or any other
endpoint, so there is no additional backend surface to test for the button
itself — its inertness is proven in the frontend test suite.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.main import app
from app.models.app_metadata import AppMetadata
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.profile import Profile
from app.models.set import Set
from app.services import card_data_update_service as svc


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


@pytest.fixture(name="seeded_session")
def seeded_session_fixture(session):
    """Seed a realistic slice of card + user data to snapshot around."""
    # Reference data
    species = PokemonSpecies(national_dex_number=25, name="Pikachu", generation=1)
    session.add(species)
    session.commit()
    session.refresh(species)

    tcg_set = Set(api_set_id="me55", name="30th Celebration", series="Mega Evolution")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)

    cards = []
    for i in range(1, 6):
        c = Card(
            api_card_id=f"me55-{i}",
            set_id=tcg_set.id,
            pokemon_species_id=species.id,
            card_number=str(i),
        )
        cards.append(c)
        session.add(c)
    session.commit()
    for c in cards:
        session.refresh(c)

    # User data (a profile is auto-created by the autouse conftest fixture)
    profile = session.exec(select(Profile).where(Profile.is_active == True)).first()  # noqa: E712
    assert profile is not None

    session.add(
        Collection(
            profile_id=profile.id,
            card_id=cards[0].id,
            quantity=3,
            is_binder_card=True,
        )
    )
    session.add(
        Collection(
            profile_id=profile.id,
            pokemon_species_id=species.id,
            quantity=1,
            is_binder_card=False,
        )
    )
    # Local card-data version (isolated metadata)
    session.add(AppMetadata(key="card_data_version", value="1"))
    session.commit()
    return session


@pytest.fixture(name="client")
def client_fixture(seeded_session):
    def override_get_session():
        yield seeded_session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Manifest helpers (no network — fetch is monkeypatched)
# ---------------------------------------------------------------------------

def _sha(n="a"):
    return (n * 64)[:64]


def _manifest(data_version=1, schema_version=1):
    sets = [
        {"id": "me55", "name": "30th Celebration", "file": "sets/me55.json",
         "version": 1, "sha256": _sha("a"), "card_count": 161},
        {"id": "me55c", "name": "30th Celebration: Classic Collection",
         "file": "sets/me55c.json", "version": 1, "sha256": _sha("b"), "card_count": 30},
    ]
    return {
        "schema_version": schema_version,
        "data_version": data_version,
        "updated_at": "2026-09-16T00:00:00Z",
        "set_count": len(sets),
        "card_count": sum(s["card_count"] for s in sets),
        "sets": sets,
    }


def _patch_fetch(monkeypatch, payload=None, exc=None):
    def fake_fetch(url, timeout):
        if exc is not None:
            raise exc
        return payload if isinstance(payload, str) else json.dumps(payload)

    monkeypatch.setattr(svc, "fetch_manifest_text", fake_fetch)


# ---------------------------------------------------------------------------
# Snapshot of every table Stage 2A must never touch
# ---------------------------------------------------------------------------

def _snapshot(session: Session) -> dict:
    def rows(model, cols):
        out = []
        for obj in session.exec(select(model)).all():
            out.append(tuple(getattr(obj, c) for c in cols))
        return sorted(out, key=lambda r: tuple(str(x) for x in r))

    return {
        "pokemon_species": rows(PokemonSpecies, ["id", "national_dex_number", "name", "generation"]),
        "sets": rows(Set, ["id", "api_set_id", "name", "series"]),
        "cards": rows(Card, ["id", "api_card_id", "set_id", "pokemon_species_id", "card_number", "rarity", "variant"]),
        "collection": rows(Collection, ["id", "profile_id", "card_id", "pokemon_species_id", "quantity", "is_binder_card"]),
        "profiles": rows(Profile, ["id", "name", "is_active"]),
        "app_metadata": rows(AppMetadata, ["key", "value"]),
    }


# ---------------------------------------------------------------------------
# Tests: every status leaves all data untouched
# ---------------------------------------------------------------------------

class TestStage2ARouterDatabaseSafety:
    @pytest.mark.parametrize(
        "label, payload, exc, expected_status",
        [
            ("up_to_date", _manifest(data_version=1), None, "UP_TO_DATE"),
            ("update_available", _manifest(data_version=2), None, "UPDATE_AVAILABLE"),
            ("remote_unavailable", None, TimeoutError("boom"), "REMOTE_UNAVAILABLE"),
            ("invalid_manifest", "{ bad json", None, "INVALID_MANIFEST"),
            ("incompatible_schema", _manifest(schema_version=2), None, "INCOMPATIBLE_SCHEMA"),
        ],
    )
    def test_update_check_never_modifies_data(
        self, client, seeded_session, monkeypatch, label, payload, exc, expected_status
    ):
        before = _snapshot(seeded_session)

        _patch_fetch(monkeypatch, payload=payload, exc=exc)
        resp = client.get("/card-data/update-check")

        assert resp.status_code == 200, label
        assert resp.json()["status"] == expected_status, label

        after = _snapshot(seeded_session)
        assert before == after, f"{label}: /card-data/update-check must not modify any data"

    def test_local_card_data_version_unchanged(self, client, seeded_session, monkeypatch):
        """The UPDATE_AVAILABLE path (button-driving) must not bump the local version."""
        _patch_fetch(monkeypatch, payload=_manifest(data_version=9))
        body = client.get("/card-data/update-check").json()
        assert body["status"] == "UPDATE_AVAILABLE"
        assert body["update_available"] is True

        row = seeded_session.exec(
            select(AppMetadata).where(AppMetadata.key == "card_data_version")
        ).first()
        assert row is not None
        # Still the original local version — no download/import/version bump.
        assert row.value == "1"

    def test_repeated_checks_are_idempotent_on_data(self, client, seeded_session, monkeypatch):
        """Even multiple checks in a session leave data byte-identical."""
        before = _snapshot(seeded_session)
        _patch_fetch(monkeypatch, payload=_manifest(data_version=2))
        for _ in range(3):
            assert client.get("/card-data/update-check").status_code == 200
        after = _snapshot(seeded_session)
        assert before == after
