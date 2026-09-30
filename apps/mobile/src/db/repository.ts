/**
 * Data-access layer over the local SQLite database.
 *
 * All functions take the SQLiteDatabase handle and return shared domain types.
 * Ownership semantics match desktop: a species is owned if a species-level row
 * exists OR any card-level row exists for a card of that species. Concept
 * status (Free Placement, future) is always derived, never stored.
 */

import type { SQLiteDatabase } from "expo-sqlite";
import {
  buildPokedexBinderPage,
  computeProgress,
  NATIONAL_DEX_COUNT,
  type CardWithContext,
  type CollectionProgress,
  type PokedexBinderPage,
  type PokedexSlotInput,
  type PokemonSpecies,
  type SpeciesOwnership,
} from "@pulldex/shared";

// ---------------------------------------------------------------------------
// Species + ownership
// ---------------------------------------------------------------------------

interface SpeciesOwnershipRow {
  id: number;
  national_dex_number: number;
  name: string;
  generation: number | null;
  owned_card_count: number;
  species_level_owned: number;
}

/**
 * Return every species with derived ownership + owned card count, in dex order.
 * One query drives the Collection list, Pokédex, Card Show Mode, and progress.
 */
export async function getSpeciesOwnership(db: SQLiteDatabase): Promise<SpeciesOwnership[]> {
  const rows = await db.getAllAsync<SpeciesOwnershipRow>(
    `SELECT
       s.id,
       s.national_dex_number,
       s.name,
       s.generation,
       (SELECT COUNT(*) FROM collection col
          JOIN cards c ON col.card_id = c.id
          WHERE c.pokemon_species_id = s.id) AS owned_card_count,
       (SELECT COUNT(*) FROM collection col2
          WHERE col2.pokemon_species_id = s.id AND col2.card_id IS NULL) AS species_level_owned
     FROM pokemon_species s
     ORDER BY s.national_dex_number;`,
  );

  return rows.map((r) => ({
    species: {
      id: r.id,
      national_dex_number: r.national_dex_number,
      name: r.name,
      generation: r.generation,
    },
    owned: r.owned_card_count > 0 || r.species_level_owned > 0,
    ownedCardCount: r.owned_card_count,
  }));
}

export async function getProgress(db: SQLiteDatabase): Promise<CollectionProgress> {
  const row = await db.getFirstAsync<{ owned: number }>(
    `SELECT COUNT(*) AS owned FROM pokemon_species s
     WHERE EXISTS (SELECT 1 FROM collection col WHERE col.pokemon_species_id = s.id AND col.card_id IS NULL)
        OR EXISTS (SELECT 1 FROM collection col JOIN cards c ON col.card_id = c.id WHERE c.pokemon_species_id = s.id);`,
  );
  return computeProgress(row?.owned ?? 0, NATIONAL_DEX_COUNT);
}

export async function getSpeciesById(db: SQLiteDatabase, speciesId: number): Promise<PokemonSpecies | null> {
  const r = await db.getFirstAsync<PokemonSpecies>(
    "SELECT id, national_dex_number, name, generation FROM pokemon_species WHERE id = ?;",
    [speciesId],
  );
  return r ?? null;
}

// ---------------------------------------------------------------------------
// Cards
// ---------------------------------------------------------------------------

interface CardJoinRow {
  id: number;
  api_card_id: string | null;
  card_number: string | null;
  rarity: string | null;
  image_url: string | null;
  variant: string | null;
  pokemon_species_id: number | null;
  pokemon_name: string | null;
  national_dex_number: number | null;
  set_id: number | null;
  set_name: string | null;
  set_code: string | null;
  is_promo: number;
}

function toCardWithContext(r: CardJoinRow): CardWithContext {
  return {
    id: r.id,
    api_card_id: r.api_card_id,
    card_number: r.card_number,
    rarity: r.rarity,
    image_url: r.image_url,
    variant: r.variant,
    pokemon_species_id: r.pokemon_species_id,
    pokemon_name: r.pokemon_name,
    national_dex_number: r.national_dex_number,
    set_id: r.set_id,
    set_name: r.set_name,
    set_code: r.set_code,
    is_promo: !!r.is_promo,
  };
}

