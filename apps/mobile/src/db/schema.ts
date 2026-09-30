/**
 * Local SQLite schema + migrations for PullDex mobile.
 *
 * Offline-first: the database lives entirely on the device (expo-sqlite). It is
 * independent of the desktop `%LOCALAPPDATA%` database and of any backend.
 *
 * Migrations are versioned via `PRAGMA user_version`. Each migration is a pure
 * SQL step; `runMigrations` applies any not-yet-applied steps in order. This is
 * a proper schema/migration approach (not JSON blobs).
 *
 * Tables mirror the desktop catalogue + collection model so the shared card
 * model is reused:
 *   - pokemon_species, sets, cards  → catalogue (seeded from bundled snapshot)
 *   - collection                    → user data (single implicit local profile)
 */

import type { SQLiteDatabase } from "expo-sqlite";

export const DATABASE_NAME = "pulldex.db";

/** Current target schema version. Bump when adding a migration below. */
export const TARGET_USER_VERSION = 1;

interface Migration {
  version: number;
  statements: string[];
}

/**
 * Ordered migrations. Migration N brings the DB from version N-1 to N.
 */
const MIGRATIONS: Migration[] = [
  {
    version: 1,
    statements: [
      `CREATE TABLE IF NOT EXISTS pokemon_species (
        id INTEGER PRIMARY KEY,
        national_dex_number INTEGER NOT NULL,
        name TEXT NOT NULL,
        generation INTEGER
      );`,
      `CREATE UNIQUE INDEX IF NOT EXISTS ix_species_dex ON pokemon_species(national_dex_number);`,
      `CREATE INDEX IF NOT EXISTS ix_species_name ON pokemon_species(name);`,

      `CREATE TABLE IF NOT EXISTS sets (
        id INTEGER PRIMARY KEY,
        api_set_id TEXT,
        name TEXT NOT NULL,
        series TEXT,
        release_date TEXT,
        is_promo INTEGER NOT NULL DEFAULT 0
      );`,

      `CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY,
        api_card_id TEXT,
        pokemon_species_id INTEGER,
        set_id INTEGER,
        card_number TEXT,
        rarity TEXT,
        variant TEXT,
        image_url TEXT
      );`,
      `CREATE INDEX IF NOT EXISTS ix_cards_species ON cards(pokemon_species_id);`,
      `CREATE INDEX IF NOT EXISTS ix_cards_set ON cards(set_id);`,

      // Collection: single implicit local profile (no profile_id on mobile MVP).
      // A species is owned if a species-level row exists OR any card-level row
      // exists for a card of that species — matching desktop semantics.
      `CREATE TABLE IF NOT EXISTS collection (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pokemon_species_id INTEGER,
        card_id INTEGER,
        quantity INTEGER NOT NULL DEFAULT 1,
        is_binder_card INTEGER NOT NULL DEFAULT 0
      );`,
      `CREATE INDEX IF NOT EXISTS ix_collection_species ON collection(pokemon_species_id);`,
      `CREATE INDEX IF NOT EXISTS ix_collection_card ON collection(card_id);`,
      // Full UNIQUE indexes so ON CONFLICT upserts can target them. In SQLite,
      // multiple NULLs are considered distinct, so:
      //   - uq_collection_card: at most one row per specific card; unlimited
      //     species-level rows (card_id NULL) are unaffected.
      //   - uq_collection_species: at most one species-level row per species;
      //     card-level rows (pokemon_species_id NULL here) are unaffected.
      // Card-level rows do not set pokemon_species_id (species is derived via
      // the cards table), so the two indexes never conflict with each other.
      `CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_card ON collection(card_id);`,
      `CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_species ON collection(pokemon_species_id);`,

      // Lightweight key/value metadata (e.g. catalogue snapshot version).
      `CREATE TABLE IF NOT EXISTS app_meta (
        key TEXT PRIMARY KEY,
        value TEXT
      );`,
    ],
  },
];

async function getUserVersion(db: SQLiteDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ user_version: number }>("PRAGMA user_version;");
  return row?.user_version ?? 0;
}

async function setUserVersion(db: SQLiteDatabase, version: number): Promise<void> {
  // PRAGMA doesn't accept bound params; version is an internal integer.
  await db.execAsync(`PRAGMA user_version = ${version};`);
}

/**
 * Apply any pending migrations. Safe to call on every launch (idempotent).
 * Returns the final schema version.
 */
export async function runMigrations(db: SQLiteDatabase): Promise<number> {
  await db.execAsync("PRAGMA journal_mode = WAL;");
  await db.execAsync("PRAGMA foreign_keys = ON;");

  let current = await getUserVersion(db);

  for (const migration of MIGRATIONS) {
    if (migration.version <= current) continue;
    await db.withExclusiveTransactionAsync(async (tx) => {
      for (const stmt of migration.statements) {
        await tx.execAsync(stmt);
      }
    });
    await setUserVersion(db, migration.version);
    current = migration.version;
  }

  return current;
}
