"""Stage A — Delta Reign (me6) card-data updater integration test.

Drives the REAL `CardDataUpdater` against the ACTUAL local card-data files
from the PullDex-Card-Data repository:

    PullDex-Card-Data/manifest.json
    PullDex-Card-Data/sets/me6.json

No network access: the manifest and set-file fetchers are injected and read
the local files from disk (file-backed fetchers). No live/seed database is
touched: each test uses its own temporary on-disk SQLite database seeded to
represent a "pre-Delta-Reign" installation (data_version 3) that already
contains the Pokémon species table (as a real install would).

This module adds NO changes to application source or existing tests. It only
exercises the public updater API and its documented dependency-injection
hooks (`manifest_fetcher`, `set_fetcher`, `backup_factory`).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.app_metadata import AppMetadata
from app.models.card import Card
from app.models.collection import Collection
from app.models.pokemon_species import PokemonSpecies
from app.models.profile import Profile
from app.models.set import Set
from app.services.card_data_updater_service import (
    CardDataUpdater,
    UpdateResultStatus,
    create_pre_update_backup,
    validate_set_payload,
)
from app.services.card_data_version_service import get_local_card_data_version


# ---------------------------------------------------------------------------
# Locate the real card-data repository (sibling of the PullDex repo)
# ---------------------------------------------------------------------------

# tests/ -> backend/ -> PullDex/ -> Desktop/ -> PullDex-Card-Data/
_CARD_DATA_REPO = (
    Path(__file__).resolve().parents[3] / "PullDex-Card-Data"
)
_MANIFEST_PATH = _CARD_DATA_REPO / "manifest.json"
_ME6_PATH = _CARD_DATA_REPO / "sets" / "me6.json"

MANIFEST_URL = "https://raw.githubusercontent.com/RyanAce97/PullDex-Card-Data/main/manifest.json"


pytestmark = pytest.mark.skipif(
    not (_MANIFEST_PATH.is_file() and _ME6_PATH.is_file()),
    reason="PullDex-Card-Data repo (manifest.json / sets/me6.json) not found",
)


# ---------------------------------------------------------------------------
# Load the real local manifest + me6 bytes once
# ---------------------------------------------------------------------------

def _load_manifest() -> dict:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _me6_entry(manifest: dict) -> dict:
    for s in manifest["sets"]:
        if s["id"] == "me6":
            return s
    raise AssertionError("me6 entry missing from local manifest.json")


def _me6_bytes() -> bytes:
    # Exact on-disk bytes — this is what the manifest sha256 is defined over.
    return _ME6_PATH.read_bytes()


def _me6_payload() -> dict:
    return json.loads(_ME6_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# File-backed fetchers (no network). They serve the manifest and any set file
# referenced by it directly from the card-data repo on disk.
# ---------------------------------------------------------------------------

def _file_backed_fetchers():
    def manifest_fetcher(url, timeout):
        return _MANIFEST_PATH.read_text(encoding="utf-8")

    def set_fetcher(url, timeout):
        # url looks like ".../main/sets/me6.json" — resolve the trailing path
        # (relative to the repo root) back to a file inside the card-data repo.
        if "/main/" in url:
            rel = url.split("/main/", 1)[-1]
        else:
            rel = "/".join(url.rsplit("/", 2)[-2:])
        file_path = _CARD_DATA_REPO / rel
        return file_path.read_bytes()

    return manifest_fetcher, set_fetcher


# ---------------------------------------------------------------------------
# Temporary DB representing a "pre-Delta-Reign" installation.
#
# We seed:
#   * every Pokémon species referenced by me6 (as a real install's species
#     table would already contain — 1,025 species ship in the baseline),
#   * one pre-existing reference set + card (to prove nothing unrelated is
#     touched),
#   * user data (profile + collection) to prove it is never modified,
#   * card_data_version = 3 (the version prior to the me6 corrections).
# ---------------------------------------------------------------------------

@pytest.fixture(name="db")
def db_fixture(tmp_path):
    db_path = tmp_path / "pulldex_stage_a.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    # The real CardDataUpdater re-downloads EVERY set in the manifest (not just
    # me6) and species-resolves every Pokémon card across ALL of them before it
    # will apply the update. A real PullDex installation's species table ships
    # the complete National Pokédex (dex 1..1025, verified against the seed DB).
    # The fixture must mirror that so species resolution succeeds for every set,
    # exactly as it would on a real install. (Seeding only me6's 87 dex numbers
    # was the bug: dex 1 — Bulbasaur, used by base1 — was absent.)
    SPECIES_MAX_DEX = 1025

    manifest = _load_manifest()

    with Session(engine) as s:
        # 1) Full National Pokédex species reference table (1..1025).
        for dex in range(1, SPECIES_MAX_DEX + 1):
            s.add(PokemonSpecies(national_dex_number=dex,
                                 name=f"species{dex}", generation=1))
        s.commit()
        species_id_by_dex = {
            sp.national_dex_number: sp.id
            for sp in s.exec(select(PokemonSpecies)).all()
        }

        # 2) Pre-seed EVERY existing set + its cards EXCEPT the new me6 set,
        #    so the DB represents a real "pre-Delta-Reign" installation that
        #    already has the other 179 sets. This makes the subsequent update
        #    create exactly one new set (me6) and exactly 141 new cards.
        for entry in manifest["sets"]:
            if entry["id"] == "me6":
                continue  # the set under test must be absent beforehand
            payload = json.loads(
                (_CARD_DATA_REPO / entry["file"]).read_text(encoding="utf-8")
            )
            sm = payload["set"]
            new_set = Set(
                api_set_id=sm["id"], name=sm["name"], series=sm["series"],
                release_date=(date.fromisoformat(sm["release_date"])
                              if sm.get("release_date") else None),
                is_promo=bool(sm.get("is_promo", False)),
            )
            s.add(new_set)
            s.flush()
            for c in payload["cards"]:
                dex = c["national_dex_number"]
                s.add(Card(
                    api_card_id=c["api_card_id"], set_id=new_set.id,
                    pokemon_species_id=(species_id_by_dex.get(dex)
                                        if dex is not None else None),
                    card_number=c["card_number"], rarity=c["rarity"],
                    variant=c["variant"], image_url=c["image_url"],
                ))
        s.commit()

        # 3) User (private) data — attached to a real pre-existing card so we
        #    can prove the merge never touches collection/profile rows.
        anchor = s.exec(select(Card)).first()
        profile = Profile(name="Ryan", is_active=True, binder_rows=5,
                          binder_columns=4, binder_sort="dex_number")
        s.add(profile)
        s.commit()
        s.refresh(profile)
        s.add(Collection(profile_id=profile.id, card_id=anchor.id,
                         quantity=3, is_binder_card=True))

        # 4) Pre-Delta-Reign card-data version.
        s.add(AppMetadata(key="card_data_version", value="3"))
        s.commit()

    needed_dex = sorted(
        {c["national_dex_number"] for c in _me6_payload()["cards"]
         if c["national_dex_number"] is not None}
    )
    yield engine, db_path, needed_dex
    engine.dispose()


def _snapshot(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        def dump(table, order):
            return [dict(r) for r in conn.execute(
                f"SELECT * FROM {table} ORDER BY {order}").fetchall()]
        return {
            "pokemon_species": dump("pokemon_species", "id"),
            "sets": dump("sets", "id"),
            "cards": dump("cards", "id"),
            "collection": dump("collection", "id"),
            "profiles": dump("profiles", "id"),
            "app_metadata": dump("app_metadata", "key"),
        }
    finally:
        conn.close()


def _make_updater(db):
    engine, db_path, _ = db
    session = Session(engine)
    mf, sf = _file_backed_fetchers()

    def backup_factory():
        return create_pre_update_backup(db_path=db_path)

    updater = CardDataUpdater(
        session=session,
        manifest_url=MANIFEST_URL,
        supported_schema_version=1,
        timeout=5.0,
        manifest_fetcher=mf,
        set_fetcher=sf,
        backup_factory=backup_factory,
    )
    return updater, session


# ===========================================================================
# 0. Manifest checksum matches the exact local me6.json bytes
# ===========================================================================

def test_manifest_sha256_matches_me6_bytes():
    manifest = _load_manifest()
    entry = _me6_entry(manifest)
    actual = hashlib.sha256(_me6_bytes()).hexdigest()
    assert entry["sha256"] == actual, (
        f"manifest me6 sha256 {entry['sha256'][:12]}… != file {actual[:12]}…"
    )
    assert entry["card_count"] == 141
    assert manifest["data_version"] == 5


# ===========================================================================
# 1. me6 payload passes the updater's own structural validation (141 cards)
# ===========================================================================

def test_me6_payload_passes_structural_validation():
    payload = _me6_payload()
    returned = validate_set_payload(payload, "me6")
    assert returned is payload
    assert payload["card_count"] == 141
    assert len(payload["cards"]) == 141


# ===========================================================================
# 2. Full update: manifest accepted, v4 detected, me6 created, 141 cards,
#    species resolve, version -> 4, nothing unrelated deleted/changed.
# ===========================================================================

class TestDeltaReignUpdate:
    def test_successful_update(self, db):
        engine, db_path, needed_dex = db
        before = _snapshot(db_path)

        updater, session = _make_updater(db)
        try:
            result = updater.update_card_data()
        finally:
            session.close()

        # --- updater reports success ---
        assert result.status is UpdateResultStatus.UPDATED, result.error
        assert result.success is True
        assert result.local_data_version == 5
        assert result.remote_data_version == 5

        # --- exactly one new set, exactly 141 new cards ---
        assert result.sets_created == 1
        assert result.cards_created == 141

        # --- manifest counts surfaced ---
        assert result.set_count == 180
        assert result.card_count == 20954

        # --- backup created ---
        assert result.backup_path is not None
        assert Path(result.backup_path).is_file()

        after = _snapshot(db_path)

        # me6 set present with 141 cards
        me6_set = next((s for s in after["sets"] if s["api_set_id"] == "me6"), None)
        assert me6_set is not None
        assert me6_set["name"] == "Delta Reign"
        assert me6_set["is_promo"] == 0  # False
        me6_set_id = me6_set["id"]
        me6_cards = [c for c in after["cards"] if c["set_id"] == me6_set_id]
        assert len(me6_cards) == 141

        # species resolution: every Pokémon me6 card has a species FK;
        # every Trainer/Energy me6 card has NULL species FK.
        payload = _me6_payload()
        te_numbers = {
            int(c["card_number"]) for c in payload["cards"]
            if c["national_dex_number"] is None
        }
        for c in me6_cards:
            num = int(c["card_number"])
            if num in te_numbers:
                assert c["pokemon_species_id"] is None, f"card {num} should be Trainer/Energy"
            else:
                assert c["pokemon_species_id"] is not None, f"card {num} missing species FK"

        # local card-data version becomes 4
        assert get_local_card_data_version(Session(engine)) == 5

        # --- nothing deleted; only me6 added ---
        # The fixture pre-seeded the other 179 sets, so after the update there
        # must be exactly 180 sets and exactly `before + 141` cards. Every set
        # that existed before must still exist (no deletions).
        before_set_ids = {s["api_set_id"] for s in before["sets"]}
        after_set_ids = {s["api_set_id"] for s in after["sets"]}
        assert before_set_ids <= after_set_ids           # nothing removed
        assert after_set_ids - before_set_ids == {"me6"}  # only me6 added
        assert len(after["sets"]) == 180
        assert len(after["cards"]) == len(before["cards"]) + 141

        # existing (pre-seeded) sets keep their stable primary keys — the
        # updater matches by api_set_id and never recreates rows.
        before_set_pk = {s["api_set_id"]: s["id"] for s in before["sets"]}
        after_set_pk = {s["api_set_id"]: s["id"] for s in after["sets"]}
        for sid in before_set_ids:
            assert after_set_pk[sid] == before_set_pk[sid]

        # species table unchanged (all 1025 already present; none added/removed)
        assert len(after["pokemon_species"]) == len(before["pokemon_species"])
        assert after["pokemon_species"] == before["pokemon_species"]

        # user data untouched
        assert after["collection"] == before["collection"]
        assert after["profiles"] == before["profiles"]

    def test_second_run_is_idempotent(self, db):
        engine, db_path, _ = db

        u1, s1 = _make_updater(db)
        try:
            r1 = u1.update_card_data()
        finally:
            s1.close()
        assert r1.status is UpdateResultStatus.UPDATED

        after_first = _snapshot(db_path)

        u2, s2 = _make_updater(db)
        try:
            r2 = u2.update_card_data()
        finally:
            s2.close()

        # Remote data_version (5) == local (now 5) -> already up to date.
        assert r2.status is UpdateResultStatus.ALREADY_UP_TO_DATE
        assert _snapshot(db_path) == after_first
