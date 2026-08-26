"""Tests for binder, cascade removal, and import merge functionality."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.main import app
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.profile import Profile
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


@pytest.fixture(name="profile")
def profile_fixture(session):
    """Ensure the active profile is ours (conftest creates 'Default' first)."""
    from sqlmodel import select as _sel
    existing = session.exec(_sel(Profile).where(Profile.is_active == True)).first()  # noqa: E712
    if existing:
        return existing
    p = Profile(name="Test", is_active=True, binder_rows=5, binder_columns=4)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@pytest.fixture(name="species_set")
def species_set_fixture(session):
    """Create 30 species (dex 1-30) for binder tests."""
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
def test_set_fixture(session):
    s = Set(api_set_id="sv1", name="Scarlet & Violet", series="Scarlet & Violet")
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _make_card(session, species, test_set, card_id_suffix="a"):
    card = Card(
        api_card_id=f"sv1-{species.national_dex_number}{card_id_suffix}",
        pokemon_species_id=species.id,
        set_id=test_set.id,
        card_number=f"{species.national_dex_number:03d}/198",
        rarity="Common",
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


# ===========================================================================
# BINDER TESTS
# ===========================================================================

class TestBinderPageCalculations:
    def test_5x4_produces_52_pages(self, client, session, profile, species_set):
        """5x4 = 20 per page, 1025/20 = ceil(52.25) = 53, but with 30 species total pages are from total_species=1025."""
        # The service always uses 1025 regardless of how many species exist
        resp = client.get("/binder/page?page_size=20")
        assert resp.status_code == 200
        assert resp.json()["total_pages"] == 52
        assert resp.json()["total_species"] == 1025

    def test_2x2_produces_257_pages(self, client, session, profile, species_set):
        resp = client.get("/binder/page?page_size=4")
        assert resp.status_code == 200
        assert resp.json()["total_pages"] == 257

    def test_5x5_produces_41_pages(self, client, session, profile, species_set):
        resp = client.get("/binder/page?page_size=25")
        assert resp.status_code == 200
        assert resp.json()["total_pages"] == 41

    def test_page_1_starts_at_dex_1(self, client, session, profile, species_set):
        resp = client.get("/binder/page?page_size=20")
        data = resp.json()
        assert data["slots"][0]["dex_number"] == 1

    def test_page_2_starts_at_correct_dex(self, client, session, profile, species_set):
        resp = client.get("/binder/page?page=2&page_size=20")
        data = resp.json()
        assert data["slots"][0]["dex_number"] == 21

    def test_page_returns_correct_number_of_slots(self, client, session, profile, species_set):
        resp = client.get("/binder/page?page_size=20")
        data = resp.json()
        assert len(data["slots"]) == 20


class TestBinderOwnership:
    def test_missing_species_shows_empty_slot(self, client, session, profile, species_set, test_set):
        """Species with no collection entry should have owned=false."""
        resp = client.get("/binder/page?page_size=20")
        data = resp.json()
        slot_1 = data["slots"][0]
        assert slot_1["dex_number"] == 1
        assert slot_1["owned"] is False
        assert slot_1["card"] is None

    def test_owning_dex_2_shows_slot_1_empty_slot_2_filled(self, client, session, profile, species_set, test_set):
        """Owning only #2 means slot #1 empty, slot #2 has card."""
        species_2 = species_set[1]  # dex #2
        card = _make_card(session, species_2, test_set)
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=1))
        session.commit()

        resp = client.get("/binder/page?page_size=20")
        data = resp.json()

        assert data["slots"][0]["dex_number"] == 1
        assert data["slots"][0]["owned"] is False
        assert data["slots"][1]["dex_number"] == 2
        assert data["slots"][1]["owned"] is True
        assert data["slots"][1]["card"] is not None
        assert data["slots"][1]["card"]["image_url"] is None  # no image in test data

    def test_card_ownership_counts_as_species_owned(self, client, session, profile, species_set, test_set):
        """Adding a card for a species makes that dex slot owned."""
        species_5 = species_set[4]  # dex #5
        card = _make_card(session, species_5, test_set)
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=2))
        session.commit()

        resp = client.get("/binder/page?page_size=20")
        data = resp.json()
        slot_5 = data["slots"][4]

        assert slot_5["dex_number"] == 5
        assert slot_5["owned"] is True
        assert slot_5["total_cards"] == 2

    def test_multiple_cards_same_species_one_slot(self, client, session, profile, species_set, test_set):
        """Multiple cards for one species still produce one binder slot."""
        species_3 = species_set[2]
        card_a = _make_card(session, species_3, test_set, "a")
        card_b = _make_card(session, species_3, test_set, "b")
        session.add(Collection(profile_id=profile.id, card_id=card_a.id, quantity=2))
        session.add(Collection(profile_id=profile.id, card_id=card_b.id, quantity=3))
        session.commit()

        resp = client.get("/binder/page?page_size=20")
        data = resp.json()
        slot_3 = data["slots"][2]

        assert slot_3["dex_number"] == 3
        assert slot_3["owned"] is True
        assert slot_3["total_cards"] == 5  # 2 + 3
        assert slot_3["card"] is not None

    def test_final_page_has_padding_slots(self, client, session, profile, species_set):
        """Last page has remaining species + None-padded empty pockets."""
        resp = client.get("/binder/page?page=52&page_size=20")
        data = resp.json()
        assert len(data["slots"]) == 20
        # Only 5 real species on last page (1021-1025), rest are padding
        real = [s for s in data["slots"] if s["dex_number"] is not None]
        padding = [s for s in data["slots"] if s["dex_number"] is None]
        assert len(real) == 5
        assert len(padding) == 15


