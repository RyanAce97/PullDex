"""Tests for the /card-data router and the local card-data version service.

The HTTP fetch is monkeypatched so no network access occurs.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.app_metadata import AppMetadata
from app.services import card_data_update_service as svc
from app.services.card_data_version_service import (
    DEFAULT_CARD_DATA_VERSION,
    get_local_card_data_version,
    set_local_card_data_version,
)


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
# Version service
# ---------------------------------------------------------------------------

class TestVersionService:
    def test_default_when_missing(self, session):
        assert get_local_card_data_version(session) == DEFAULT_CARD_DATA_VERSION

    def test_reads_stored_value(self, session):
        session.add(AppMetadata(key="card_data_version", value="3"))
        session.commit()
        assert get_local_card_data_version(session) == 3

    def test_non_numeric_falls_back(self, session):
        session.add(AppMetadata(key="card_data_version", value="oops"))
        session.commit()
        assert get_local_card_data_version(session) == DEFAULT_CARD_DATA_VERSION

    def test_set_then_get(self, session):
        set_local_card_data_version(session, 5)
        assert get_local_card_data_version(session) == 5
        # updates existing row rather than duplicating
        set_local_card_data_version(session, 6)
        assert get_local_card_data_version(session) == 6
        # only one metadata row for the key
        from sqlmodel import select
        all_rows = session.exec(select(AppMetadata).where(AppMetadata.key == "card_data_version")).all()
        assert len(all_rows) == 1


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class TestUpdateCheckRoute:
    def test_up_to_date(self, client, session, monkeypatch):
        # local defaults to 1 (no row) ; remote 1
        _patch_fetch(monkeypatch, _manifest(data_version=1))
        resp = client.get("/card-data/update-check")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "UP_TO_DATE"
        assert body["local_data_version"] == 1
        assert body["remote_data_version"] == 1
        assert body["remote_set_count"] == 2
        assert body["remote_card_count"] == 191
        assert body["update_available"] is False
        assert len(body["sets"]) == 2

    def test_update_available(self, client, session, monkeypatch):
        _patch_fetch(monkeypatch, _manifest(data_version=2))
        body = client.get("/card-data/update-check").json()
        assert body["status"] == "UPDATE_AVAILABLE"
        assert body["update_available"] is True

    def test_remote_unavailable(self, client, session, monkeypatch):
        _patch_fetch(monkeypatch, exc=TimeoutError("boom"))
        body = client.get("/card-data/update-check").json()
        assert body["status"] == "REMOTE_UNAVAILABLE"
        assert body["remote_data_version"] is None

    def test_invalid_manifest(self, client, session, monkeypatch):
        _patch_fetch(monkeypatch, "{ bad json")
        body = client.get("/card-data/update-check").json()
        assert body["status"] == "INVALID_MANIFEST"

    def test_incompatible_schema(self, client, session, monkeypatch):
        _patch_fetch(monkeypatch, _manifest(schema_version=2))
        body = client.get("/card-data/update-check").json()
        assert body["status"] == "INCOMPATIBLE_SCHEMA"

    def test_route_respects_stored_local_version(self, client, session, monkeypatch):
        session.add(AppMetadata(key="card_data_version", value="2"))
        session.commit()
        _patch_fetch(monkeypatch, _manifest(data_version=2))
        body = client.get("/card-data/update-check").json()
        assert body["local_data_version"] == 2
        assert body["status"] == "UP_TO_DATE"
