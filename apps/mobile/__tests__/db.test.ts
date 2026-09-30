import * as fs from "fs";
import * as os from "os";
import * as path from "path";

import { openDatabaseAsync, type SQLiteDatabase } from "expo-sqlite";
import { runMigrations, TARGET_USER_VERSION } from "../src/db/schema";
import { seedCatalogue, catalogueNeedsSeed } from "../src/db/seed";
import {
  getProgress,
  getSpeciesOwnership,
  markCardOwned,
  removeCardOwnership,
  markSpeciesOwned,
  toggleSpeciesOwnership,
  isSpeciesOwned,
  searchCards,
  getCardsForSpecies,
  getOwnedCardIds,
  setBinderCard,
  getPokedexBinderPage,
} from "../src/db/repository";

async function freshDb(): Promise<SQLiteDatabase> {
  const db = await openDatabaseAsync(":memory:");
  await runMigrations(db);
  await seedCatalogue(db);
  return db;
}

describe("schema + migrations", () => {
  it("creates all tables and reaches target version", async () => {
    const db = await openDatabaseAsync(":memory:");
    const version = await runMigrations(db);
    expect(version).toBe(TARGET_USER_VERSION);

    const tables = await db.getAllAsync<{ name: string }>(
      "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;",
    );
    const names = tables.map((t) => t.name);
    expect(names).toEqual(expect.arrayContaining(["pokemon_species", "sets", "cards", "collection", "app_meta"]));
  });

  it("is idempotent when run twice", async () => {
    const db = await openDatabaseAsync(":memory:");
    await runMigrations(db);
    const v2 = await runMigrations(db);
    expect(v2).toBe(TARGET_USER_VERSION);
  });
});

describe("catalogue seeding", () => {
  it("seeds species/sets/cards from the snapshot", async () => {
    const db = await freshDb();
    const species = await db.getFirstAsync<{ n: number }>("SELECT COUNT(*) AS n FROM pokemon_species;");
    const cards = await db.getFirstAsync<{ n: number }>("SELECT COUNT(*) AS n FROM cards;");
    expect(species?.n).toBe(3);
    expect(cards?.n).toBe(4);
  });

  it("is idempotent (no reseed when version matches)", async () => {
    const db = await freshDb();
    expect(await catalogueNeedsSeed(db)).toBe(false);
    await seedCatalogue(db); // no-op
    const cards = await db.getFirstAsync<{ n: number }>("SELECT COUNT(*) AS n FROM cards;");
    expect(cards?.n).toBe(4);
  });
});

describe("collection ownership (card level)", () => {
  it("marks a card owned and derives species ownership", async () => {
    const db = await freshDb();
    expect(await isSpeciesOwned(db, 1)).toBe(false);
    await markCardOwned(db, 100); // bulbasaur card
    expect(await isSpeciesOwned(db, 1)).toBe(true);

    const ids = await getOwnedCardIds(db);
    expect(ids.has(100)).toBe(true);
  });

  it("increments quantity idempotently on repeated add", async () => {
    const db = await freshDb();
    await markCardOwned(db, 100, 1);
    await markCardOwned(db, 100, 2);
    const row = await db.getFirstAsync<{ quantity: number; n: number }>(
      "SELECT quantity, COUNT(*) AS n FROM collection WHERE card_id = 100;",
    );
    expect(row?.n).toBe(1); // still a single row
    expect(row?.quantity).toBe(3);
  });

  it("removes card ownership", async () => {
    const db = await freshDb();
    await markCardOwned(db, 100);
    await removeCardOwnership(db, 100);
    expect(await isSpeciesOwned(db, 1)).toBe(false);
  });
});

describe("collection ownership (species level) + toggle", () => {
  it("marks species owned without a specific card", async () => {
    const db = await freshDb();
    await markSpeciesOwned(db, 4);
    expect(await isSpeciesOwned(db, 4)).toBe(true);
  });

  it("toggles ownership on and off", async () => {
    const db = await freshDb();
    expect(await toggleSpeciesOwnership(db, 25)).toBe(true);
    expect(await isSpeciesOwned(db, 25)).toBe(true);
    expect(await toggleSpeciesOwnership(db, 25)).toBe(false);
    expect(await isSpeciesOwned(db, 25)).toBe(false);
  });

  it("removing species ownership also clears its card entries", async () => {
    const db = await freshDb();
    await markCardOwned(db, 102); // pikachu sv1
    await markCardOwned(db, 103); // pikachu promo
    expect(await isSpeciesOwned(db, 25)).toBe(true);
    await toggleSpeciesOwnership(db, 25); // owned -> remove all
    expect(await isSpeciesOwned(db, 25)).toBe(false);
    const ids = await getOwnedCardIds(db);
    expect(ids.has(102)).toBe(false);
    expect(ids.has(103)).toBe(false);
  });
});

