"""Stage B — Delta Reign (me6) full upgrade simulation.

Verifies the GENUINE ``CardDataUpdater`` can upgrade a realistic existing
installation — 179 sets / card_data_version 3, seeded from the ACTUAL local
PullDex-Card-Data set files (everything except me6) — up to the 180-set /
version-4 catalogue, adding Delta Reign and preserving ALL existing user data
(profiles, collection entries, binders, binder placements) byte-for-byte.

No network: the manifest and set-file fetchers are injected and read the real
local repo files from disk. No real database is touched: each test uses its own
temporary on-disk SQLite DB under pytest ``tmp_path``. The genuine pre-update
backup helper is used; because the DB lives under ``tmp_path`` the backup it
writes (``db_path.parent / pulldex_backup_before_card_update_*.db``) is also
confined to the temporary directory.

This module adds NO changes to application source or existing tests. It only
exercises the public updater API and its documented DI hooks
(``manifest_fetcher`` / ``set_fetcher`` / ``backup_factory``).
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
from app.models.binder import Binder, BinderPlacement, BinderType
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
_CARD_DATA_REPO = Path(__file__).resolve().parents[3] / "PullDex-Card-Data"
_MANIFEST_PATH = _CARD_DATA_REPO / "manifest.json"
_ME6_PATH = _CARD_DATA_REPO / "sets" / "me6.json"

MANIFEST_URL = "https://raw.githubusercontent.com/RyanAce97/PullDex-Card-Data/main/manifest.json"

SPECIES_MAX_DEX = 1025  # full National Pokédex, matching a real install


pytestmark = pytest.mark.skipif(
    not (_MANIFEST_PATH.is_file() and _ME6_PATH.is_file()),
    reason="PullDex-Card-Data repo (manifest.json / sets/me6.json) not found",
)


def _load_manifest() -> dict:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _me6_payload() -> dict:
    return json.loads(_ME6_PATH.read_text(encoding="utf-8"))


def _me6_bytes() -> bytes:
    return _ME6_PATH.read_bytes()


def _me6_card_ids() -> set[str]:
    return {c["api_card_id"] for c in _me6_payload()["cards"]}


# ---------------------------------------------------------------------------
# File-backed fetchers (no network)
# ---------------------------------------------------------------------------

def _file_backed_fetchers():
    def manifest_fetcher(url, timeout):
        return _MANIFEST_PATH.read_text(encoding="utf-8")

    def set_fetcher(url, timeout):
        if "/main/" in url:
            rel = url.split("/main/", 1)[-1]
        else:
            rel = "/".join(url.rsplit("/", 2)[-2:])
        return (_CARD_DATA_REPO / rel).read_bytes()

    return manifest_fetcher, set_fetcher


# ---------------------------------------------------------------------------
# Realistic pre-update DB: 179 sets (all except me6), full species table,
# user data (profile, collection, binder, binder placement), version 3.
# ---------------------------------------------------------------------------

@pytest.fixture(name="db")
def db_fixture(tmp_path):
    db_path = tmp_path / "pulldex_stage_b.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    manifest = _load_manifest()

    with Session(engine) as s:
        # 1) Full National Pokédex species table (1..1025).
        for dex in range(1, SPECIES_MAX_DEX + 1):
            s.add(PokemonSpecies(national_dex_number=dex,
                                 name=f"species{dex}", generation=1))
        s.commit()
        species_id_by_dex = {
            sp.national_dex_number: sp.id
            for sp in s.exec(select(PokemonSpecies)).all()
        }

        # 2) Every manifest set EXCEPT me6, seeded from the real repo files.
        for entry in manifest["sets"]:
            if entry["id"] == "me6":
                continue
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

        # 3) Realistic user data.
        profile = Profile(name="Ryan", is_active=True, binder_rows=3,
                          binder_columns=3, binder_sort="set")
        s.add(profile)
        s.commit()
        s.refresh(profile)

        # Pick two real, stable pre-existing cards to own / place.
        anchor_cards = s.exec(
            select(Card).where(Card.api_card_id.in_(["base1-58", "base1-4"]))
        ).all()
        # Fall back to the first two cards if those ids ever change.
        if len(anchor_cards) < 2:
            anchor_cards = s.exec(select(Card).order_by(Card.id)).all()[:2]
        card_a, card_b = anchor_cards[0], anchor_cards[1]

        # Card-level collection entry (owned copies) + species-level entry.
        s.add(Collection(profile_id=profile.id, card_id=card_a.id,
                         quantity=3, is_binder_card=True))
        s.add(Collection(profile_id=profile.id,
                         pokemon_species_id=card_b.pokemon_species_id,
                         quantity=1, is_binder_card=False))

        # A FREE_PLACEMENT binder with one explicit placement.
        binder = Binder(profile_id=profile.id, name="Master Collection",
                        binder_type=BinderType.FREE_PLACEMENT.value,
                        rows=3, columns=3, sort_order="set", is_default=True)
        s.add(binder)
        s.commit()
        s.refresh(binder)
        s.add(BinderPlacement(binder_id=binder.id, card_id=card_a.id,
                              page=1, slot=0))

        # 4) Pre-Delta-Reign card-data version.
        s.add(AppMetadata(key="card_data_version", value="3"))
        s.commit()

    yield engine, db_path, tmp_path
    engine.dispose()


# ---------------------------------------------------------------------------
# Snapshot helpers — full row-level dumps (detect add/delete/CHANGE).
# ---------------------------------------------------------------------------

_USER_TABLES = ("profiles", "collection", "binders", "binder_placements")
_REF_TABLES = ("pokemon_species", "sets", "cards", "app_metadata")
_ORDER = {
    "pokemon_species": "id", "sets": "id", "cards": "id",
    "app_metadata": "key", "profiles": "id", "collection": "id",
    "binders": "id", "binder_placements": "id",
}


def _dump(conn, table):
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(
        f"SELECT * FROM {table} ORDER BY {_ORDER[table]}").fetchall()]


def _snapshot(db_path, tables):
    conn = sqlite3.connect(str(db_path))
    try:
        return {t: _dump(conn, t) for t in tables}
    finally:
        conn.close()


def _checksum(db_path, tables):
    """Deterministic checksum over the given tables' full row contents."""
    snap = _snapshot(db_path, tables)
    blob = json.dumps(snap, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _make_updater(db):
    engine, db_path, _tmp = db
    session = Session(engine)
    mf, sf = _file_backed_fetchers()

    def backup_factory():
        # Genuine backup helper; output confined to the DB's (tmp) directory.
        return create_pre_update_backup(db_path=db_path)

    updater = CardDataUpdater(
        session=session,
        manifest_url=MANIFEST_URL,
        supported_schema_version=1,
        timeout=10.0,
        manifest_fetcher=mf,
        set_fetcher=sf,
        backup_factory=backup_factory,
    )
    return updater, session


# ===========================================================================
# Fixture sanity: the pre-update DB really is a 179-set / v3 install.
# ===========================================================================

class TestPreUpdateState:
    def test_fixture_is_realistic_179_set_install(self, db):
        engine, db_path, _ = db
        conn = sqlite3.connect(str(db_path))
        try:
            n_sets = conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0]
            has_me6 = conn.execute(
                "SELECT COUNT(*) FROM sets WHERE api_set_id='me6'").fetchone()[0]
            n_species = conn.execute(
                "SELECT COUNT(*) FROM pokemon_species").fetchone()[0]
        finally:
            conn.close()
        assert n_sets == 179
        assert has_me6 == 0
        assert n_species == SPECIES_MAX_DEX
        assert get_local_card_data_version(Session(engine)) == 3