# ===========================================================================
# CASCADE REMOVAL TESTS
# ===========================================================================

class TestCascadeRemoval:
    def test_remove_species_with_no_cards(self, client, session, profile, species_set):
        """Remove a species-level entry (no cards)."""
        sp = species_set[0]
        session.add(Collection(profile_id=profile.id, pokemon_species_id=sp.id, quantity=1))
        session.commit()

        resp = client.delete(f"/collection/species/{sp.id}/cascade")
        assert resp.status_code == 200
        data = resp.json()
        assert data["removed_species"] is True
        assert data["removed_cards"] == 0

    def test_remove_species_with_card_entries(self, client, session, profile, species_set, test_set):
        """Remove species + all card entries."""
        sp = species_set[0]
        card_a = _make_card(session, sp, test_set, "a")
        card_b = _make_card(session, sp, test_set, "b")
        session.add(Collection(profile_id=profile.id, pokemon_species_id=sp.id, quantity=1))
        session.add(Collection(profile_id=profile.id, card_id=card_a.id, quantity=2))
        session.add(Collection(profile_id=profile.id, card_id=card_b.id, quantity=1))
        session.commit()

        resp = client.delete(f"/collection/species/{sp.id}/cascade")
        assert resp.status_code == 200
        data = resp.json()
        assert data["removed_species"] is True
        assert data["removed_cards"] == 2

        # Verify collection is empty for this species
        remaining = session.exec(
            select(Collection).where(Collection.profile_id == profile.id)
        ).all()
        assert len(remaining) == 0

    def test_cascade_removal_scoped_to_active_profile(self, client, session, profile, species_set, test_set):
        """Removing from profile 1 doesn't affect profile 2."""
        sp = species_set[0]
        card = _make_card(session, sp, test_set)

        # Profile 2
        p2 = Profile(name="Other", is_active=False)
        session.add(p2)
        session.commit()
        session.refresh(p2)

        # Both profiles own the same card
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=1))
        session.add(Collection(profile_id=p2.id, card_id=card.id, quantity=3))
        session.commit()

        resp = client.delete(f"/collection/species/{sp.id}/cascade")
        assert resp.status_code == 200

        # Profile 2's entry should still exist
        p2_entries = session.exec(
            select(Collection).where(Collection.profile_id == p2.id)
        ).all()
        assert len(p2_entries) == 1
        assert p2_entries[0].quantity == 3

    def test_cascade_404_when_nothing_to_remove(self, client, session, profile, species_set):
        """Returns 404 if no collection entries exist for the species."""
        sp = species_set[0]
        resp = client.delete(f"/collection/species/{sp.id}/cascade")
        assert resp.status_code == 404


# ===========================================================================
# IMPORT MERGE TESTS
# ===========================================================================