describe("progress + species ownership list", () => {
  it("reports progress out of the full national dex", async () => {
    const db = await freshDb();
    await markCardOwned(db, 100);
    await markSpeciesOwned(db, 4);
    const progress = await getProgress(db);
    expect(progress.totalSpecies).toBe(1025);
    expect(progress.ownedSpecies).toBe(2);
  });

  it("lists species with derived ownership + owned card count", async () => {
    const db = await freshDb();
    await markCardOwned(db, 102);
    await markCardOwned(db, 103);
    const rows = await getSpeciesOwnership(db);
    const pika = rows.find((r) => r.species.id === 25);
    expect(pika?.owned).toBe(true);
    expect(pika?.ownedCardCount).toBe(2);
    const bulba = rows.find((r) => r.species.id === 1);
    expect(bulba?.owned).toBe(false);
  });
});

describe("card search + queries", () => {
  it("searches by name, set, code, number", async () => {
    const db = await freshDb();
    expect((await searchCards(db, "pikachu")).length).toBe(2);
    expect((await searchCards(db, "Scarlet")).length).toBe(3);
    expect((await searchCards(db, "svp")).length).toBe(1);
    expect((await searchCards(db, "001")).length).toBe(1);
  });

  it("returns cards for a species with set context + promo flag", async () => {
    const db = await freshDb();
    const cards = await getCardsForSpecies(db, 25);
    expect(cards.length).toBe(2);
    const promo = cards.find((c) => c.set_code === "svp");
    expect(promo?.is_promo).toBe(true);
  });
});

describe("pokedex binder page (derived)", () => {
  it("builds a page with owned/has_card/representative + no concept for unowned", async () => {
    const db = await freshDb();
    await markCardOwned(db, 100); // bulbasaur owned w/ card
    await markSpeciesOwned(db, 4); // charmander owned, no card

    const page = await getPokedexBinderPage(db, 1, 4); // dex 1..4
    expect(page.binder_type).toBe("POKEDEX");
    expect(page.total_species).toBe(1025);

    const s1 = page.slots.find((s) => s.dex_number === 1)!;
    expect(s1.owned).toBe(true);
    expect(s1.has_card).toBe(true);
    expect(s1.card?.id).toBe(100);

    const s4 = page.slots.find((s) => s.dex_number === 4)!;
    expect(s4.owned).toBe(true);
    expect(s4.has_card).toBe(false);
    expect(s4.card).toBeNull();

    const s2 = page.slots.find((s) => s.dex_number === 2)!;
    expect(s2.owned).toBe(false);
    expect(s2.card).toBeNull(); // never a concept card in the Pokédex binder
  });

  it("respects the is_binder_card representative selection", async () => {
    const db = await freshDb();
    await markCardOwned(db, 102); // pikachu sv1
    await markCardOwned(db, 103); // pikachu promo
    await setBinderCard(db, 103); // choose promo as representative

    const page = await getPokedexBinderPage(db, 7, 4); // dex 25..28
    const s25 = page.slots.find((s) => s.dex_number === 25)!;
    expect(s25.has_card).toBe(true);
    expect(s25.card?.id).toBe(103);
  });
});

describe("persistence across reopen (file-backed)", () => {
  it("retains collection data after closing and reopening the DB file", async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pulldex-mobile-"));
    const file = path.join(dir, "persist.db");
    try {
      const db1 = await openDatabaseAsync(file);
      await runMigrations(db1);
      await seedCatalogue(db1);
      await markCardOwned(db1, 100);
      (db1 as unknown as { closeSync(): void }).closeSync();

      // Reopen: migrations no-op, catalogue already seeded, ownership persists.
      const db2 = await openDatabaseAsync(file);
      await runMigrations(db2);
      await seedCatalogue(db2);
      expect(await isSpeciesOwned(db2, 1)).toBe(true);
      const ids = await getOwnedCardIds(db2);
      expect(ids.has(100)).toBe(true);
      (db2 as unknown as { closeSync(): void }).closeSync();
    } finally {
      // Best-effort cleanup; Windows may briefly hold the file lock after close.
      try {
        fs.rmSync(dir, { recursive: true, force: true });
      } catch {
        /* ignore temp-dir cleanup races on Windows */
      }
    }
  });
});
