"""Stage 2B card-data updater tests.

Covers the full update lifecycle with NO network access (manifest + set
fetchers are always injected fakes) and NO use of the live database (each test
uses its own temporary on-disk SQLite database).

Scenarios (per the Stage 2B spec §13):
    A. Manifest fetch failure        -> no DB change
    B. Invalid manifest              -> no DB change
    C. Set download failure          -> no DB change
    D. SHA-256 mismatch              -> no DB change
    E. Malformed set JSON            -> no DB change
    F. DB failure mid-merge          -> rollback, version unchanged
    G. Successful update             -> sets/cards present, version changed
    H. Re-run successful update      -> idempotent, no dupes, no user changes

Plus:
    * INCOMPATIBLE_SCHEMA and ALREADY_UP_TO_DATE
    * species-mapping failure (unmapped Pokémon dex) -> INVALID_SET_DATA
    * the CRITICAL protected-user-data snapshot test (success + rollback)
    * the no-overwrite, abort-on-failure backup helper
    * "never deletes existing cards/sets"
"""

import hashlib
import json
import sqlite3
import urllib.error
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
    _BackupError,
    SetValidationError,
)
from app.services.card_data_version_service import get_local_card_data_version


# ===========================================================================
# Fixtures: an on-disk SQLite DB seeded with reference + user data
# ===========================================================================

@pytest.fixture(name="db")
def db_fixture(tmp_path):
    """A real on-disk SQLite DB (so backup + rollback are meaningful)."""
    db_path = tmp_path / "pulldex_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as s:
        # --- reference (public) data ---
        pikachu = PokemonSpecies(national_dex_number=25, name="pikachu", generation=1)
        charizard = PokemonSpecies(national_dex_number=6, name="charizard", generation=1)
        mew = PokemonSpecies(national_dex_number=151, name="mew", generation=1)
        s.add_all([pikachu, charizard, mew])
        s.commit()
        for obj in (pikachu, charizard, mew):
            s.refresh(obj)

        base = Set(api_set_id="base1", name="Base", series="Base")
        s.add(base)
        s.commit()
        s.refresh(base)

        c1 = Card(api_card_id="base1-58", set_id=base.id, pokemon_species_id=pikachu.id,
                  card_number="58", rarity="Common", image_url="http://img/base1-58")
        c2 = Card(api_card_id="base1-4", set_id=base.id, pokemon_species_id=charizard.id,
                  card_number="4", rarity="Rare Holo", image_url="http://img/base1-4")
        s.add_all([c1, c2])
        s.commit()
        for obj in (c1, c2):
            s.refresh(obj)

        # --- user (private) data ---
        profile = Profile(name="Ryan", is_active=True, binder_rows=5,
                          binder_columns=4, binder_sort="dex_number")
        s.add(profile)
        s.commit()
        s.refresh(profile)

        s.add(Collection(profile_id=profile.id, card_id=c1.id, quantity=3,
                         is_binder_card=True))
        s.add(Collection(profile_id=profile.id, pokemon_species_id=mew.id,
                         quantity=1, is_binder_card=False))
        s.add(AppMetadata(key="card_data_version", value="1"))
        s.commit()

    yield engine, db_path
    engine.dispose()


# ===========================================================================
# Manifest / set-file fixtures (no network — everything injected)
# ===========================================================================

MANIFEST_URL = "https://example.test/main/manifest.json"


def _set_payload(set_id, name, series, cards, release_date="2020-01-01", is_promo=False):
    return {
        "set": {"id": set_id, "name": name, "series": series,
                "release_date": release_date, "is_promo": is_promo},
        "card_count": len(cards),
        "cards": cards,
    }


def _card(api_card_id, number, dex=None, species=None, rarity="Common",
          variant=None, image="http://img/x"):
    return {
        "api_card_id": api_card_id,
        "card_number": number,
        "rarity": rarity,
        "variant": variant,
        "image_url": image,
        "national_dex_number": dex,
        "species_name": species,
    }


def _canonical_bytes(payload) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _build_remote(sets, data_version=2, schema_version=1):
    """Build (manifest_dict, {file: bytes}) for a set of payloads keyed by id."""
    files = {}
    manifest_sets = []
    total_cards = 0
    for set_id, payload in sets.items():
        raw = _canonical_bytes(payload)
        file_path = f"sets/{set_id}.json"
        files[file_path] = raw
        total_cards += payload["card_count"]
        manifest_sets.append({
            "id": set_id,
            "name": payload["set"]["name"],
            "series": payload["set"]["series"],
            "release_date": payload["set"]["release_date"],
            "file": file_path,
            "card_count": payload["card_count"],
            "version": 1,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "is_promo": payload["set"].get("is_promo", False),
        })
    manifest = {
        "schema_version": schema_version,
        "data_version": data_version,
        "updated_at": "2026-09-16T00:00:00Z",
        "set_count": len(manifest_sets),
        "card_count": total_cards,
        "sets": manifest_sets,
    }
    return manifest, files