class TestImportReplace:
    """Tests for 'Import & Replace' mode — file becomes the collection state."""

    def _export_data(self, collection_entries):
        return {
            "format_version": 1,
            "exported_at": "2026-08-20T00:00:00Z",
            "app_version": "0.3.0",
            "profile": {"name": "Test", "binder_rows": 5, "binder_columns": 4, "binder_sort": "dex_number"},
            "collection": collection_entries,
        }

    def test_replace_new_card(self, client, session, profile, species_set, test_set):
        """Importing a new card creates it with the file's quantity."""
        card = _make_card(session, species_set[0], test_set)

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 3}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "replace"})
        assert resp.status_code == 200
        result = resp.json()
        assert result["imported_cards"] == 1

        entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id, Collection.card_id == card.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].quantity == 3

    def test_replace_higher_quantity(self, client, session, profile, species_set, test_set):
        """Replace with file qty=5 when current is qty=2 results in qty=5."""
        card = _make_card(session, species_set[0], test_set)
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=2))
        session.commit()

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 5}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "replace"})
        assert resp.status_code == 200

        entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id, Collection.card_id == card.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].quantity == 5

    def test_replace_lower_quantity(self, client, session, profile, species_set, test_set):
        """Replace with file qty=1 when current is qty=4 results in qty=1."""
        card = _make_card(session, species_set[0], test_set)
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=4))
        session.commit()

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 1}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "replace"})
        assert resp.status_code == 200

        entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id, Collection.card_id == card.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].quantity == 1

    def test_replace_same_file_twice_is_idempotent(self, client, session, profile, species_set, test_set):
        """Importing the same file twice produces identical collection state."""
        card = _make_card(session, species_set[0], test_set)

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 3}
        ])

        client.post("/data/import", json={"data": data, "mode": "replace"})
        client.post("/data/import", json={"data": data, "mode": "replace"})

        entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].quantity == 3

    def test_replace_removes_cards_not_in_file(self, client, session, profile, species_set, test_set):
        """Cards in the current collection but NOT in the file are removed."""
        card_a = _make_card(session, species_set[0], test_set, "a")
        card_b = _make_card(session, species_set[1], test_set, "b")
        session.add(Collection(profile_id=profile.id, card_id=card_a.id, quantity=2))
        session.add(Collection(profile_id=profile.id, card_id=card_b.id, quantity=1))
        session.commit()

        # Import file only contains card_a
        data = self._export_data([
            {"type": "card", "api_card_id": card_a.api_card_id, "quantity": 3}
        ])
        client.post("/data/import", json={"data": data, "mode": "replace"})

        entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].card_id == card_a.id
        assert entries[0].quantity == 3

    def test_replace_creates_backup(self, client, session, profile, species_set, test_set):
        """Replace mode reports has_backup=True."""
        card = _make_card(session, species_set[0], test_set)
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=2))
        session.commit()

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 3}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "replace"})
        assert resp.json()["has_backup"] is True

    def test_replace_invalid_card_is_skipped(self, client, session, profile, species_set, test_set):
        """Invalid card references are skipped with a warning."""
        data = self._export_data([
            {"type": "card", "api_card_id": "nonexistent-card-xyz", "quantity": 1}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "replace"})
        assert resp.status_code == 200
        result = resp.json()
        assert result["skipped_cards"] == 1
        assert len(result["warnings"]) == 1


