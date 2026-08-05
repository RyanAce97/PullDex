"""Unit tests for the Card importer.

All tests use an in-memory SQLite database and mocked API responses —
no network calls and no disk writes.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.card import Card
from app.models.pokemon_species import PokemonSpecies
from app.models.set import Set
from app.services.importers.card_importer import (
    import_all_cards,
    upsert_card,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    """Provide an in-memory SQLite session with the full schema created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="sv1_set")
def sv1_set_fixture(session):
    """A persisted Set row for Scarlet & Violet Base Set."""
    tcg_set = Set(api_set_id="sv1", name="Scarlet & Violet", series="Scarlet & Violet")
    session.add(tcg_set)
    session.commit()
    session.refresh(tcg_set)
    return tcg_set


@pytest.fixture(name="bulbasaur_species")
def bulbasaur_species_fixture(session):
    """A persisted PokemonSpecies row for Bulbasaur (#1)."""
    species = PokemonSpecies(national_dex_number=1, name="bulbasaur", generation=1)
    session.add(species)
    session.commit()
    session.refresh(species)
    return species


# ---------------------------------------------------------------------------
# Sample API card data
# ---------------------------------------------------------------------------

def _make_card_data(
    card_id: str = "sv1-1",
    api_set_id: str = "sv1",
    dex_numbers: list[int] | None = None,
    number: str = "001/198",
    rarity: str = "Common",
    image_large: str = "https://images.pokemontcg.io/sv1/1_hires.png",
) -> dict:
    return {
        "id": card_id,
        "number": number,
        "rarity": rarity,
        "set": {"id": api_set_id},
        "nationalPokedexNumbers": dex_numbers if dex_numbers is not None else [1],
        "images": {
            "small": "https://images.pokemontcg.io/sv1/1.png",
            "large": image_large,
        },
    }


# ---------------------------------------------------------------------------
# upsert_card
# ---------------------------------------------------------------------------

class TestUpsertCard:
    def test_creates_new_card(self, session, sv1_set, bulbasaur_species):
        data = _make_card_data()
        upsert_card(session, data)
        session.commit()

        result = session.exec(select(Card).where(Card.api_card_id == "sv1-1")).first()

        assert result is not None
        assert result.api_card_id == "sv1-1"
        assert result.card_number == "001/198"
        assert result.rarity == "Common"
        assert result.image_url == "https://images.pokemontcg.io/sv1/1_hires.png"

    def test_links_set(self, session, sv1_set, bulbasaur_species):
        upsert_card(session, _make_card_data())
        session.commit()

        card = session.exec(select(Card).where(Card.api_card_id == "sv1-1")).first()
        assert card.set_id == sv1_set.id

    def test_links_pokemon_species(self, session, sv1_set, bulbasaur_species):
        upsert_card(session, _make_card_data(dex_numbers=[1]))
        session.commit()

        card = session.exec(select(Card).where(Card.api_card_id == "sv1-1")).first()
        assert card.pokemon_species_id == bulbasaur_species.id

    def test_no_species_id_for_card_without_dex_number(self, session, sv1_set):
        """Trainer and energy cards have no nationalPokedexNumbers."""
        data = _make_card_data(card_id="sv1-trainer", dex_numbers=[])
        upsert_card(session, data)
        session.commit()

        card = session.exec(select(Card).where(Card.api_card_id == "sv1-trainer")).first()
        assert card.pokemon_species_id is None

    def test_no_species_id_when_species_not_in_db(self, session, sv1_set):
        """Species FK stays None when the species hasn't been imported yet."""
        data = _make_card_data(dex_numbers=[999])  # dex #999 not in DB
        upsert_card(session, data)
        session.commit()

        card = session.exec(select(Card).where(Card.api_card_id == "sv1-1")).first()
        assert card.pokemon_species_id is None

    def test_no_set_id_when_set_not_in_db(self, session):
        """Set FK stays None when the set hasn't been imported yet."""
        data = _make_card_data(api_set_id="unknown-set")
        upsert_card(session, data)
        session.commit()

        card = session.exec(select(Card).where(Card.api_card_id == "sv1-1")).first()
        assert card.set_id is None

    def test_updates_existing_card(self, session, sv1_set, bulbasaur_species):
        upsert_card(session, _make_card_data())
        session.commit()

        updated = _make_card_data(rarity="Rare Holo")
        upsert_card(session, updated)
        session.commit()

        results = session.exec(select(Card).where(Card.api_card_id == "sv1-1")).all()
        assert len(results) == 1
        assert results[0].rarity == "Rare Holo"

    def test_update_does_not_create_duplicate(self, session, sv1_set, bulbasaur_species):
        upsert_card(session, _make_card_data())
        upsert_card(session, _make_card_data())
        session.commit()

        results = session.exec(select(Card)).all()
        assert len(results) == 1

    def test_prefers_large_image(self, session, sv1_set):
        data = _make_card_data(card_id="sv1-trainer", dex_numbers=[], image_large="https://example.com/large.png")
        upsert_card(session, data)
        session.commit()

        card = session.exec(select(Card).where(Card.api_card_id == "sv1-trainer")).first()
        assert card.image_url == "https://example.com/large.png"

    def test_falls_back_to_small_image_when_no_large(self, session, sv1_set):
        data = _make_card_data(card_id="sv1-noimg", dex_numbers=[])
        data["images"] = {"small": "https://example.com/small.png"}
        upsert_card(session, data)
        session.commit()

        card = session.exec(select(Card).where(Card.api_card_id == "sv1-noimg")).first()
        assert card.image_url == "https://example.com/small.png"

    def test_returns_card_instance(self, session, sv1_set):
        result = upsert_card(session, _make_card_data(dex_numbers=[]))
        assert isinstance(result, Card)


# ---------------------------------------------------------------------------
# import_all_cards
# ---------------------------------------------------------------------------

class TestImportAllCards:
    def _make_response(self, cards: list[dict], total: int | None = None) -> dict:
        return {
            "data": cards,
            "page": 1,
            "pageSize": 250,
            "count": len(cards),
            "totalCount": total if total is not None else len(cards),
        }

    def test_imports_cards_into_database(self, session, sv1_set, bulbasaur_species):
        cards = [
            _make_card_data(card_id="sv1-1", dex_numbers=[1]),
            _make_card_data(card_id="sv1-2", dex_numbers=[2], number="002/198"),
        ]
        response = self._make_response(cards)

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_cards.return_value = response

        with (
            patch("app.services.importers.card_importer.PokemonTCGClient", return_value=mock_client),
            patch("app.services.importers.card_importer.get_session_context") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            import_all_cards()

        results = session.exec(select(Card)).all()
        assert len(results) == 2
        ids = {c.api_card_id for c in results}
        assert ids == {"sv1-1", "sv1-2"}

    def test_is_idempotent(self, session, sv1_set):
        response = self._make_response([_make_card_data(dex_numbers=[])])

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_cards.return_value = response

        with (
            patch("app.services.importers.card_importer.PokemonTCGClient", return_value=mock_client),
            patch("app.services.importers.card_importer.get_session_context") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: session
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            import_all_cards()
            import_all_cards()

        results = session.exec(select(Card)).all()
        assert len(results) == 1
