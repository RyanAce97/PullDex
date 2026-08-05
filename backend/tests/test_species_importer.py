"""Unit tests for the PokémonSpecies importer.

All tests use an in-memory SQLite database and mocked API responses —
no network calls and no disk writes.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.pokemon_species import PokemonSpecies
from app.services.importers.species_importer import (
    import_all_species,
    parse_generation,
    upsert_species,
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
# parse_generation
# ---------------------------------------------------------------------------

class TestParseGeneration:
    def test_generation_i(self):
        assert parse_generation("generation-i") == 1

    def test_generation_iv(self):
        assert parse_generation("generation-iv") == 4

    def test_generation_viii(self):
        assert parse_generation("generation-viii") == 8

    def test_generation_ix(self):
        assert parse_generation("generation-ix") == 9

    def test_unknown_returns_none(self):
        assert parse_generation("generation-x") is None

    def test_empty_string_returns_none(self):
        assert parse_generation("") is None

    def test_malformed_returns_none(self):
        assert parse_generation("not-a-generation") is None


# ---------------------------------------------------------------------------
# upsert_species
# ---------------------------------------------------------------------------

_BULBASAUR_DATA = {
    "id": 1,
    "name": "bulbasaur",
    "generation": {"name": "generation-i", "url": "https://pokeapi.co/api/v2/generation/1/"},
}

_PIKACHU_DATA = {
    "id": 25,
    "name": "pikachu",
    "generation": {"name": "generation-i", "url": "https://pokeapi.co/api/v2/generation/1/"},
}


class TestUpsertSpecies:
    def test_inserts_new_species(self, session):
        upsert_species(session, _BULBASAUR_DATA)
        session.commit()

        result = session.exec(
            select(PokemonSpecies).where(PokemonSpecies.national_dex_number == 1)
        ).first()

        assert result is not None
        assert result.name == "bulbasaur"
        assert result.national_dex_number == 1
        assert result.generation == 1

    def test_updates_existing_species(self, session):
        # Insert original record.
        upsert_species(session, _BULBASAUR_DATA)
        session.commit()

        # Re-import with an updated name (simulating a corrected spelling).
        updated = {**_BULBASAUR_DATA, "name": "bulbasaur-updated"}
        upsert_species(session, updated)
        session.commit()

        results = session.exec(
            select(PokemonSpecies).where(PokemonSpecies.national_dex_number == 1)
        ).all()

        # Must not duplicate — still exactly one row.
        assert len(results) == 1
        assert results[0].name == "bulbasaur-updated"

    def test_returns_species_instance(self, session):
        result = upsert_species(session, _PIKACHU_DATA)
        assert isinstance(result, PokemonSpecies)
        assert result.name == "pikachu"

    def test_handles_missing_generation(self, session):
        data = {"id": 1, "name": "bulbasaur", "generation": None}
        species = upsert_species(session, data)
        session.commit()
        assert species.generation is None

    def test_multiple_species_no_collision(self, session):
        upsert_species(session, _BULBASAUR_DATA)
        upsert_species(session, _PIKACHU_DATA)
        session.commit()

        all_species = session.exec(select(PokemonSpecies)).all()
        assert len(all_species) == 2


# ---------------------------------------------------------------------------
# import_all_species
# ---------------------------------------------------------------------------

class TestImportAllSpecies:
    def _make_list_response(self, names: list[str]) -> dict:
        return {
            "count": len(names),
            "next": None,
            "previous": None,
            "results": [{"name": n, "url": f"https://pokeapi.co/api/v2/pokemon-species/{n}/"} for n in names],
        }

    def _make_detail(self, dex_number: int, name: str, gen: str = "generation-i") -> dict:
        return {
            "id": dex_number,
            "name": name,
            "generation": {"name": gen, "url": ""},
        }

    def test_imports_species_into_database(self, session):
        list_response = self._make_list_response(["bulbasaur", "ivysaur"])
        details = {
            "bulbasaur": self._make_detail(1, "bulbasaur"),
            "ivysaur": self._make_detail(2, "ivysaur"),
        }

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_pokemon_species_page.return_value = list_response
        mock_client.get_pokemon_species.side_effect = lambda name: details[name]

        with (
            patch("app.services.importers.species_importer.PokeApiClient", return_value=mock_client),
            patch("app.services.importers.species_importer.get_session_context") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            import_all_species()

        results = session.exec(select(PokemonSpecies)).all()
        assert len(results) == 2
        names = {s.name for s in results}
        assert names == {"bulbasaur", "ivysaur"}

    def test_is_idempotent(self, session):
        """Running the importer twice must not duplicate rows."""
        list_response = self._make_list_response(["bulbasaur"])
        detail = self._make_detail(1, "bulbasaur")

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_pokemon_species_page.return_value = list_response
        mock_client.get_pokemon_species.return_value = detail

        with (
            patch("app.services.importers.species_importer.PokeApiClient", return_value=mock_client),
            patch("app.services.importers.species_importer.get_session_context") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            import_all_species()
            import_all_species()

        results = session.exec(select(PokemonSpecies)).all()
        assert len(results) == 1