def _fetchers(manifest, files, *, manifest_exc=None, set_exc=None,
              corrupt_files=None, tamper_bytes=False):
    manifest_text = json.dumps(manifest)

    def manifest_fetcher(url, timeout):
        if manifest_exc is not None:
            raise manifest_exc
        return manifest_text

    def set_fetcher(url, timeout):
        if set_exc is not None:
            raise set_exc
        key = "sets/" + url.rsplit("/", 1)[1]
        if corrupt_files and key in corrupt_files:
            return corrupt_files[key]
        raw = files[key]
        if tamper_bytes:
            return raw + b"tampered"
        return raw

    return manifest_fetcher, set_fetcher


def _make_updater(db, manifest, files, *, backup_factory=None, **fetch_kwargs):
    engine, db_path = db
    session = Session(engine)
    mf, sf = _fetchers(manifest, files, **fetch_kwargs)
    if backup_factory is None:
        def backup_factory():
            return create_pre_update_backup(db_path=db_path)
    updater = CardDataUpdater(
        session=session,
        manifest_url=MANIFEST_URL,
        supported_schema_version=1,
        timeout=1.0,
        manifest_fetcher=mf,
        set_fetcher=sf,
        backup_factory=backup_factory,
    )
    return updater, session


# ===========================================================================
# Full-database snapshot (everything the updater must protect)
# ===========================================================================

