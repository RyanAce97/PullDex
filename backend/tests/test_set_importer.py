"""Unit tests for the Set importer.

All tests use an in-memory SQLite database and mocked API responses —
no network calls and no disk writes.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.set import Set
from app.services.importers.set_importer import (
    import_all_sets,
    parse_release_date,
    upsert_set,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    """Provide an in-memory SQLite session with the schema created."""
    engine = create_engine(
        "sqlite://",  # pure in-memory, no file
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_BASE_SET_DATA = {
    "id": "base1",
    "name": "Base Set",
    "series": "Base",
    "releaseDate": "1999/01/09",
}

_SV1_DATA = {
    "id": "sv1",
    "name": "Scarlet & Violet",
    "series": "Scarlet & Violet",
    "releaseDate": "2023/03/31",
}


# ---------------------------------------------------------------------------
# parse_release_date
# ---------------------------------------------------------------------------

class TestParseReleaseDate:
    def test_parses_valid_date(self):
        assert parse_release_date("2023/03/31") == date(2023, 3, 31)

    def test_parses_single_digit_month_and_day(self):
        assert parse_release_date("1999/01/09") == date(1999, 1, 9)

    def test_returns_none_for_none(self):
        assert parse_release_date(None) is None

    def test_returns_none_for_empty_string(self):
        assert parse_release_date("") is None

    def test_returns_none_for_malformed_string(self):
        assert parse_release_date("not-a-date") is None

    def test_returns_none_for_partial_date(self):
        assert parse_release_date("2023/03") is None


# ---------------------------------------------------------------------------
# upsert_set
# ---------------------------------------------------------------------------

class TestUpsertSet:
    def test_inserts_new_set(self, session):
        upsert_set(session, _BASE_SET_DATA)
        session.commit()

        result = session.exec(
            select(Set).where(Set.api_set_id == "base1")
        ).first()

        assert result is not None
        assert result.api_set_id == "base1"
        assert result.name == "Base Set"
        assert result.series == "Base"
        assert result.release_date == date(1999, 1, 9)

    def test_updates_existing_set(self, session):
        upsert_set(session, _BASE_SET_DATA)
        session.commit()

        updated = {**_BASE_SET_DATA, "name": "Base Set (Updated)"}
        upsert_set(session, updated)
        session.commit()

        results = session.exec(
            select(Set).where(Set.api_set_id == "base1")
        ).all()

        assert len(results) == 1
        assert results[0].name == "Base Set (Updated)"

    def test_update_does_not_create_duplicate(self, session):
        upsert_set(session, _BASE_SET_DATA)
        upsert_set(session, _BASE_SET_DATA)
        session.commit()

        results = session.exec(select(Set)).all()
        assert len(results) == 1

    def test_returns_set_instance(self, session):
        result = upsert_set(session, _SV1_DATA)
        assert isinstance(result, Set)
        assert result.api_set_id == "sv1"

    def test_handles_missing_release_date(self, session):
        data = {**_BASE_SET_DATA, "releaseDate": None}
        tcg_set = upsert_set(session, data)
        session.commit()
        assert tcg_set.release_date is None

    def test_multiple_sets_no_collision(self, session):
        upsert_set(session, _BASE_SET_DATA)
        upsert_set(session, _SV1_DATA)
        session.commit()

        all_sets = session.exec(select(Set)).all()
        assert len(all_sets) == 2


# ---------------------------------------------------------------------------
# import_all_sets
# ---------------------------------------------------------------------------

class TestImportAllSets:
    def _make_response(self, sets: list[dict], total: int | None = None) -> dict:
        return {
            "data": sets,
            "page": 1,
            "pageSize": 250,
            "count": len(sets),
            "totalCount": total if total is not None else len(sets),
        }

    def test_imports_sets_into_database(self, session):
        response = self._make_response([_BASE_SET_DATA, _SV1_DATA])

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_sets.return_value = response

        with (
            patch("app.services.importers.set_importer.PokemonTCGClient", return_value=mock_client),
            patch("app.services.importers.set_importer.get_session_context") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            import_all_sets()

        results = session.exec(select(Set)).all()
        assert len(results) == 2
        ids = {s.api_set_id for s in results}
        assert ids == {"base1", "sv1"}

    def test_is_idempotent(self, session):
        """Running the importer twice must not duplicate rows."""
        response = self._make_response([_BASE_SET_DATA])

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_sets.return_value = response

        with (
            patch("app.services.importers.set_importer.PokemonTCGClient", return_value=mock_client),
            patch("app.services.importers.set_importer.get_session_context") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            import_all_sets()
            import_all_sets()

        results = session.exec(select(Set)).all()
        assert len(results) == 1

    def test_release_date_is_stored_as_date(self, session):
        response = self._make_response([_SV1_DATA])

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_sets.return_value = response

        with (
            patch("app.services.importers.set_importer.PokemonTCGClient", return_value=mock_client),
            patch("app.services.importers.set_importer.get_session_context") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            import_all_sets()

        result = session.exec(select(Set).where(Set.api_set_id == "sv1")).first()
        assert result.release_date == date(2023, 3, 31)
