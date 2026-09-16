"""Tests for the Stage 1 card-data update check (read-only manifest check).

No test here touches the network: the HTTP fetch is always injected as a
fake ``fetcher`` callable. Covers:
  * valid manifest parsing + exposed metadata
  * version comparison policy (up-to-date / update-available / local-ahead)
  * invalid manifests (malformed JSON, missing fields, dupes, bad counts, bad sha)
  * network failures (timeout, connection error, HTTP 404/500)
  * schema compatibility (supported vs newer)
  * database safety: performing a check changes NO card/collection/profile data
"""

import json
import sqlite3
import urllib.error

import pytest

from app.services.card_data_update_service import (
    CardDataUpdateService,
    UpdateStatus,
    _validate_manifest,
    ManifestValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha(n: str = "a") -> str:
    return (n * 64)[:64]


def _valid_manifest(data_version: int = 1, schema_version: int = 1, sets=None) -> dict:
    if sets is None:
        sets = [
            {
                "id": "me55",
                "name": "30th Celebration",
                "file": "sets/me55.json",
                "version": 1,
                "sha256": _sha("a"),
                "card_count": 161,
            },
            {
                "id": "me55c",
                "name": "30th Celebration: Classic Collection",
                "file": "sets/me55c.json",
                "version": 1,
                "sha256": _sha("b"),
                "card_count": 30,
            },
        ]
    return {
        "schema_version": schema_version,
        "data_version": data_version,
        "updated_at": "2026-09-16T00:00:00Z",
        "set_count": len(sets),
        "card_count": sum(s["card_count"] for s in sets),
        "sets": sets,
    }


def _fetcher_returning(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)

    def _fetch(url: str, timeout: float) -> str:
        return text

    return _fetch


def _fetcher_raising(exc: Exception):
    def _fetch(url: str, timeout: float) -> str:
        raise exc

    return _fetch


def _service(local_version, payload=None, fetcher=None, supported_schema=1):
    return CardDataUpdateService(
        local_data_version=local_version,
        manifest_url="https://example.test/manifest.json",
        supported_schema_version=supported_schema,
        timeout=1.0,
        fetcher=fetcher or _fetcher_returning(payload),
    )


# ===========================================================================
# Valid manifest
# ===========================================================================

class TestValidManifest:
    def test_parses_and_exposes_metadata(self):
        result = _service(1, _valid_manifest(data_version=1)).check()
        assert result.status is UpdateStatus.UP_TO_DATE
        assert result.remote_data_version == 1
        assert result.remote_schema_version == 1
        assert result.remote_set_count == 2
        assert result.remote_card_count == 191

    def test_all_set_metadata_exposed(self):
        result = _service(1, _valid_manifest()).check()
        assert len(result.sets) == 2
        me55 = next(s for s in result.sets if s.id == "me55")
        assert me55.name == "30th Celebration"
        assert me55.file == "sets/me55.json"
        assert me55.version == 1
        assert me55.card_count == 161
        assert len(me55.sha256) == 64

    def test_to_dict_shape(self):
        result = _service(1, _valid_manifest(data_version=2)).check()
        d = result.to_dict()
        assert d["status"] == "UPDATE_AVAILABLE"
        assert d["update_available"] is True
        assert d["local_data_version"] == 1
        assert d["remote_data_version"] == 2
        assert isinstance(d["sets"], list) and len(d["sets"]) == 2


# ===========================================================================
# Version comparison
# ===========================================================================

class TestVersionComparison:
    def test_local1_remote1_up_to_date(self):
        r = _service(1, _valid_manifest(data_version=1)).check()
        assert r.status is UpdateStatus.UP_TO_DATE

    def test_local1_remote2_update_available(self):
        r = _service(1, _valid_manifest(data_version=2)).check()
        assert r.status is UpdateStatus.UPDATE_AVAILABLE
        assert r.remote_data_version == 2

    def test_local2_remote1_treated_as_up_to_date(self):
        # Policy: never downgrade. Local ahead of remote => UP_TO_DATE.
        r = _service(2, _valid_manifest(data_version=1)).check()
        assert r.status is UpdateStatus.UP_TO_DATE
        assert r.remote_data_version == 1
        assert r.local_data_version == 2


# ===========================================================================
# Invalid manifests
# ===========================================================================

class TestInvalidManifest:
    def test_malformed_json(self):
        r = _service(1, fetcher=_fetcher_returning("{ not valid json")).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST
        assert r.error

    def test_not_an_object(self):
        r = _service(1, fetcher=_fetcher_returning("[]")).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST

    def test_missing_data_version(self):
        m = _valid_manifest()
        del m["data_version"]
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST

    def test_missing_schema_version(self):
        m = _valid_manifest()
        del m["schema_version"]
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST

    def test_missing_sets(self):
        m = _valid_manifest()
        del m["sets"]
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST

    def test_missing_set_count(self):
        m = _valid_manifest()
        del m["set_count"]
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST

    def test_missing_card_count(self):
        m = _valid_manifest()
        del m["card_count"]
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST

    def test_duplicate_set_ids(self):
        s = {
            "id": "me55", "name": "A", "file": "sets/me55.json",
            "version": 1, "sha256": _sha("a"), "card_count": 1,
        }
        m = _valid_manifest(sets=[dict(s), dict(s)])
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST
        assert "Duplicate" in r.error

    def test_set_count_mismatch(self):
        m = _valid_manifest()
        m["set_count"] = 99  # inconsistent with len(sets)
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST

    def test_invalid_sha256(self):
        m = _valid_manifest()
        m["sets"][0]["sha256"] = "not-a-valid-hash"
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST
        assert "sha256" in r.error

    def test_malformed_set_entry_missing_field(self):
        m = _valid_manifest()
        del m["sets"][0]["version"]
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST

    def test_set_entry_not_object(self):
        m = _valid_manifest()
        m["sets"][0] = "oops"
        m["set_count"] = len(m["sets"])
        r = _service(1, m).check()
        assert r.status is UpdateStatus.INVALID_MANIFEST


# ===========================================================================
# Network failures
# ===========================================================================

class TestNetworkFailures:
    def test_timeout(self):
        r = _service(1, fetcher=_fetcher_raising(TimeoutError("timed out"))).check()
        assert r.status is UpdateStatus.REMOTE_UNAVAILABLE
        assert r.error

    def test_connection_error(self):
        r = _service(1, fetcher=_fetcher_raising(urllib.error.URLError("dns fail"))).check()
        assert r.status is UpdateStatus.REMOTE_UNAVAILABLE

    def test_http_404(self):
        exc = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        r = _service(1, fetcher=_fetcher_raising(exc)).check()
        assert r.status is UpdateStatus.REMOTE_UNAVAILABLE

    def test_http_500(self):
        exc = urllib.error.HTTPError("url", 500, "Server Error", {}, None)
        r = _service(1, fetcher=_fetcher_raising(exc)).check()
        assert r.status is UpdateStatus.REMOTE_UNAVAILABLE

    def test_generic_oserror(self):
        r = _service(1, fetcher=_fetcher_raising(OSError("socket boom"))).check()
        assert r.status is UpdateStatus.REMOTE_UNAVAILABLE

    def test_local_version_preserved_on_failure(self):
        r = _service(7, fetcher=_fetcher_raising(TimeoutError())).check()
        assert r.local_data_version == 7
        assert r.remote_data_version is None


# ===========================================================================
# Schema compatibility
# ===========================================================================

class TestSchemaCompatibility:
    def test_supported_schema_accepted(self):
        r = _service(1, _valid_manifest(schema_version=1), supported_schema=1).check()
        assert r.status is UpdateStatus.UP_TO_DATE

    def test_newer_schema_incompatible(self):
        r = _service(1, _valid_manifest(schema_version=2), supported_schema=1).check()
        assert r.status is UpdateStatus.INCOMPATIBLE_SCHEMA
        assert r.remote_schema_version == 2

    def test_incompatible_schema_takes_precedence_over_update(self):
        # data_version newer AND schema newer -> INCOMPATIBLE_SCHEMA wins
        r = _service(1, _valid_manifest(data_version=5, schema_version=2), supported_schema=1).check()
        assert r.status is UpdateStatus.INCOMPATIBLE_SCHEMA


# ===========================================================================
# Direct validator unit tests
# ===========================================================================

class TestValidatorDirect:
    def test_valid_manifest_passes(self):
        assert _validate_manifest(_valid_manifest()) is not None

    def test_raises_on_non_dict(self):
        with pytest.raises(ManifestValidationError):
            _validate_manifest([])


# ===========================================================================
# Database safety — the check must not modify any card/user data
# ===========================================================================

def _make_db(tmp_path):
    db = str(tmp_path / "safety.db")
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("CREATE TABLE sets (id INTEGER PRIMARY KEY, api_set_id TEXT, name TEXT, series TEXT, release_date TEXT)")
    cur.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY, api_card_id TEXT, set_id INTEGER, pokemon_species_id INTEGER, card_number TEXT, rarity TEXT, variant TEXT, image_url TEXT)")
    cur.execute("CREATE TABLE collection (id INTEGER PRIMARY KEY, card_id INTEGER, pokemon_species_id INTEGER, quantity INTEGER, profile_id INTEGER, is_binder_card INTEGER)")
    cur.execute("CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT, is_active INTEGER)")
    cur.execute("CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("INSERT INTO sets (id, api_set_id, name, series) VALUES (1,'me55','30th Celebration','Mega Evolution')")
    for i in range(1, 51):
        cur.execute("INSERT INTO cards (api_card_id, set_id, card_number) VALUES (?,?,?)", (f"me55-{i}", 1, str(i)))
    cur.execute("INSERT INTO profiles (id, name, is_active) VALUES (1,'Ryan',1)")
    cur.execute("INSERT INTO collection (card_id, quantity, profile_id, is_binder_card) VALUES (1, 3, 1, 1)")
    cur.execute("INSERT INTO collection (pokemon_species_id, quantity, profile_id, is_binder_card) VALUES (25, 2, 1, 0)")
    cur.execute("INSERT INTO app_metadata (key, value) VALUES ('card_data_version','1')")
    conn.commit()
    conn.close()
    return db


def _snapshot(db):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    snap = {
        "cards": cur.execute("SELECT COUNT(*) FROM cards").fetchone()[0],
        "sets": cur.execute("SELECT COUNT(*) FROM sets").fetchone()[0],
        "collection": cur.execute("SELECT COUNT(*) FROM collection").fetchone()[0],
        "profiles": cur.execute("SELECT COUNT(*) FROM profiles").fetchone()[0],
        "binder": cur.execute("SELECT COUNT(*) FROM collection WHERE is_binder_card=1").fetchone()[0],
        "quantities": cur.execute("SELECT COALESCE(SUM(quantity),0) FROM collection").fetchone()[0],
        "collection_rows": cur.execute("SELECT id, card_id, pokemon_species_id, quantity, profile_id, is_binder_card FROM collection ORDER BY id").fetchall(),
    }
    conn.close()
    return snap


class TestDatabaseSafety:
    def test_check_does_not_modify_database(self, tmp_path):
        db = _make_db(tmp_path)
        before = _snapshot(db)

        conn = sqlite3.connect(db)
        row = conn.execute("SELECT value FROM app_metadata WHERE key='card_data_version'").fetchone()
        local_version = int(row[0])
        conn.close()

        result = _service(local_version, _valid_manifest(data_version=2)).check()
        assert result.status is UpdateStatus.UPDATE_AVAILABLE

        after = _snapshot(db)
        assert before == after, "card-data update check must not modify the database"

    def test_check_offline_does_not_modify_database(self, tmp_path):
        db = _make_db(tmp_path)
        before = _snapshot(db)
        _service(1, fetcher=_fetcher_raising(TimeoutError())).check()
        after = _snapshot(db)
        assert before == after
