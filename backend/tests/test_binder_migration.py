"""Migration test for the binders/binder_placements tables.

Verifies that upgrading a database that contains existing profiles (at the
previous head ``f2a4b6c8d0e1``) to the new head ``a7d3f1b9c2e4``:

- creates the ``binders`` and ``binder_placements`` tables,
- seeds exactly one default POKEDEX binder named "Pokédex Binder" per profile,
- copies each profile's ``binder_rows`` / ``binder_columns`` / ``binder_sort``,
- leaves ``collection`` (including ``is_binder_card``) untouched,
- and that downgrade cleanly drops the two tables.

The test operates entirely on an isolated temporary SQLite file. It NEVER
touches the dev or live databases.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.config import settings


BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_DIR = BACKEND_DIR / "alembic"
PREV_HEAD = "f2a4b6c8d0e1"
NEW_HEAD = "a7d3f1b9c2e4"


def _alembic_config(db_path: Path) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    # Use forward slashes for a valid SQLite URL on all platforms.
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """A fresh temporary SQLite DB path (isolated; never the real DB).

    ``alembic/env.py`` overrides the config URL with ``settings.database_url``,
    so we point that at the temp file for the duration of the test. This keeps
    the migration completely isolated from the dev/live databases.
    """
    db_path = tmp_path / "migtest.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path.as_posix()}")
    return db_path


def _seed_prev_head_schema(db_path: Path):
    """Upgrade an empty DB to the PREVIOUS head, then insert test profiles."""
    cfg = _alembic_config(db_path)
    command.upgrade(cfg, PREV_HEAD)

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    # Start from a known-empty set of profiles. The profiles migration seeds a
    # default 'Default' profile; clear it so this test controls the exact set.
    cur.execute("DELETE FROM collection")
    cur.execute("DELETE FROM profiles")
    # Two profiles with distinct layouts to prove per-profile copying.
    cur.execute(
        "INSERT INTO profiles (id, name, is_active, created_at, binder_rows, binder_columns, binder_sort) "
        "VALUES (1, 'Default', 1, '2026-01-01 00:00:00', 3, 3, 'dex_number')"
    )
    cur.execute(
        "INSERT INTO profiles (id, name, is_active, created_at, binder_rows, binder_columns, binder_sort) "
        "VALUES (2, 'Second', 0, '2026-01-02 00:00:00', 4, 5, 'recent')"
    )
    # A species + card + collection entry with is_binder_card to prove preservation.
    cur.execute(
        "INSERT INTO pokemon_species (national_dex_number, name, generation) VALUES (1, 'bulbasaur', 1)"
    )
    species_id = cur.lastrowid
    cur.execute("INSERT INTO sets (api_set_id, name, series) VALUES ('sv1', 'SV', 'SV')")
    set_id = cur.lastrowid
    cur.execute(
        "INSERT INTO cards (api_card_id, pokemon_species_id, set_id, card_number) "
        "VALUES ('sv1-1', ?, ?, '001/198')",
        (species_id, set_id),
    )
    card_id = cur.lastrowid
    cur.execute(
        "INSERT INTO collection (profile_id, card_id, quantity, is_binder_card) VALUES (1, ?, 2, 1)",
        (card_id,),
    )
    conn.commit()
    conn.close()


def test_migration_seeds_default_pokedex_binder_per_profile(temp_db):
    _seed_prev_head_schema(temp_db)

    cfg = _alembic_config(temp_db)
    command.upgrade(cfg, NEW_HEAD)

    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()

    # Version advanced.
    cur.execute("SELECT version_num FROM alembic_version")
    assert cur.fetchone()[0] == NEW_HEAD

    # Tables exist.
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='binders'")
    assert cur.fetchone() is not None
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='binder_placements'")
    assert cur.fetchone() is not None

    # Exactly one binder per profile.
    cur.execute("SELECT COUNT(*) FROM binders")
    assert cur.fetchone()[0] == 2

    # Profile 1: 3x3 dex_number, default, POKEDEX, correct name.
    cur.execute(
        "SELECT name, binder_type, rows, columns, sort_order, is_default "
        "FROM binders WHERE profile_id = 1"
    )
    row = cur.fetchone()
    assert row[0] == "Pokédex Binder"
    assert row[1] == "POKEDEX"
    assert (row[2], row[3], row[4]) == (3, 3, "dex_number")
    assert row[5] == 1

    # Profile 2: 4x5 recent layout copied.
    cur.execute(
        "SELECT rows, columns, sort_order, is_default FROM binders WHERE profile_id = 2"
    )
    row = cur.fetchone()
    assert (row[0], row[1], row[2]) == (4, 5, "recent")
    assert row[3] == 1

    # Collection preserved, including is_binder_card.
    cur.execute("SELECT COUNT(*) FROM collection")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT COUNT(*) FROM collection WHERE is_binder_card = 1")
    assert cur.fetchone()[0] == 1

    # No placements seeded.
    cur.execute("SELECT COUNT(*) FROM binder_placements")
    assert cur.fetchone()[0] == 0

    conn.close()


def test_migration_downgrade_drops_tables(temp_db):
    _seed_prev_head_schema(temp_db)
    cfg = _alembic_config(temp_db)
    command.upgrade(cfg, NEW_HEAD)
    command.downgrade(cfg, PREV_HEAD)

    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()

    cur.execute("SELECT version_num FROM alembic_version")
    assert cur.fetchone()[0] == PREV_HEAD

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='binders'")
    assert cur.fetchone() is None
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='binder_placements'")
    assert cur.fetchone() is None

    # Data preserved through the round trip.
    cur.execute("SELECT COUNT(*) FROM collection WHERE is_binder_card = 1")
    assert cur.fetchone()[0] == 1

    conn.close()