const CARD_SELECT = `
  SELECT c.id, c.api_card_id, c.card_number, c.rarity, c.image_url, c.variant,
         c.pokemon_species_id,
         s.name AS pokemon_name, s.national_dex_number,
         c.set_id, st.name AS set_name, st.api_set_id AS set_code,
         COALESCE(st.is_promo, 0) AS is_promo
  FROM cards c
  LEFT JOIN pokemon_species s ON c.pokemon_species_id = s.id
  LEFT JOIN sets st ON c.set_id = st.id`;

export async function getCardsForSpecies(db: SQLiteDatabase, speciesId: number): Promise<CardWithContext[]> {
  const rows = await db.getAllAsync<CardJoinRow>(
    `${CARD_SELECT} WHERE c.pokemon_species_id = ? ORDER BY st.name, c.card_number;`,
    [speciesId],
  );
  return rows.map(toCardWithContext);
}

/** Free-text card search across the whole catalogue (name/set/number/id). */
export async function searchCards(db: SQLiteDatabase, query: string, limit = 100): Promise<CardWithContext[]> {
  const q = query.trim();
  if (q.length === 0) return [];
  const like = `%${q}%`;
  const rows = await db.getAllAsync<CardJoinRow>(
    `${CARD_SELECT}
     WHERE s.name LIKE ? OR st.name LIKE ? OR st.api_set_id LIKE ? OR c.card_number LIKE ? OR c.api_card_id LIKE ?
     ORDER BY s.national_dex_number, st.name, c.card_number
     LIMIT ?;`,
    [like, like, like, like, like, limit],
  );
  return rows.map(toCardWithContext);
}

/** Set of card ids the local collection owns (card-level). Drives concept/owned. */
export async function getOwnedCardIds(db: SQLiteDatabase): Promise<Set<number>> {
  const rows = await db.getAllAsync<{ card_id: number }>(
    "SELECT card_id FROM collection WHERE card_id IS NOT NULL;",
  );
  return new Set(rows.map((r) => r.card_id));
}

// ---------------------------------------------------------------------------
// Collection mutations
// ---------------------------------------------------------------------------

/** Mark a specific card as owned (idempotent; quantity increments). */
export async function markCardOwned(db: SQLiteDatabase, cardId: number, quantity = 1): Promise<void> {
  await db.runAsync(
    `INSERT INTO collection(card_id, quantity, is_binder_card) VALUES(?, ?, 0)
     ON CONFLICT(card_id) DO UPDATE SET quantity = quantity + excluded.quantity;`,
    [cardId, quantity],
  );
}

/** Remove ownership of a specific card entirely. */
export async function removeCardOwnership(db: SQLiteDatabase, cardId: number): Promise<void> {
  await db.runAsync("DELETE FROM collection WHERE card_id = ?;", [cardId]);
}

/** Mark a species as owned at species level (no specific card). Idempotent. */
export async function markSpeciesOwned(db: SQLiteDatabase, speciesId: number): Promise<void> {
  await db.runAsync(
    `INSERT INTO collection(pokemon_species_id, card_id, quantity, is_binder_card) VALUES(?, NULL, 1, 0)
     ON CONFLICT(pokemon_species_id) DO NOTHING;`,
    [speciesId],
  );
}

/** Remove ALL ownership for a species (species-level entry + card entries). */
export async function removeSpeciesOwnership(db: SQLiteDatabase, speciesId: number): Promise<void> {
  await db.withExclusiveTransactionAsync(async (tx) => {
    await tx.runAsync(
      "DELETE FROM collection WHERE pokemon_species_id = ? AND card_id IS NULL;",
      [speciesId],
    );
    await tx.runAsync(
      `DELETE FROM collection WHERE card_id IN (SELECT id FROM cards WHERE pokemon_species_id = ?);`,
      [speciesId],
    );
  });
}

/** Toggle species ownership (species-level). Returns the new owned state. */
export async function toggleSpeciesOwnership(db: SQLiteDatabase, speciesId: number): Promise<boolean> {
  const owned = await isSpeciesOwned(db, speciesId);
  if (owned) {
    await removeSpeciesOwnership(db, speciesId);
    return false;
  }
  await markSpeciesOwned(db, speciesId);
  return true;
}

