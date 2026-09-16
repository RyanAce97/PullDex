"""Stage A tests for explicit set promo classification (`Set.is_promo`).

Covers:
  * Alembic migration adds `is_promo` to an existing DB, defaulting existing
    rows to False, without touching user data.
  * The card-data updater persists `is_promo` when creating a set (promo and
    non-promo), and when an existing set's classification changes.
  * User data (collection/profiles/species) is untouched by such an update.
  * Set-payload validation requires a boolean `is_promo`; a legacy payload
    missing it is rejected as INVALID_SET_DATA (safe, no partial import), and
    the merge itself defaults a missing value to False (defence in depth).

No network access (fetchers injected). No live DB (temp on-disk SQLite).
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
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
    SetValidationError,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_set_model_defaults_is_promo_false():
    s = Set(api_set_id="x", name="X", series="Other")
    assert s.is_promo is False


# ===========================================================================
# Alembic migration from an existing (pre-is_promo) database
# ===========================================================================

class TestMigration:
    def test_migration_adds_column_defaults_false_preserves_user_data(self, tmp_path):
        db_path = tmp_path / "migrate.db"
        url = f"sqlite:///{db_path}"

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE pokemon_species (id INTEGER PRIMARY KEY, national_dex_number INTEGER, name TEXT, generation INTEGER);
            CREATE TABLE sets (id INTEGER PRIMARY KEY, api_set_id TEXT, name TEXT, series TEXT, release_date DATE);
            CREATE TABLE cards (id INTEGER PRIMARY KEY, api_card_id TEXT, pokemon_species_id INTEGER, set_id INTEGER, card_number TEXT, rarity TEXT, variant TEXT, image_url TEXT);
            CREATE TABLE collection (id INTEGER PRIMARY KEY, profile_id INTEGER, pokemon_species_id INTEGER, card_id INTEGER, quantity INTEGER, is_binder_card BOOLEAN);
            CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT, is_active BOOLEAN, binder_rows INTEGER, binder_columns INTEGER, binder_sort TEXT);
            CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        cur.execute("INSERT INTO pokemon_species (id,national_dex_number,name,generation) VALUES (1,25,'pikachu',1)")
        cur.execute("INSERT INTO sets (id,api_set_id,name,series) VALUES (1,'base1','Base','Base')")
        cur.execute("INSERT INTO sets (id,api_set_id,name,series) VALUES (2,'basep','Wizards Black Star Promos','Base')")
        cur.execute("INSERT INTO cards (id,api_card_id,set_id,pokemon_species_id,card_number) VALUES (1,'base1-58',1,1,'58')")
        cur.execute("INSERT INTO profiles (id,name,is_active,binder_rows,binder_columns,binder_sort) VALUES (1,'Ryan',1,5,4,'dex_number')")
        cur.execute("INSERT INTO collection (id,profile_id,card_id,quantity,is_binder_card) VALUES (1,1,1,3,1)")
        cur.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        cur.execute("INSERT INTO alembic_version (version_num) VALUES ('e1f3a5c7d9b2')")
        conn.commit()
        conn.close()

        def snap():
            c = sqlite3.connect(str(db_path)); c.row_factory = sqlite3.Row
            out = {
                "collection": [dict(r) for r in c.execute("SELECT * FROM collection ORDER BY id")],
                "profiles": [dict(r) for r in c.execute("SELECT * FROM profiles ORDER BY id")],
                "species": [dict(r) for r in c.execute("SELECT * FROM pokemon_species ORDER BY id")],
            }
            c.close(); return out
        before = snap()

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(BACKEND_DIR),
            env={**os.environ, "DATABASE_URL": url},
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"alembic failed: {result.stderr}\n{result.stdout}"

        c = sqlite3.connect(str(db_path)); c.row_factory = sqlite3.Row
        cols = {r[1] for r in c.execute("PRAGMA table_info(sets)")}
        assert "is_promo" in cols
        promo_vals = {r["api_set_id"]: r["is_promo"] for r in c.execute("SELECT api_set_id, is_promo FROM sets")}
        c.close()
        assert promo_vals["base1"] == 0
        assert promo_vals["basep"] == 0  # migration alone does not classify

        assert snap() == before

    def test_migration_downgrade_removes_column(self, tmp_path):
        db_path = tmp_path / "down.db"
        url = f"sqlite:///{db_path}"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            "CREATE TABLE sets (id INTEGER PRIMARY KEY, api_set_id TEXT, name TEXT, series TEXT, release_date DATE);"
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);"
            "INSERT INTO alembic_version VALUES ('e1f3a5c7d9b2');"
        )
        conn.commit(); conn.close()
        env = {**os.environ, "DATABASE_URL": url}
        up = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                            cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True)
        assert up.returncode == 0, up.stderr
        c = sqlite3.connect(str(db_path))
        assert "is_promo" in {r[1] for r in c.execute("PRAGMA table_info(sets)")}
        c.close()
        down = subprocess.run([sys.executable, "-m", "alembic", "downgrade", "-1"],
                              cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True)
        assert down.returncode == 0, down.stderr
        c = sqlite3.connect(str(db_path))
        assert "is_promo" not in {r[1] for r in c.execute("PRAGMA table_info(sets)")}
        c.close()


# ===========================================================================
# Updater: persist is_promo (create promo / non-promo / change)
# ===========================================================================

MANIFEST_URL = "https://example.test/main/manifest.json"


def _set_payload(set_id, name, series, cards, release_date="2020-01-01", is_promo=False):
    return {
        "set": {"id": set_id, "name": name, "series": series,
                "release_date": release_date, "is_promo": is_promo},
        "card_count": len(cards),
        "cards": cards,
    }


def _card(api_card_id, number, dex=None, species=None):
    return {
        "api_card_id": api_card_id, "card_number": number, "rarity": None,
        "variant": None, "image_url": "http://img/x",
        "national_dex_number": dex, "species_name": species,
    }


def _canon(payload):
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _build_remote(sets, data_version=2):
    files, manifest_sets, total = {}, [], 0
    for sid, payload in sets.items():
        raw = _canon(payload)
        files[f"sets/{sid}.json"] = raw
        total += payload["card_count"]
        manifest_sets.append({
            "id": sid, "name": payload["set"]["name"], "series": payload["set"]["series"],
            "release_date": payload["set"]["release_date"], "file": f"sets/{sid}.json",
            "card_count": payload["card_count"], "version": 1,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "is_promo": payload["set"].get("is_promo", False),
        })
    manifest = {"schema_version": 1, "data_version": data_version, "updated_at": "x",
                "set_count": len(manifest_sets), "card_count": total, "sets": manifest_sets}
    return manifest, files


def _fetchers(manifest, files):
    def mf(url, timeout): return json.dumps(manifest)
    def sf(url, timeout): return files["sets/" + url.rsplit("/", 1)[1]]
    return mf, sf


@pytest.fixture(name="db")
def db_fixture(tmp_path):
    db_path = tmp_path / "pulldex.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(PokemonSpecies(national_dex_number=25, name="pikachu", generation=1))
        s.add(AppMetadata(key="card_data_version", value="1"))
        s.add(Profile(name="Ryan", is_active=True, binder_rows=5, binder_columns=4, binder_sort="dex_number"))
        s.commit()
    yield engine, db_path
    engine.dispose()


def _updater(engine, db_path, manifest, files):
    session = Session(engine)
    mf, sf = _fetchers(manifest, files)
    u = CardDataUpdater(
        session=session, manifest_url=MANIFEST_URL, supported_schema_version=1, timeout=1.0,
        manifest_fetcher=mf, set_fetcher=sf,
        backup_factory=lambda: create_pre_update_backup(db_path=db_path),
    )
    return u, session


class TestUpdaterPersistsIsPromo:
    def test_creates_promo_and_non_promo_sets(self, db):
        engine, db_path = db
        promo = _set_payload("basep", "Wizards Black Star Promos", "Base",
                             [_card("basep-1", "1", 25, "pikachu")], is_promo=True)
        normal = _set_payload("base1", "Base", "Base",
                              [_card("base1-58", "58", 25, "pikachu")], is_promo=False)
        manifest, files = _build_remote({"basep": promo, "base1": normal}, data_version=2)
        u, s = _updater(engine, db_path, manifest, files)
        try:
            r = u.update_card_data()
        finally:
            s.close()
        assert r.status is UpdateResultStatus.UPDATED
        with Session(engine) as s:
            assert s.exec(select(Set).where(Set.api_set_id == "basep")).first().is_promo is True
            assert s.exec(select(Set).where(Set.api_set_id == "base1")).first().is_promo is False

    def test_changes_existing_set_promo_classification(self, db):
        engine, db_path = db
        with Session(engine) as s:
            s.add(Set(api_set_id="mcd22", name="McDonald's Collection 2022",
                      series="Other", is_promo=False))
            s.commit()
        payload = _set_payload("mcd22", "McDonald's Collection 2022", "Other",
                               [_card("mcd22-7", "7", 25, "pikachu")], is_promo=True)
        manifest, files = _build_remote({"mcd22": payload}, data_version=2)
        u, s = _updater(engine, db_path, manifest, files)
        try:
            r = u.update_card_data()
        finally:
            s.close()
        assert r.status is UpdateResultStatus.UPDATED
        assert r.sets_updated == 1
        with Session(engine) as s:
            assert s.exec(select(Set).where(Set.api_set_id == "mcd22")).first().is_promo is True

    def test_update_does_not_touch_user_data(self, db):
        engine, db_path = db
        with Session(engine) as s:
            prof = s.exec(select(Profile)).first()
            s.add(Collection(profile_id=prof.id, pokemon_species_id=1, quantity=2, is_binder_card=False))
            s.commit()

        def snap():
            c = sqlite3.connect(str(db_path)); c.row_factory = sqlite3.Row
            out = {
                "collection": [dict(r) for r in c.execute("SELECT * FROM collection ORDER BY id")],
                "profiles": [dict(r) for r in c.execute("SELECT * FROM profiles ORDER BY id")],
                "species": [dict(r) for r in c.execute("SELECT * FROM pokemon_species ORDER BY id")],
            }
            c.close(); return out
        before = snap()

        promo = _set_payload("basep", "Wizards Black Star Promos", "Base",
                             [_card("basep-1", "1", 25, "pikachu")], is_promo=True)
        manifest, files = _build_remote({"basep": promo}, data_version=2)
        u, s = _updater(engine, db_path, manifest, files)
        try:
            u.update_card_data()
        finally:
            s.close()
        assert snap() == before


# ===========================================================================
# Validation: require boolean is_promo; legacy payloads handled safely
# ===========================================================================

class TestValidation:
    def test_valid_boolean_passes(self):
        p = _set_payload("basep", "Wizards Black Star Promos", "Base",
                         [_card("basep-1", "1", 25, "pikachu")], is_promo=True)
        assert validate_set_payload(p, "basep") is p

    def test_missing_is_promo_rejected(self):
        p = _set_payload("base1", "Base", "Base", [_card("base1-1", "1", 25, "pikachu")])
        del p["set"]["is_promo"]
        with pytest.raises(SetValidationError):
            validate_set_payload(p, "base1")

    def test_non_boolean_is_promo_rejected(self):
        p = _set_payload("base1", "Base", "Base", [_card("base1-1", "1", 25, "pikachu")])
        p["set"]["is_promo"] = "true"
        with pytest.raises(SetValidationError):
            validate_set_payload(p, "base1")

    def test_legacy_payload_missing_is_promo_fails_update_safely(self, db):
        engine, db_path = db
        p = _set_payload("base1", "Base", "Base", [_card("base1-1", "1", 25, "pikachu")])
        del p["set"]["is_promo"]
        manifest, files = _build_remote({"base1": p}, data_version=2)
        u, s = _updater(engine, db_path, manifest, files)
        try:
            r = u.update_card_data()
        finally:
            s.close()
        assert r.status is UpdateResultStatus.INVALID_SET_DATA
        with Session(engine) as s:
            assert s.exec(select(Set).where(Set.api_set_id == "base1")).first() is None

    def test_merge_defaults_missing_is_promo_to_false(self, db):
        engine, db_path = db
        u, s = _updater(engine, db_path, *_build_remote({}, data_version=2))
        try:
            from app.services.card_data_updater_service import _DownloadedSet
            payload = {"set": {"id": "base1", "name": "Base", "series": "Base",
                               "release_date": "1999-01-09"},
                       "card_count": 0, "cards": []}
            counts = u._merge([_DownloadedSet(manifest_entry={"id": "base1"}, payload=payload)], {})
            s.commit()
            assert counts.sets_created == 1
            created = s.exec(select(Set).where(Set.api_set_id == "base1")).first()
            assert created.is_promo is False
        finally:
            s.close()
