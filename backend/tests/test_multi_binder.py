"""Tests for the multi-binder system.

Covers binder CRUD, default handling, limits, validation, immutability,
profile isolation, POKEDEX pagination & representative-card behaviour,
FREE_PLACEMENT placements, concept-card derivation, ownership transitions,
layout reflow, and non-destructive removal semantics.

Uses the standard in-memory SQLite session pattern (SQLModel.metadata
.create_all on a bound connection), so the new binder tables are created
automatically. Migration seeding is covered separately in
``test_binder_migration.py``.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.main import app
from app.models.binder import Binder, BinderPlacement, BinderType
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.profile import Profile
from app.models.set import Set
from app.services import binder_service as svc


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


@pytest.fixture(name="profile")
def profile_fixture(session) -> Profile:
    """The active 'Default' profile (created by conftest ensure_default_profile)."""
    existing = session.exec(select(Profile).where(Profile.is_active == True)).first()  # noqa: E712
    assert existing is not None
    return existing


@pytest.fixture(name="species_set")
def species_set_fixture(session):
    """Create 30 species (dex 1-30)."""
    species = []
    for i in range(1, 31):
        s = PokemonSpecies(national_dex_number=i, name=f"species_{i}", generation=1)
        session.add(s)
        species.append(s)
    session.commit()
    for s in species:
        session.refresh(s)
    return species


@pytest.fixture(name="test_set")
def test_set_fixture(session) -> Set:
    s = Set(api_set_id="sv1", name="Scarlet & Violet", series="Scarlet & Violet")
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _make_card(session, species, test_set, suffix="a") -> Card:
    card = Card(
        api_card_id=f"sv1-{species.national_dex_number}{suffix}",
        pokemon_species_id=species.id,
        set_id=test_set.id,
        card_number=f"{species.national_dex_number:03d}/198",
        rarity="Common",
        image_url=f"https://img/{species.national_dex_number}{suffix}.png",
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def _own_card(session, profile, card, quantity=1, is_binder_card=False) -> Collection:
    entry = Collection(
        profile_id=profile.id,
        card_id=card.id,
        quantity=quantity,
        is_binder_card=is_binder_card,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def _make_free_binder(session, profile, name="Free", rows=3, columns=3) -> Binder:
    return svc.create_binder(
        session,
        profile.id,
        name=name,
        binder_type=BinderType.FREE_PLACEMENT.value,
        rows=rows,
        columns=columns,
    )


# ===========================================================================
# Profile / default-binder seeding
# ===========================================================================

class TestSeeding:
    def test_new_profile_gets_one_default_pokedex_binder(self, session):
        from app.services.profile_service import create_profile

        profile = create_profile(session, "Ash")
        binders = svc.list_binders(session, profile.id)
        assert len(binders) == 1
        assert binders[0].binder_type == BinderType.POKEDEX.value
        assert binders[0].is_default is True

    def test_new_profile_binder_copies_layout(self, session):
        from app.services.profile_service import create_profile

        profile = create_profile(session, "Misty")
        # Profile defaults: rows=5, columns=4, sort dex_number
        binder = svc.list_binders(session, profile.id)[0]
        assert binder.rows == profile.binder_rows
        assert binder.columns == profile.binder_columns
        assert binder.sort_order == profile.binder_sort

    def test_ensure_default_binder_creates_when_missing(self, session, profile):
        # conftest created the profile directly (no binder). Safety net creates one.
        assert svc.list_binders(session, profile.id) == []
        binder = svc.ensure_default_binder(session, profile.id)
        assert binder.is_default is True
        assert binder.binder_type == BinderType.POKEDEX.value
        assert len(svc.list_binders(session, profile.id)) == 1

    def test_list_binders_endpoint_autocreates_default(self, client):
        resp = client.get("/binders")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["binder_type"] == "POKEDEX"
        assert data[0]["is_default"] is True


# ===========================================================================
# Binder CRUD, limits, validation, immutability
# ===========================================================================

class TestBinderCrud:
    def test_create_binder(self, session, profile):
        svc.ensure_default_binder(session, profile.id)
        b = _make_free_binder(session, profile, name="Trades")
        assert b.id is not None
        assert b.binder_type == BinderType.FREE_PLACEMENT.value
        assert b.is_default is False  # default already exists

    def test_first_binder_becomes_default(self, session, profile):
        # No default yet — create_binder makes the first one default.
        b = svc.create_binder(
            session, profile.id, name="First", binder_type=BinderType.POKEDEX.value
        )
        assert b.is_default is True

    def test_min_one_binder_enforced(self, session, profile):
        svc.ensure_default_binder(session, profile.id)
        only = svc.list_binders(session, profile.id)[0]
        with pytest.raises(svc.BinderMinimumError):
            svc.delete_binder(session, only.id, profile.id)

    def test_delete_last_binder_returns_409(self, client):
        client.get("/binders")  # autocreate default
        binders = client.get("/binders").json()
        assert len(binders) == 1
        resp = client.delete(f"/binders/{binders[0]['id']}")
        assert resp.status_code == 409

    def test_deleting_default_promotes_oldest_remaining(self, session, profile):
        default = svc.ensure_default_binder(session, profile.id)  # oldest
        second = _make_free_binder(session, profile, name="Second")
        third = _make_free_binder(session, profile, name="Third")
        # Make third the default, then delete it — oldest remaining (default binder)
        svc.set_default_binder(session, third.id, profile.id)
        svc.delete_binder(session, third.id, profile.id)
        remaining = svc.list_binders(session, profile.id)
        defaults = [b for b in remaining if b.is_default]
        assert len(defaults) == 1
        # Oldest remaining is the original default binder.
        assert defaults[0].id == default.id

    def test_max_binders_enforced(self, session, profile, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "max_binders_per_profile", 3)
        svc.create_binder(session, profile.id, name="b1", binder_type=BinderType.FREE_PLACEMENT.value)
        svc.create_binder(session, profile.id, name="b2", binder_type=BinderType.FREE_PLACEMENT.value)
        svc.create_binder(session, profile.id, name="b3", binder_type=BinderType.FREE_PLACEMENT.value)
        with pytest.raises(svc.BinderLimitError):
            svc.create_binder(session, profile.id, name="b4", binder_type=BinderType.FREE_PLACEMENT.value)

    def test_max_binders_endpoint_returns_409(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "max_binders_per_profile", 1)
        client.get("/binders")  # autocreate default (count now 1)
        resp = client.post(
            "/binders",
            json={"name": "Extra", "binder_type": "FREE_PLACEMENT"},
        )
        assert resp.status_code == 409

    def test_name_validation_empty(self, session, profile):
        with pytest.raises(svc.BinderValidationError):
            svc.create_binder(session, profile.id, name="   ", binder_type=BinderType.POKEDEX.value)

    def test_name_validation_too_long(self, session, profile):
        with pytest.raises(svc.BinderValidationError):
            svc.create_binder(
                session, profile.id, name="x" * 101, binder_type=BinderType.POKEDEX.value
            )

    def test_layout_validation_bounds(self, session, profile):
        with pytest.raises(svc.BinderValidationError):
            svc.create_binder(
                session, profile.id, name="Bad", binder_type=BinderType.POKEDEX.value, rows=1
            )
        with pytest.raises(svc.BinderValidationError):
            svc.create_binder(
                session, profile.id, name="Bad", binder_type=BinderType.POKEDEX.value, columns=6
            )

    def test_valid_layouts_accepted(self, session, profile):
        for rows in range(2, 6):
            for cols in range(2, 6):
                b = svc.create_binder(
                    session,
                    profile.id,
                    name=f"{rows}x{cols}",
                    binder_type=BinderType.POKEDEX.value,
                    rows=rows,
                    columns=cols,
                )
                assert b.rows == rows and b.columns == cols
                session.delete(b)
                session.commit()

    def test_invalid_sort_rejected(self, session, profile):
        with pytest.raises(svc.BinderValidationError):
            svc.create_binder(
                session,
                profile.id,
                name="Bad",
                binder_type=BinderType.POKEDEX.value,
                sort_order="nonsense",
            )

    def test_invalid_type_rejected(self, session, profile):
        with pytest.raises(svc.BinderValidationError):
            svc.create_binder(session, profile.id, name="Bad", binder_type="WEIRD")

    def test_binder_type_immutable(self, session, profile):
        b = _make_free_binder(session, profile)
        with pytest.raises(svc.BinderValidationError):
            svc.update_binder(
                session, b.id, profile.id, binder_type=BinderType.POKEDEX.value
            )
        # Passing same type is a no-op.
        svc.update_binder(
            session, b.id, profile.id, binder_type=BinderType.FREE_PLACEMENT.value, name="Renamed"
        )
        session.refresh(b)
        assert b.name == "Renamed"

    def test_rename_and_relayout(self, session, profile):
        b = _make_free_binder(session, profile, rows=2, columns=2)
        svc.update_binder(session, b.id, profile.id, name="New", rows=4, columns=4)
        session.refresh(b)
        assert b.name == "New" and b.rows == 4 and b.columns == 4

    # ------------------------------------------------------------------
    # Single POKEDEX binder per profile
    # ------------------------------------------------------------------

    def test_only_one_pokedex_binder_allowed(self, session, profile):
        svc.create_binder(
            session, profile.id, name="Dex", binder_type=BinderType.POKEDEX.value
        )
        with pytest.raises(svc.BinderValidationError):
            svc.create_binder(
                session, profile.id, name="Dex 2", binder_type=BinderType.POKEDEX.value
            )

    def test_second_pokedex_binder_endpoint_returns_400(self, client):
        # Autocreate the default POKEDEX binder.
        client.get("/binders")
        resp = client.post("/binders", json={"name": "Dex 2", "binder_type": "POKEDEX"})
        assert resp.status_code == 400
        assert "one Pokédex binder" in resp.json()["detail"]

    def test_free_placement_still_allowed_alongside_pokedex(self, session, profile):
        svc.ensure_default_binder(session, profile.id)  # POKEDEX default
        b = _make_free_binder(session, profile, name="Trades")
        assert b.binder_type == BinderType.FREE_PLACEMENT.value
        # A second free-placement binder is also fine.
        b2 = _make_free_binder(session, profile, name="Master")
        assert b2.id is not None

    def test_single_pokedex_rule_coexists_with_max_limit(self, session, profile, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "max_binders_per_profile", 4)
        svc.create_binder(session, profile.id, name="Dex", binder_type=BinderType.POKEDEX.value)
        # Fill up to the limit with free-placement binders.
        svc.create_binder(session, profile.id, name="f1", binder_type=BinderType.FREE_PLACEMENT.value)
        svc.create_binder(session, profile.id, name="f2", binder_type=BinderType.FREE_PLACEMENT.value)
        svc.create_binder(session, profile.id, name="f3", binder_type=BinderType.FREE_PLACEMENT.value)
        with pytest.raises(svc.BinderLimitError):
            svc.create_binder(session, profile.id, name="f4", binder_type=BinderType.FREE_PLACEMENT.value)


# ===========================================================================
# Profile isolation
# ===========================================================================

class TestProfileIsolation:
    def _second_profile(self, session) -> Profile:
        p = Profile(name="Second", is_active=False)
        session.add(p)
        session.commit()
        session.refresh(p)
        return p

    def test_cannot_access_other_profiles_binder(self, session, profile):
        other = self._second_profile(session)
        other_binder = svc.create_binder(
            session, other.id, name="Theirs", binder_type=BinderType.POKEDEX.value
        )
        with pytest.raises(svc.BinderNotFoundError):
            svc.get_binder_for_profile(session, other_binder.id, profile.id)

    def test_cannot_delete_other_profiles_binder(self, session, profile):
        other = self._second_profile(session)
        svc.ensure_default_binder(session, profile.id)
        other_binder = svc.create_binder(
            session, other.id, name="Theirs", binder_type=BinderType.POKEDEX.value
        )
        with pytest.raises(svc.BinderNotFoundError):
            svc.delete_binder(session, other_binder.id, profile.id)

    def test_cannot_place_in_other_profiles_binder(self, session, profile, species_set, test_set):
        other = self._second_profile(session)
        other_binder = svc.create_binder(
            session, other.id, name="Theirs", binder_type=BinderType.FREE_PLACEMENT.value
        )
        card = _make_card(session, species_set[0], test_set)
        with pytest.raises(svc.BinderNotFoundError):
            svc.add_placement(
                session, other_binder.id, profile.id, card_id=card.id, page=1, slot=0
            )

    def test_page_endpoint_isolation_returns_404(self, client, session, profile):
        other = self._second_profile(session)
        other_binder = svc.create_binder(
            session, other.id, name="Theirs", binder_type=BinderType.POKEDEX.value
        )
        resp = client.get(f"/binders/{other_binder.id}/page")
        assert resp.status_code == 404


# ===========================================================================
# POKEDEX behaviour
# ===========================================================================

class TestPokedexBinder:
    def test_pagination_total_pages(self, session, profile):
        binder = svc.create_binder(
            session, profile.id, name="Dex", binder_type=BinderType.POKEDEX.value,
            rows=5, columns=4,
        )
        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        # 1025 / 20 = 52 (ceil 51.25)
        assert page["total_pages"] == 52
        assert page["total_species"] == 1025
        assert page["slots"][0]["dex_number"] == 1

    def test_representative_card_behaviour(self, session, profile, species_set, test_set):
        binder = svc.create_binder(
            session, profile.id, name="Dex", binder_type=BinderType.POKEDEX.value,
            rows=5, columns=4,
        )
        sp = species_set[0]  # dex 1
        card_a = _make_card(session, sp, test_set, suffix="a")
        card_b = _make_card(session, sp, test_set, suffix="b")
        _own_card(session, profile, card_a, is_binder_card=False)
        _own_card(session, profile, card_b, is_binder_card=True)  # representative

        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        slot = next(s for s in page["slots"] if s["dex_number"] == 1)
        assert slot["owned"] is True
        assert slot["has_card"] is True
        assert slot["card"]["id"] == card_b.id  # is_binder_card wins
        assert slot["total_cards"] == 2

    def test_unowned_species_shows_empty_no_concept(self, session, profile, species_set):
        binder = svc.create_binder(
            session, profile.id, name="Dex", binder_type=BinderType.POKEDEX.value,
            rows=5, columns=4,
        )
        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        slot = next(s for s in page["slots"] if s["dex_number"] == 2)
        # Not owned: empty/unowned state, never a concept card.
        assert slot["owned"] is False
        assert slot["has_card"] is False
        assert slot["card"] is None

    def test_pokedex_page_endpoint_shape(self, client, session, profile):
        binder = svc.create_binder(
            session, profile.id, name="Dex", binder_type=BinderType.POKEDEX.value
        )
        resp = client.get(f"/binders/{binder.id}/page?page=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["binder_type"] == "POKEDEX"
        assert "total_species" in data


# ===========================================================================
# FREE_PLACEMENT behaviour: placements, concept, transitions, reflow
# ===========================================================================

class TestFreePlacement:
    def test_add_owned_card(self, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)
        _own_card(session, profile, card)
        placement = svc.add_placement(
            session, binder.id, profile.id, card_id=card.id, page=1, slot=0
        )
        assert placement.id is not None
        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        slot = page["slots"][0]
        assert slot["card"]["card_id"] == card.id
        assert slot["is_concept"] is False

    def test_add_unowned_card_is_concept(self, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)  # not owned
        svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=1, slot=0)
        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        slot = page["slots"][0]
        assert slot["card"]["card_id"] == card.id
        assert slot["is_concept"] is True

    def test_concept_becomes_owned_without_changing_placement(
        self, session, profile, species_set, test_set
    ):
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)
        placement = svc.add_placement(
            session, binder.id, profile.id, card_id=card.id, page=1, slot=2
        )
        # Initially concept
        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        assert page["slots"][2]["is_concept"] is True

        # Acquire the card
        _own_card(session, profile, card)
        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        assert page["slots"][2]["is_concept"] is False
        assert page["slots"][2]["placement_id"] == placement.id  # placement unchanged
        assert page["slots"][2]["card"]["card_id"] == card.id

    def test_losing_ownership_reverts_to_concept_without_deleting_placement(
        self, session, profile, species_set, test_set
    ):
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)
        entry = _own_card(session, profile, card)
        placement = svc.add_placement(
            session, binder.id, profile.id, card_id=card.id, page=1, slot=0
        )
        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        assert page["slots"][0]["is_concept"] is False

        # Remove from collection
        session.delete(entry)
        session.commit()

        page = svc.get_binder_page_for(session, binder, profile_id=profile.id, page=1)
        assert page["slots"][0]["is_concept"] is True
        # Placement still exists
        assert session.get(BinderPlacement, placement.id) is not None

    def test_same_card_in_multiple_binders(self, session, profile, species_set, test_set):
        b1 = _make_free_binder(session, profile, name="B1")
        b2 = _make_free_binder(session, profile, name="B2")
        card = _make_card(session, species_set[0], test_set)
        svc.add_placement(session, b1.id, profile.id, card_id=card.id, page=1, slot=0)
        # Same card can go in a different binder.
        p2 = svc.add_placement(session, b2.id, profile.id, card_id=card.id, page=1, slot=0)
        assert p2.id is not None

    def test_same_card_twice_in_one_binder_rejected(
        self, session, profile, species_set, test_set
    ):
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)
        svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=1, slot=0)
        with pytest.raises(svc.PlacementConflictError):
            svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=1, slot=1)

    def test_occupied_slot_rejected(self, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile)
        c1 = _make_card(session, species_set[0], test_set)
        c2 = _make_card(session, species_set[1], test_set)
        svc.add_placement(session, binder.id, profile.id, card_id=c1.id, page=1, slot=0)
        with pytest.raises(svc.PlacementConflictError):
            svc.add_placement(session, binder.id, profile.id, card_id=c2.id, page=1, slot=0)

    def test_occupied_slot_endpoint_returns_409(self, client, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile)
        c1 = _make_card(session, species_set[0], test_set)
        c2 = _make_card(session, species_set[1], test_set)
        client.post(
            f"/binders/{binder.id}/placements",
            json={"card_id": c1.id, "page": 1, "slot": 0},
        )
        resp = client.post(
            f"/binders/{binder.id}/placements",
            json={"card_id": c2.id, "page": 1, "slot": 0},
        )
        assert resp.status_code == 409

    def test_move_placement_to_empty_slot(self, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)
        p = svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=1, slot=0)
        moved = svc.move_placement(session, binder.id, profile.id, p.id, page=1, slot=5)
        assert moved.slot == 5

    def test_move_onto_occupied_slot_rejected(self, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile)
        c1 = _make_card(session, species_set[0], test_set)
        c2 = _make_card(session, species_set[1], test_set)
        p1 = svc.add_placement(session, binder.id, profile.id, card_id=c1.id, page=1, slot=0)
        svc.add_placement(session, binder.id, profile.id, card_id=c2.id, page=1, slot=1)
        with pytest.raises(svc.PlacementConflictError):
            svc.move_placement(session, binder.id, profile.id, p1.id, page=1, slot=1)

    def test_move_to_same_slot_is_noop(self, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)
        p = svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=1, slot=3)
        moved = svc.move_placement(session, binder.id, profile.id, p.id, page=1, slot=3)
        assert moved.slot == 3

    def test_remove_placement_does_not_touch_collection(
        self, session, profile, species_set, test_set
    ):
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)
        entry = _own_card(session, profile, card)
        p = svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=1, slot=0)
        svc.remove_placement(session, binder.id, profile.id, p.id)
        assert session.get(BinderPlacement, p.id) is None
        # Collection entry intact
        assert session.get(Collection, entry.id) is not None

    def test_delete_binder_does_not_touch_collection(
        self, session, profile, species_set, test_set
    ):
        svc.ensure_default_binder(session, profile.id)
        binder = _make_free_binder(session, profile)
        card = _make_card(session, species_set[0], test_set)
        entry = _own_card(session, profile, card)
        p = svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=1, slot=0)
        svc.delete_binder(session, binder.id, profile.id)
        # Placement cascade-deleted, collection preserved.
        assert session.get(BinderPlacement, p.id) is None
        assert session.get(Collection, entry.id) is not None

    def test_invalid_page_slot_rejected(self, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile, rows=2, columns=2)  # capacity 4
        card = _make_card(session, species_set[0], test_set)
        with pytest.raises(svc.PlacementValidationError):
            svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=1, slot=4)
        with pytest.raises(svc.PlacementValidationError):
            svc.add_placement(session, binder.id, profile.id, card_id=card.id, page=0, slot=0)

    def test_add_nonexistent_card_rejected(self, session, profile):
        binder = _make_free_binder(session, profile)
        with pytest.raises(svc.PlacementValidationError):
            svc.add_placement(session, binder.id, profile.id, card_id=99999, page=1, slot=0)

    def test_placement_only_on_free_placement(self, session, profile, species_set, test_set):
        pokedex = svc.create_binder(
            session, profile.id, name="Dex", binder_type=BinderType.POKEDEX.value
        )
        card = _make_card(session, species_set[0], test_set)
        with pytest.raises(svc.PlacementValidationError):
            svc.add_placement(session, pokedex.id, profile.id, card_id=card.id, page=1, slot=0)


# ===========================================================================
# Reflow
# ===========================================================================

class TestReflow:
    def _cards(self, session, species_set, test_set, n):
        return [_make_card(session, species_set[i], test_set) for i in range(n)]

    def test_shrink_compacts_cards(self, session, profile, species_set, test_set):
        # 3x3 = 9 capacity; place cards on page 1 slots 0,4,8 and page 2 slot 0.
        binder = _make_free_binder(session, profile, rows=3, columns=3)
        cards = self._cards(session, species_set, test_set, 4)
        svc.add_placement(session, binder.id, profile.id, card_id=cards[0].id, page=1, slot=0)
        svc.add_placement(session, binder.id, profile.id, card_id=cards[1].id, page=1, slot=4)
        svc.add_placement(session, binder.id, profile.id, card_id=cards[2].id, page=1, slot=8)
        svc.add_placement(session, binder.id, profile.id, card_id=cards[3].id, page=2, slot=0)

        # Shrink to 2x2 = 4 capacity.
        svc.update_binder(session, binder.id, profile.id, rows=2, columns=2)

        placements = list(
            session.exec(
                select(BinderPlacement)
                .where(BinderPlacement.binder_id == binder.id)
                .order_by(BinderPlacement.page, BinderPlacement.slot)
            ).all()
        )
        # 4 placements preserved, densely packed into new capacity.
        assert len(placements) == 4
        # Linear order preserved: cards[0], cards[1], cards[2], cards[3]
        ordered_card_ids = [p.card_id for p in placements]
        assert ordered_card_ids == [c.id for c in cards]
        # Dense packing into 2x2: positions (1,0),(1,1),(1,2),(1,3)
        assert [(p.page, p.slot) for p in placements] == [(1, 0), (1, 1), (1, 2), (1, 3)]

    def test_grow_packs_densely(self, session, profile, species_set, test_set):
        # 2x2 = 4 capacity; fill page1 slots 0..3 and page2 slot0.
        binder = _make_free_binder(session, profile, rows=2, columns=2)
        cards = self._cards(session, species_set, test_set, 5)
        for i in range(4):
            svc.add_placement(session, binder.id, profile.id, card_id=cards[i].id, page=1, slot=i)
        svc.add_placement(session, binder.id, profile.id, card_id=cards[4].id, page=2, slot=0)

        # Grow to 3x3 = 9 capacity.
        svc.update_binder(session, binder.id, profile.id, rows=3, columns=3)

        placements = list(
            session.exec(
                select(BinderPlacement)
                .where(BinderPlacement.binder_id == binder.id)
                .order_by(BinderPlacement.page, BinderPlacement.slot)
            ).all()
        )
        assert len(placements) == 5
        # All 5 now fit on page 1 slots 0..4 in original order.
        assert [(p.page, p.slot) for p in placements] == [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)]
        assert [p.card_id for p in placements] == [c.id for c in cards]

    def test_reflow_preserves_all_cards(self, session, profile, species_set, test_set):
        binder = _make_free_binder(session, profile, rows=3, columns=3)
        cards = self._cards(session, species_set, test_set, 7)
        for i, c in enumerate(cards):
            page = i // 9 + 1
            slot = i % 9
            svc.add_placement(session, binder.id, profile.id, card_id=c.id, page=page, slot=slot)
        before = {
            p.card_id
            for p in session.exec(
                select(BinderPlacement).where(BinderPlacement.binder_id == binder.id)
            ).all()
        }
        svc.update_binder(session, binder.id, profile.id, rows=2, columns=2)
        after = {
            p.card_id
            for p in session.exec(
                select(BinderPlacement).where(BinderPlacement.binder_id == binder.id)
            ).all()
        }
        assert before == after


# ===========================================================================
# Compatibility routes (legacy /binder) still operate on default POKEDEX
# ===========================================================================

class TestCompatibility:
    def test_legacy_binder_page_still_works(self, client, session, profile, species_set):
        # Autocreate default binder via /binders, then hit legacy route.
        client.get("/binders")
        resp = client.get("/binder/page?page_size=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_species"] == 1025
        assert data["slots"][0]["dex_number"] == 1

    def test_legacy_binder_page_without_binder_falls_back(self, client, species_set):
        # No /binders call — legacy route uses profile.binder_* fallback.
        resp = client.get("/binder/page?page_size=20")
        assert resp.status_code == 200
        assert resp.json()["total_species"] == 1025