export async function isSpeciesOwned(db: SQLiteDatabase, speciesId: number): Promise<boolean> {
  const row = await db.getFirstAsync<{ n: number }>(
    `SELECT (
        EXISTS (SELECT 1 FROM collection WHERE pokemon_species_id = ? AND card_id IS NULL)
     OR EXISTS (SELECT 1 FROM collection col JOIN cards c ON col.card_id = c.id WHERE c.pokemon_species_id = ?)
     ) AS n;`,
    [speciesId, speciesId],
  );
  return (row?.n ?? 0) === 1;
}

// ---------------------------------------------------------------------------
// Representative binder card (Pokédex binder)
// ---------------------------------------------------------------------------

export async function setBinderCard(db: SQLiteDatabase, cardId: number): Promise<void> {
  const card = await db.getFirstAsync<{ pokemon_species_id: number | null }>(
    "SELECT pokemon_species_id FROM cards WHERE id = ?;",
    [cardId],
  );
  const speciesId = card?.pokemon_species_id ?? null;
  await db.withExclusiveTransactionAsync(async (tx) => {
    if (speciesId != null) {
      await tx.runAsync(
        `UPDATE collection SET is_binder_card = 0
         WHERE card_id IN (SELECT id FROM cards WHERE pokemon_species_id = ?);`,
        [speciesId],
      );
    }
    await tx.runAsync("UPDATE collection SET is_binder_card = 1 WHERE card_id = ?;", [cardId]);
  });
}

// ---------------------------------------------------------------------------
// Pokédex binder page (derived National Dex view)
// ---------------------------------------------------------------------------

/**
 * Build a Pokédex binder page for [dex range of `page`], reusing the shared
 * pure builder. Representative card = the is_binder_card entry if present, else
 * the first owned card for that species.
 */
export async function getPokedexBinderPage(
  db: SQLiteDatabase,
  page: number,
  pageSize: number,
): Promise<PokedexBinderPage> {
  const startDex = (page - 1) * pageSize + 1;
  const endDex = Math.min(startDex + pageSize - 1, NATIONAL_DEX_COUNT);

  const speciesRows = await db.getAllAsync<PokemonSpecies>(
    `SELECT id, national_dex_number, name, generation FROM pokemon_species
     WHERE national_dex_number >= ? AND national_dex_number <= ?
     ORDER BY national_dex_number;`,
    [startDex, endDex],
  );

  const inputs = new Map<number, PokedexSlotInput>();

  for (const sp of speciesRows) {
    // Owned card count for the species.
    const countRow = await db.getFirstAsync<{ n: number; qty: number | null }>(
      `SELECT COUNT(*) AS n, SUM(col.quantity) AS qty
       FROM collection col JOIN cards c ON col.card_id = c.id
       WHERE c.pokemon_species_id = ?;`,
      [sp.id],
    );
    const cardCount = countRow?.n ?? 0;

    const speciesLevel = await db.getFirstAsync<{ n: number }>(
      "SELECT COUNT(*) AS n FROM collection WHERE pokemon_species_id = ? AND card_id IS NULL;",
      [sp.id],
    );
    const owned = cardCount > 0 || (speciesLevel?.n ?? 0) > 0;

    let representative: CardWithContext | null = null;
    if (cardCount > 0) {
      const rep = await db.getFirstAsync<CardJoinRow>(
        `${CARD_SELECT}
         JOIN collection col ON col.card_id = c.id
         WHERE c.pokemon_species_id = ?
         ORDER BY col.is_binder_card DESC, c.card_number, c.id
         LIMIT 1;`,
        [sp.id],
      );
      representative = rep ? toCardWithContext(rep) : null;
    }

    inputs.set(sp.national_dex_number, {
      species: sp,
      owned,
      representativeCard: representative,
      totalCards: countRow?.qty ?? 0,
    });
  }

  return buildPokedexBinderPage(inputs, page, pageSize, NATIONAL_DEX_COUNT);
}