class TestImportMerge:
    """Tests for 'Import & Merge' mode — additive quantities."""

    def _export_data(self, collection_entries):
        return {
            "format_version": 1,
            "exported_at": "2026-08-20T00:00:00Z",
            "app_version": "0.3.0",
            "profile": {"name": "Test", "binder_rows": 5, "binder_columns": 4, "binder_sort": "dex_number"},
            "collection": collection_entries,
        }

    def test_merge_new_card(self, client, session, profile, species_set, test_set):
        """Merging a new card creates it with the file's quantity."""
        card = _make_card(session, species_set[0], test_set)

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 3}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "merge"})
        assert resp.status_code == 200
        assert resp.json()["imported_cards"] == 1

        entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id, Collection.card_id == card.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].quantity == 3

    def test_merge_overlapping_cards_adds_quantities(self, client, session, profile, species_set, test_set):
        """Merging an existing card adds quantities together."""
        card = _make_card(session, species_set[0], test_set)
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=2))
        session.commit()

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 3}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "merge"})
        assert resp.status_code == 200
        assert resp.json()["imported_cards"] == 1

        entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id, Collection.card_id == card.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].quantity == 5  # 2 + 3

    def test_merge_maintains_single_row_per_card(self, client, session, profile, species_set, test_set):
        """Merge never creates duplicate rows for the same card."""
        card = _make_card(session, species_set[0], test_set)
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=1))
        session.commit()

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 2}
        ])

        # Merge multiple times
        client.post("/data/import", json={"data": data, "mode": "merge"})
        client.post("/data/import", json={"data": data, "mode": "merge"})

        entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id, Collection.card_id == card.id)
        ).all()
        assert len(entries) == 1
        assert entries[0].quantity == 5  # 1 + 2 + 2

    def test_merge_existing_species_not_duplicated(self, client, session, profile, species_set):
        """Merging an existing species entry skips it — no duplicates."""
        sp = species_set[0]
        session.add(Collection(profile_id=profile.id, pokemon_species_id=sp.id, quantity=1))
        session.commit()

        data = self._export_data([
            {"type": "species", "national_dex_number": sp.national_dex_number, "species_name": sp.name}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "merge"})
        assert resp.status_code == 200
        assert resp.json()["skipped_species"] == 1

        entries = session.exec(
            select(Collection).where(
                Collection.profile_id == profile.id,
                Collection.pokemon_species_id == sp.id,
                Collection.card_id.is_(None),
            )
        ).all()
        assert len(entries) == 1

    def test_merge_preserves_existing_cards_not_in_file(self, client, session, profile, species_set, test_set):
        """Cards in the current collection but NOT in the file remain unchanged."""
        card_a = _make_card(session, species_set[0], test_set, "a")
        card_b = _make_card(session, species_set[1], test_set, "b")
        session.add(Collection(profile_id=profile.id, card_id=card_a.id, quantity=2))
        session.commit()

        # Import file only contains card_b
        data = self._export_data([
            {"type": "card", "api_card_id": card_b.api_card_id, "quantity": 4}
        ])
        client.post("/data/import", json={"data": data, "mode": "merge"})

        all_entries = session.exec(
            select(Collection).where(Collection.profile_id == profile.id)
        ).all()
        assert len(all_entries) == 2
        # card_a unchanged
        a_entry = next(e for e in all_entries if e.card_id == card_a.id)
        assert a_entry.quantity == 2
        # card_b added
        b_entry = next(e for e in all_entries if e.card_id == card_b.id)
        assert b_entry.quantity == 4

    def test_import_as_new_profile_isolates_data(self, client, session, profile, species_set, test_set):
        """Importing as new profile doesn't affect existing profile."""
        card = _make_card(session, species_set[0], test_set)
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=2))
        session.commit()

        data = self._export_data([
            {"type": "card", "api_card_id": card.api_card_id, "quantity": 5}
        ])
        resp = client.post("/data/import", json={"data": data, "mode": "new_profile"})
        assert resp.status_code == 200

        # Original profile unchanged
        orig = session.exec(
            select(Collection).where(Collection.profile_id == profile.id, Collection.card_id == card.id)
        ).all()
        assert len(orig) == 1
        assert orig[0].quantity == 2

        # New profile exists with its own data
        new_profiles = session.exec(select(Profile).where(Profile.id != profile.id)).all()
        assert len(new_profiles) == 1
        new_entries = session.exec(
            select(Collection).where(Collection.profile_id == new_profiles[0].id)
        ).all()
        assert len(new_entries) == 1
        assert new_entries[0].quantity == 5


# ===========================================================================
# BINDER CARD SELECTION TESTS
# ===========================================================================