# ===========================================================================
# The upgrade.
# ===========================================================================

class TestDeltaReignUpgrade:
    def test_full_upgrade_preserves_user_data(self, db):
        engine, db_path, tmp_path = db

        before_ref = _snapshot(db_path, _REF_TABLES)
        before_user = _snapshot(db_path, _USER_TABLES)
        before_user_checksum = _checksum(db_path, _USER_TABLES)

        # Stable identity maps for existing reference rows.
        before_set_pk = {s["api_set_id"]: s["id"] for s in before_ref["sets"]}
        before_card_pk = {c["api_card_id"]: c["id"] for c in before_ref["cards"]}

        # Existing backups in the tmp dir before the run (expect none).
        backups_before = list(tmp_path.glob("pulldex_backup_before_card_update_*.db"))

        updater, session = _make_updater(db)
        try:
            result = updater.update_card_data()
        finally:
            session.close()

        # 1. success
        assert result.status is UpdateResultStatus.UPDATED, result.error
        assert result.success is True
        assert result.sets_created == 1
        assert result.cards_created == 141

        conn = sqlite3.connect(str(db_path))
        try:
            # 2. 180 sets
            assert conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0] == 180
            # 3. 20,954 cards
            assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 20954
            # 4. me6 exists
            me6_row = conn.execute(
                "SELECT id, name, is_promo FROM sets WHERE api_set_id='me6'"
            ).fetchone()
            assert me6_row is not None
            me6_set_id, me6_name, me6_promo = me6_row
            assert me6_name == "Mega Evolution\u2014Delta Reign"
            assert me6_promo == 0
            # 5. me6 has exactly 141 cards
            me6_card_rows = conn.execute(
                "SELECT api_card_id FROM cards WHERE set_id=?", (me6_set_id,)
            ).fetchall()
            assert len(me6_card_rows) == 141
            # 6. card IDs match me6.json exactly
            assert {r[0] for r in me6_card_rows} == _me6_card_ids()
            # 7. version now 4
            assert get_local_card_data_version(Session(engine)) == 4
        finally:
            conn.close()

        # 8. a valid pre-update backup was created
        assert result.backup_path is not None
        backup_path = Path(result.backup_path)
        assert backup_path.is_file()
        backups_after = list(tmp_path.glob("pulldex_backup_before_card_update_*.db"))
        assert len(backups_after) == len(backups_before) + 1

        # 9. backup represents the PRE-update state (179 sets, no me6, v3)
        bconn = sqlite3.connect(str(backup_path))
        try:
            assert bconn.execute("SELECT COUNT(*) FROM sets").fetchone()[0] == 179
            assert bconn.execute(
                "SELECT COUNT(*) FROM sets WHERE api_set_id='me6'").fetchone()[0] == 0
            bver = bconn.execute(
                "SELECT value FROM app_metadata WHERE key='card_data_version'"
            ).fetchone()[0]
            assert bver == "3"
        finally:
            bconn.close()

        after_ref = _snapshot(db_path, _REF_TABLES)

        # 10. existing set + card PKs and API IDs unchanged
        after_set_pk = {s["api_set_id"]: s["id"] for s in after_ref["sets"]}
        after_card_pk = {c["api_card_id"]: c["id"] for c in after_ref["cards"]}
        for api_id, pk in before_set_pk.items():
            assert after_set_pk[api_id] == pk
        for api_id, pk in before_card_pk.items():
            assert after_card_pk[api_id] == pk

        # 11. nothing deleted (all prior sets/cards still present)
        assert set(before_set_pk) <= set(after_set_pk)
        assert set(before_card_pk) <= set(after_card_pk)
        assert set(after_set_pk) - set(before_set_pk) == {"me6"}
        assert len(after_card_pk) - len(before_card_pk) == 141

        # 12. user data identical (row-level + checksum)
        after_user = _snapshot(db_path, _USER_TABLES)
        assert after_user == before_user
        assert _checksum(db_path, _USER_TABLES) == before_user_checksum

        # 13. species records unchanged
        assert after_ref["pokemon_species"] == before_ref["pokemon_species"]

    def test_second_run_is_idempotent(self, db):
        engine, db_path, tmp_path = db

        # First upgrade.
        u1, s1 = _make_updater(db)
        try:
            r1 = u1.update_card_data()
        finally:
            s1.close()
        assert r1.status is UpdateResultStatus.UPDATED

        ref_after_first = _snapshot(db_path, _REF_TABLES)
        user_after_first = _snapshot(db_path, _USER_TABLES)
        set_pk_after_first = {s["api_set_id"]: s["id"] for s in ref_after_first["sets"]}
        card_pk_after_first = {c["api_card_id"]: c["id"] for c in ref_after_first["cards"]}
        backups_after_first = list(
            tmp_path.glob("pulldex_backup_before_card_update_*.db"))

        # Second run.
        u2, s2 = _make_updater(db)
        try:
            r2 = u2.update_card_data()
        finally:
            s2.close()

        # already up to date (remote v4 == local v4)
        assert r2.status is UpdateResultStatus.ALREADY_UP_TO_DATE

        conn = sqlite3.connect(str(db_path))
        try:
            assert conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0] == 180
            assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 20954
            me6_id = conn.execute(
                "SELECT id FROM sets WHERE api_set_id='me6'").fetchone()[0]
            assert conn.execute(
                "SELECT COUNT(*) FROM cards WHERE set_id=?", (me6_id,)
            ).fetchone()[0] == 141
            # no duplicate sets/cards
            assert conn.execute(
                "SELECT COUNT(*) FROM (SELECT api_set_id FROM sets "
                "GROUP BY api_set_id HAVING COUNT(*) > 1)").fetchone()[0] == 0
            assert conn.execute(
                "SELECT COUNT(*) FROM (SELECT api_card_id FROM cards "
                "GROUP BY api_card_id HAVING COUNT(*) > 1)").fetchone()[0] == 0
        finally:
            conn.close()

        # user data + reference identity stable across the no-op run
        assert _snapshot(db_path, _USER_TABLES) == user_after_first
        after_ref = _snapshot(db_path, _REF_TABLES)
        assert {s["api_set_id"]: s["id"] for s in after_ref["sets"]} == set_pk_after_first
        assert {c["api_card_id"]: c["id"] for c in after_ref["cards"]} == card_pk_after_first

        # no unnecessary second backup: an ALREADY_UP_TO_DATE run returns
        # before the backup step, so the backup count must not increase.
        assert r2.backup_path is None
        backups_after_second = list(
            tmp_path.glob("pulldex_backup_before_card_update_*.db"))
        assert len(backups_after_second) == len(backups_after_first)
