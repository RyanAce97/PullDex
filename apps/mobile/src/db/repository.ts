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
  rankSetRecommendations,
  NATIONAL_DEX_COUNT,
  type CardWithContext,
  type CollectionProgress,
  type PokedexBinderPage,
  type PokedexSlotInput,
  type PokemonSpecies,
  type SetAggregate,
  type SetRecommendation,
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

export async function getRepresentativeCardId(db: SQLiteDatabase, speciesId: number): Promise<number | null> {
  const row = await db.getFirstAsync<{ card_id: number }>(
    `SELECT col.card_id AS card_id
     FROM collection col JOIN cards c ON col.card_id = c.id
     WHERE c.pokemon_species_id = ? AND col.is_binder_card = 1
     LIMIT 1;`,
    [speciesId],
  );
  return row?.card_id ?? null;
}

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

// ---------------------------------------------------------------------------
// Dashboard summary
// ---------------------------------------------------------------------------

export interface CollectionSummary {
  progress: CollectionProgress;
  totalCatalogueCards: number;
  totalSets: number;
  promoSets: number;
  ownedCardEntries: number; // distinct owned cards (card-level)
}

export async function getCollectionSummary(db: SQLiteDatabase): Promise<CollectionSummary> {
  const progress = await getProgress(db);
  const cards = await db.getFirstAsync<{ n: number }>("SELECT COUNT(*) AS n FROM cards;");
  const sets = await db.getFirstAsync<{ n: number }>("SELECT COUNT(*) AS n FROM sets;");
  const promos = await db.getFirstAsync<{ n: number }>("SELECT COUNT(*) AS n FROM sets WHERE is_promo = 1;");
  const ownedCards = await db.getFirstAsync<{ n: number }>(
    "SELECT COUNT(*) AS n FROM collection WHERE card_id IS NOT NULL;",
  );
  return {
    progress,
    totalCatalogueCards: cards?.n ?? 0,
    totalSets: sets?.n ?? 0,
    promoSets: promos?.n ?? 0,
    ownedCardEntries: ownedCards?.n ?? 0,
  };
}

// ---------------------------------------------------------------------------
// Binder layout persistence (app_meta) — configurable via Settings
// ---------------------------------------------------------------------------

const BINDER_ROWS_KEY = "binder_rows";
const BINDER_COLS_KEY = "binder_columns";

export interface BinderLayout {
  rows: number;
  columns: number;
}

async function getMetaInt(db: SQLiteDatabase, key: string): Promise<number | null> {
  const row = await db.getFirstAsync<{ value: string }>("SELECT value FROM app_meta WHERE key = ?;", [key]);
  if (!row) return null;
  const n = parseInt(row.value, 10);
  return Number.isNaN(n) ? null : n;
}

export async function getBinderLayout(db: SQLiteDatabase): Promise<BinderLayout> {
  const rows = (await getMetaInt(db, BINDER_ROWS_KEY)) ?? 5;
  const columns = (await getMetaInt(db, BINDER_COLS_KEY)) ?? 4;
  return { rows, columns };
}

export async function setBinderLayout(db: SQLiteDatabase, rows: number, columns: number): Promise<void> {
  const clamp = (n: number) => Math.max(2, Math.min(5, Math.round(n)));
  await db.runAsync(
    "INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
    [BINDER_ROWS_KEY, String(clamp(rows))],
  );
  await db.runAsync(
    "INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
    [BINDER_COLS_KEY, String(clamp(columns))],
  );
}

export async function getCatalogueGeneratedAt(db: SQLiteDatabase): Promise<string | null> {
  const row = await db.getFirstAsync<{ value: string }>(
    "SELECT value FROM app_meta WHERE key = 'catalogue_generated_at';",
  );
  return row?.value ?? null;
}

// ---------------------------------------------------------------------------
// Recommendations (offline; mirrors desktop ranking via shared helper)
// ---------------------------------------------------------------------------

interface SetAggRow {
  set_id: number;
  api_set_id: string | null;
  set_name: string;
  series: string | null;
  release_date: string | null;
  is_promo: number;
  total_cards_in_set: number;
  total_species_in_set: number;
  missing_species_count: number;
}

/**
 * Return ranked set recommendations for the given pool (promos flag), computed
 * entirely on-device. Mirrors the desktop recommendation_service: only sets
 * with >=1 missing species; ranked by missing DESC / total_cards ASC /
 * release_date DESC; coverage & density via the shared pure helper.
 */
export async function getSetRecommendations(
  db: SQLiteDatabase,
  promos: boolean,
  limit = 10,
): Promise<{ totalMissing: number; recommendations: SetRecommendation[] }> {
  const progress = await getProgress(db);
  const totalMissing = progress.missingSpecies;
  if (totalMissing === 0) return { totalMissing: 0, recommendations: [] };

  // Per-set aggregates. "missing" = species in the set the user does not own
  // (neither species-level nor any card-level ownership for that species).
  const rows = await db.getAllAsync<SetAggRow>(
    `SELECT
       st.id AS set_id,
       st.api_set_id AS api_set_id,
       st.name AS set_name,
       st.series AS series,
       st.release_date AS release_date,
       st.is_promo AS is_promo,
       (SELECT COUNT(*) FROM cards c2 WHERE c2.set_id = st.id) AS total_cards_in_set,
       COUNT(DISTINCT c.pokemon_species_id) AS total_species_in_set,
       COUNT(DISTINCT CASE WHEN NOT (
           EXISTS (SELECT 1 FROM collection col WHERE col.pokemon_species_id = c.pokemon_species_id AND col.card_id IS NULL)
        OR EXISTS (SELECT 1 FROM collection col2 JOIN cards cc ON col2.card_id = cc.id WHERE cc.pokemon_species_id = c.pokemon_species_id)
       ) THEN c.pokemon_species_id END) AS missing_species_count
     FROM sets st
     JOIN cards c ON c.set_id = st.id AND c.pokemon_species_id IS NOT NULL
     WHERE st.is_promo = ?
     GROUP BY st.id;`,
    [promos ? 1 : 0],
  );

  const aggregates: SetAggregate[] = rows.map((r) => ({
    set_id: r.set_id,
    api_set_id: r.api_set_id,
    set_name: r.set_name,
    series: r.series,
    release_date: r.release_date,
    is_promo: !!r.is_promo,
    total_cards_in_set: r.total_cards_in_set,
    total_species_in_set: r.total_species_in_set,
    missing_species_count: r.missing_species_count,
  }));

  return {
    totalMissing,
    recommendations: rankSetRecommendations(aggregates, totalMissing, limit),
  };
}

/** Missing species that have a card in the given set (drill-down), dex order. */
export async function getMissingSpeciesInSet(db: SQLiteDatabase, setId: number): Promise<PokemonSpecies[]> {
  return db.getAllAsync<PokemonSpecies>(
    `SELECT DISTINCT s.id, s.national_dex_number, s.name, s.generation
     FROM pokemon_species s
     JOIN cards c ON c.pokemon_species_id = s.id AND c.set_id = ?
     WHERE NOT (
         EXISTS (SELECT 1 FROM collection col WHERE col.pokemon_species_id = s.id AND col.card_id IS NULL)
      OR EXISTS (SELECT 1 FROM collection col2 JOIN cards cc ON col2.card_id = cc.id WHERE cc.pokemon_species_id = s.id)
     )
     ORDER BY s.national_dex_number;`,
    [setId],
  );
}