class TestBinderCardSelection:
    def test_species_only_ownership_shows_no_card(self, client, session, profile, species_set):
        """Species-level ownership: owned=True, has_card=False, card=None."""
        sp = species_set[0]
        session.add(Collection(profile_id=profile.id, pokemon_species_id=sp.id, quantity=1))
        session.commit()

        resp = client.get("/binder/page?page_size=20")
        slot = resp.json()["slots"][0]
        assert slot["owned"] is True
        assert slot["has_card"] is False
        assert slot["card"] is None

    def test_one_owned_card_auto_becomes_binder_card(self, client, session, profile, species_set, test_set):
        """Adding one card automatically selects it as the binder card."""
        sp = species_set[0]
        card = _make_card(session, sp, test_set)

        # Add via API to trigger auto-selection
        resp = client.post("/collection/cards", json={"card_id": card.id, "quantity": 1})
        assert resp.status_code == 201
        assert resp.json()["is_binder_card"] is True

        # Binder should show the card
        binder = client.get("/binder/page?page_size=20")
        slot = binder.json()["slots"][0]
        assert slot["owned"] is True
        assert slot["has_card"] is True
        assert slot["card"]["id"] == card.id

    def test_selecting_card_b_deselects_card_a(self, client, session, profile, species_set, test_set):
        """Selecting a new binder card deselects the previous one."""
        sp = species_set[0]
        card_a = _make_card(session, sp, test_set, "a")
        card_b = _make_card(session, sp, test_set, "b")

        # Add both cards
        resp_a = client.post("/collection/cards", json={"card_id": card_a.id, "quantity": 1})
        entry_a_id = resp_a.json()["id"]
        resp_b = client.post("/collection/cards", json={"card_id": card_b.id, "quantity": 1})
        entry_b_id = resp_b.json()["id"]

        # Select card B
        resp = client.put(f"/binder/card/{entry_b_id}")
        assert resp.status_code == 200

        # Verify card A is no longer binder card
        entries = client.get(f"/collection/species/{sp.id}/cards").json()
        a_entry = next(e for e in entries if e["card_id"] == card_a.id)
        b_entry = next(e for e in entries if e["card_id"] == card_b.id)
        assert a_entry["is_binder_card"] is False
        assert b_entry["is_binder_card"] is True

    def test_removing_binder_card_auto_selects_another(self, client, session, profile, species_set, test_set):
        """Removing the selected binder card auto-selects another owned card."""
        sp = species_set[0]
        card_a = _make_card(session, sp, test_set, "a")
        card_b = _make_card(session, sp, test_set, "b")

        # Add both cards (first is auto-selected)
        resp_a = client.post("/collection/cards", json={"card_id": card_a.id, "quantity": 1})
        entry_a_id = resp_a.json()["id"]
        client.post("/collection/cards", json={"card_id": card_b.id, "quantity": 1})

        # Remove card A (the binder card)
        client.delete(f"/collection/{entry_a_id}")

        # Card B should auto-become binder card
        entries = client.get(f"/collection/species/{sp.id}/cards").json()
        assert len(entries) == 1
        assert entries[0]["is_binder_card"] is True

    def test_removing_final_card_falls_back_to_species_only(self, client, session, profile, species_set, test_set):
        """Removing the last card when species-level entry exists → owned, no card."""
        sp = species_set[0]
        card = _make_card(session, sp, test_set)

        # Add species-level + card-level
        session.add(Collection(profile_id=profile.id, pokemon_species_id=sp.id, quantity=1))
        session.commit()
        resp = client.post("/collection/cards", json={"card_id": card.id, "quantity": 1})
        entry_id = resp.json()["id"]

        # Remove the card
        client.delete(f"/collection/{entry_id}")

        # Binder: owned but no card
        binder = client.get("/binder/page?page_size=20")
        slot = binder.json()["slots"][0]
        assert slot["owned"] is True
        assert slot["has_card"] is False
        assert slot["card"] is None

    def test_binder_never_shows_other_profiles_cards(self, client, session, profile, species_set, test_set):
        """Cards owned by another profile must not appear in this profile's binder."""
        sp = species_set[0]
        card = _make_card(session, sp, test_set)

        # Add card to a DIFFERENT profile
        p2 = Profile(name="Other", is_active=False)
        session.add(p2)
        session.commit()
        session.refresh(p2)
        session.add(Collection(profile_id=p2.id, card_id=card.id, quantity=1, is_binder_card=True))
        session.commit()

        # Active profile's binder should NOT show the card
        binder = client.get("/binder/page?page_size=20")
        slot = binder.json()["slots"][0]
        assert slot["owned"] is False
        assert slot["card"] is None

    def test_binder_selection_is_profile_specific(self, client, session, profile, species_set, test_set):
        """Each profile can independently select its binder card."""
        sp = species_set[0]
        card = _make_card(session, sp, test_set)

        # Active profile owns the card
        session.add(Collection(profile_id=profile.id, card_id=card.id, quantity=1, is_binder_card=True))
        session.commit()

        # Binder shows it
        binder = client.get("/binder/page?page_size=20")
        slot = binder.json()["slots"][0]
        assert slot["owned"] is True
        assert slot["has_card"] is True
        assert slot["card"]["id"] == card.id