def _snapshot_all(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        def dump(table, order):
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
            return [dict(r) for r in rows]
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


def _protected_snapshot(db_path):
    full = _snapshot_all(db_path)
    return {
        "collection": full["collection"],
        "profiles": full["profiles"],
        "pokemon_species": full["pokemon_species"],
    }


def _standard_remote(data_version=2):
    me55 = _set_payload("me55", "30th Celebration", "Mega Evolution", [
        _card("me55-1", "1", dex=25, species="pikachu", rarity="Common"),
        _card("me55-2", "2", dex=None, species=None, rarity="Trainer"),
    ], release_date="2026-09-16")
    base1 = _set_payload("base1", "Base", "Base", [
        _card("base1-58", "58", dex=25, species="pikachu", rarity="Common",
              image="http://img/base1-58"),
        _card("base1-4", "4", dex=6, species="charizard", rarity="Rare Holo",
              image="http://img/base1-4-NEW"),
    ], release_date="1999-01-09")
    return _build_remote({"me55": me55, "base1": base1}, data_version=data_version)


# ===========================================================================
# Scenario G — successful update
# ===========================================================================

class TestSuccessfulUpdate:
    def test_update_adds_and_updates_reference_data(self, db):
        engine, db_path = db
        manifest, files = _standard_remote(data_version=2)
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()

        assert result.status is UpdateResultStatus.UPDATED
        assert result.success is True
        assert result.local_data_version == 2
        assert result.remote_data_version == 2
        assert result.sets_created == 1
        assert result.cards_created == 2
        assert result.cards_updated == 1
        assert result.backup_path is not None
        assert Path(result.backup_path).is_file()

        after = _snapshot_all(db_path)
        card_ids = {c["api_card_id"] for c in after["cards"]}
        assert {"base1-58", "base1-4", "me55-1", "me55-2"} == card_ids
        set_ids = {s["api_set_id"] for s in after["sets"]}
        assert {"base1", "me55"} == set_ids
        b4 = next(c for c in after["cards"] if c["api_card_id"] == "base1-4")
        assert b4["image_url"] == "http://img/base1-4-NEW"
        t = next(c for c in after["cards"] if c["api_card_id"] == "me55-2")
        assert t["pokemon_species_id"] is None
        assert get_local_card_data_version(Session(engine)) == 2

    def test_existing_card_ids_are_stable(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        before_card_id = {c["api_card_id"]: c["id"] for c in before["cards"]}

        manifest, files = _standard_remote()
        updater, session = _make_updater(db, manifest, files)
        try:
            updater.update_card_data()
        finally:
            session.close()

        after = _snapshot_all(db_path)
        after_card_id = {c["api_card_id"]: c["id"] for c in after["cards"]}
        assert after_card_id["base1-58"] == before_card_id["base1-58"]
        assert after_card_id["base1-4"] == before_card_id["base1-4"]


# ===========================================================================
# Scenario A — manifest fetch failure
# ===========================================================================

class TestManifestFetchFailure:
    def test_no_db_change(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote()
        updater, session = _make_updater(
            db, manifest, files, manifest_exc=urllib.error.URLError("dns")
        )
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.REMOTE_UNAVAILABLE
        assert result.success is False
        assert _snapshot_all(db_path) == before


# ===========================================================================
# Scenario B — invalid manifest
# ===========================================================================

class TestInvalidManifest:
    def test_bad_json_no_db_change(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)

        def bad_manifest_fetcher(url, timeout):
            return "{ not json"

        def no_backup():
            raise AssertionError("backup must not run")

        session = Session(engine)
        updater = CardDataUpdater(
            session=session, manifest_url=MANIFEST_URL, supported_schema_version=1,
            timeout=1.0, manifest_fetcher=bad_manifest_fetcher,
            set_fetcher=lambda u, t: b"{}", backup_factory=no_backup,
        )
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.INVALID_MANIFEST
        assert _snapshot_all(db_path) == before

    def test_structurally_invalid_manifest(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote()
        del manifest["sets"][0]["sha256"]
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.INVALID_MANIFEST
        assert _snapshot_all(db_path) == before


# ===========================================================================
# Scenario C — set download failure
# ===========================================================================

class TestSetDownloadFailure:
    def test_no_db_change(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote()
        updater, session = _make_updater(db, manifest, files, set_exc=TimeoutError("slow"))
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.DOWNLOAD_FAILED
        assert _snapshot_all(db_path) == before


# ===========================================================================
# Scenario D — SHA-256 mismatch
# ===========================================================================

class TestHashMismatch:
    def test_tampered_bytes_rejected_before_db(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote()
        updater, session = _make_updater(db, manifest, files, tamper_bytes=True)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.HASH_MISMATCH
        assert _snapshot_all(db_path) == before


# ===========================================================================
# Scenario E — malformed set JSON
# ===========================================================================

class TestMalformedSetJson:
    def test_hash_matches_but_not_json(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote()
        bad = b"this is not json at all\n"
        target = manifest["sets"][0]["file"]
        manifest["sets"][0]["sha256"] = hashlib.sha256(bad).hexdigest()
        updater, session = _make_updater(db, manifest, files, corrupt_files={target: bad})
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.HASH_MISMATCH
        assert _snapshot_all(db_path) == before

    def test_valid_json_but_invalid_structure(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        broken = _set_payload("me55", "30th", "Mega", [_card("me55-1", "1", 25, "pikachu")])
        broken["card_count"] = 5
        manifest, files = _build_remote({"me55": broken})
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.INVALID_SET_DATA
        assert _snapshot_all(db_path) == before


# ===========================================================================
# Scenario F — DB failure mid-merge -> rollback
# ===========================================================================

class TestMergeFailureRollsBack:
    def test_rollback_leaves_everything_unchanged(self, db, monkeypatch):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote(data_version=2)
        updater, session = _make_updater(db, manifest, files)

        original_merge = updater._merge

        def exploding_merge(downloaded, species_by_dex):
            original_merge(downloaded, species_by_dex)
            raise sqlite3.OperationalError("simulated mid-merge failure")

        monkeypatch.setattr(updater, "_merge", exploding_merge)
        try:
            result = updater.update_card_data()
        finally:
            session.close()

        assert result.status is UpdateResultStatus.DATABASE_UPDATE_FAILED
        assert result.success is False
        assert _snapshot_all(db_path) == before
        assert get_local_card_data_version(Session(engine)) == 1


# ===========================================================================
# Scenario H + idempotency
# ===========================================================================

class TestIdempotency:
    def test_second_run_is_up_to_date_no_changes(self, db):
        engine, db_path = db
        manifest, files = _standard_remote(data_version=2)

        updater1, s1 = _make_updater(db, manifest, files)
        try:
            r1 = updater1.update_card_data()
        finally:
            s1.close()
        assert r1.status is UpdateResultStatus.UPDATED

        after_first = _snapshot_all(db_path)

        updater2, s2 = _make_updater(db, manifest, files)
        try:
            r2 = updater2.update_card_data()
        finally:
            s2.close()
        assert r2.status is UpdateResultStatus.ALREADY_UP_TO_DATE
        assert _snapshot_all(db_path) == after_first

    def test_reapplying_same_content_at_higher_version_makes_no_dupes(self, db):
        engine, db_path = db
        manifest, files = _standard_remote(data_version=2)
        u1, s1 = _make_updater(
            db, manifest, files,
            backup_factory=lambda: str(db_path.parent / "backup_run1.db"),
        )
        try:
            u1.update_card_data()
        finally:
            s1.close()
        counts_after_first = {
            "cards": len(_snapshot_all(db_path)["cards"]),
            "sets": len(_snapshot_all(db_path)["sets"]),
        }

        manifest2, files2 = _standard_remote(data_version=3)
        u2, s2 = _make_updater(
            db, manifest2, files2,
            backup_factory=lambda: str(db_path.parent / "backup_run2.db"),
        )
        try:
            r = u2.update_card_data()
        finally:
            s2.close()
        assert r.status is UpdateResultStatus.UPDATED
        assert r.cards_created == 0
        assert r.sets_created == 0
        after = _snapshot_all(db_path)
        assert len(after["cards"]) == counts_after_first["cards"]
        assert len(after["sets"]) == counts_after_first["sets"]


# ===========================================================================
# INCOMPATIBLE_SCHEMA / ALREADY_UP_TO_DATE / never-downgrade
# ===========================================================================

class TestSchemaAndVersionPolicy:
    def test_incompatible_schema_no_db_change(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote(data_version=2)
        manifest["schema_version"] = 2
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.INCOMPATIBLE_SCHEMA
        assert _snapshot_all(db_path) == before

    def test_remote_equal_local_is_up_to_date(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote(data_version=1)
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.ALREADY_UP_TO_DATE
        assert _snapshot_all(db_path) == before

    def test_remote_below_local_never_downgrades(self, db):
        engine, db_path = db
        with Session(engine) as s:
            row = s.exec(select(AppMetadata).where(AppMetadata.key == "card_data_version")).first()
            row.value = "5"
            s.add(row)
            s.commit()
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote(data_version=3)
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.ALREADY_UP_TO_DATE
        assert _snapshot_all(db_path) == before
        assert get_local_card_data_version(Session(engine)) == 5


# ===========================================================================
# Species mapping failure -> INVALID_SET_DATA
# ===========================================================================

class TestSpeciesMappingFailure:
    def test_unmapped_pokemon_dex_fails(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        payload = _set_payload("me55", "30th", "Mega", [
            _card("me55-1", "1", dex=9999, species="missingno"),
        ])
        manifest, files = _build_remote({"me55": payload})
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.INVALID_SET_DATA
        assert _snapshot_all(db_path) == before
        assert len(_snapshot_all(db_path)["pokemon_species"]) == len(before["pokemon_species"])


# ===========================================================================
# Backup behaviour
# ===========================================================================

class TestBackupFailureAborts:
    def test_backup_failure_no_db_change(self, db):
        engine, db_path = db
        before = _snapshot_all(db_path)
        manifest, files = _standard_remote(data_version=2)

        def failing_backup():
            raise _BackupError("disk full")

        updater, session = _make_updater(db, manifest, files, backup_factory=failing_backup)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.DATABASE_BACKUP_FAILED
        assert _snapshot_all(db_path) == before
        assert get_local_card_data_version(Session(engine)) == 1


class TestBackupHelper:
    def test_creates_timestamped_usable_copy(self, db):
        engine, db_path = db
        path = create_pre_update_backup(db_path=db_path)
        p = Path(path)
        assert p.is_file()
        assert p.name.startswith("pulldex_backup_before_card_update_")
        assert p.name.endswith(".db")
        conn = sqlite3.connect(str(p))
        try:
            n = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            assert n == 2
        finally:
            conn.close()

    def test_never_overwrites_existing_backup(self, db):
        import datetime as _dt
        engine, db_path = db
        fixed = _dt.datetime(2026, 1, 2, 3, 4, 5)
        first = create_pre_update_backup(db_path=db_path, now=fixed)
        assert Path(first).is_file()
        with pytest.raises(_BackupError):
            create_pre_update_backup(db_path=db_path, now=fixed)

    def test_missing_db_raises(self, tmp_path):
        with pytest.raises(_BackupError):
            create_pre_update_backup(db_path=tmp_path / "nope.db")


# ===========================================================================
# CRITICAL data-safety snapshot test (spec §14)
# ===========================================================================

class TestCriticalProtectedDataSnapshot:
    def test_success_updates_reference_but_never_user_data(self, db):
        engine, db_path = db
        protected_before = _protected_snapshot(db_path)

        manifest, files = _standard_remote(data_version=2)
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()

        assert result.status is UpdateResultStatus.UPDATED

        after = _snapshot_all(db_path)
        assert {"base1", "me55"} == {s["api_set_id"] for s in after["sets"]}
        assert "me55-1" in {c["api_card_id"] for c in after["cards"]}
        b4 = next(c for c in after["cards"] if c["api_card_id"] == "base1-4")
        assert b4["image_url"] == "http://img/base1-4-NEW"
        meta = {m["key"]: m["value"] for m in after["app_metadata"]}
        assert meta["card_data_version"] == "2"

        protected_after = _protected_snapshot(db_path)
        assert protected_after == protected_before

    def test_midmerge_failure_restores_reference_and_protects_user_data(self, db, monkeypatch):
        engine, db_path = db
        full_before = _snapshot_all(db_path)
        protected_before = _protected_snapshot(db_path)

        manifest, files = _standard_remote(data_version=2)
        updater, session = _make_updater(db, manifest, files)

        original_merge = updater._merge

        def exploding_merge(downloaded, species_by_dex):
            original_merge(downloaded, species_by_dex)
            raise RuntimeError("boom during merge")

        monkeypatch.setattr(updater, "_merge", exploding_merge)
        try:
            result = updater.update_card_data()
        finally:
            session.close()

        assert result.status is UpdateResultStatus.DATABASE_UPDATE_FAILED
        assert _snapshot_all(db_path) == full_before
        assert _protected_snapshot(db_path) == protected_before
        assert get_local_card_data_version(Session(engine)) == 1


# ===========================================================================
# Never deletes existing cards/sets
# ===========================================================================

class TestNeverDeletes:
    def test_set_absent_from_remote_is_retained(self, db):
        engine, db_path = db
        me55 = _set_payload("me55", "30th", "Mega", [
            _card("me55-1", "1", dex=25, species="pikachu"),
        ])
        manifest, files = _build_remote({"me55": me55}, data_version=2)
        updater, session = _make_updater(db, manifest, files)
        try:
            result = updater.update_card_data()
        finally:
            session.close()
        assert result.status is UpdateResultStatus.UPDATED
        after = _snapshot_all(db_path)
        set_ids = {s["api_set_id"] for s in after["sets"]}
        card_ids = {c["api_card_id"] for c in after["cards"]}
        assert "base1" in set_ids
        assert {"base1-58", "base1-4"} <= card_ids
        assert "me55" in set_ids


# ===========================================================================
# validate_set_payload direct unit tests
# ===========================================================================

class TestValidateSetPayloadDirect:
    def test_valid_passes(self):
        payload = _set_payload("me55", "30th", "Mega", [
            _card("me55-1", "1", dex=25, species="pikachu"),
            _card("me55-2", "2", dex=None, species=None),
        ])
        assert validate_set_payload(payload, "me55") is payload

    def test_wrong_set_id(self):
        payload = _set_payload("me55", "30th", "Mega", [])
        with pytest.raises(SetValidationError):
            validate_set_payload(payload, "different")

    def test_duplicate_card_id(self):
        payload = _set_payload("me55", "30th", "Mega", [
            _card("me55-1", "1", dex=25, species="pikachu"),
            _card("me55-1", "2", dex=6, species="charizard"),
        ])
        with pytest.raises(SetValidationError):
            validate_set_payload(payload, "me55")

    def test_pokemon_without_species_name_rejected(self):
        payload = _set_payload("me55", "30th", "Mega", [
            _card("me55-1", "1", dex=25, species=None),
        ])
        with pytest.raises(SetValidationError):
            validate_set_payload(payload, "me55")

    def test_trainer_with_species_name_rejected(self):
        payload = _set_payload("me55", "30th", "Mega", [
            _card("me55-1", "1", dex=None, species="pikachu"),
        ])
        with pytest.raises(SetValidationError):
            validate_set_payload(payload, "me55")

    def test_bad_release_date_rejected(self):
        payload = _set_payload("me55", "30th", "Mega", [], release_date="16/09/2026")
        with pytest.raises(SetValidationError):
            validate_set_payload(payload, "me55")

    def test_negative_dex_rejected(self):
        payload = _set_payload("me55", "30th", "Mega", [
            _card("me55-1", "1", dex=-3, species="x"),
        ])
        with pytest.raises(SetValidationError):
            validate_set_payload(payload, "me55")
