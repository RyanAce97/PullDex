/**
 * Pure, framework-agnostic PullDex helpers.
 *
 * These contain no I/O and no React/SQLite dependencies, so they are trivially
 * unit-testable and reused by the mobile data layer and UI. The logic mirrors
 * the desktop backend's derived behaviour (Pokédex slots, ownership, concept
 * status) to keep the two platforms consistent.
 */

import { NATIONAL_DEX_COUNT } from "./constants";
import type {
  CardWithContext,
  CollectionProgress,
  OwnershipFilter,
  PokedexBinderPage,
  PokedexBinderSlot,
  PokemonSpecies,
  SetAggregate,
  SetRecommendation,
  SpeciesOwnership,
} from "./types";

// ---------------------------------------------------------------------------
// Progress
// ---------------------------------------------------------------------------

export function computeProgress(ownedSpeciesCount: number, totalSpecies = NATIONAL_DEX_COUNT): CollectionProgress {
  const owned = Math.max(0, Math.min(ownedSpeciesCount, totalSpecies));
  const missing = totalSpecies - owned;
  const percentage = totalSpecies > 0 ? Math.round((owned / totalSpecies) * 1000) / 10 : 0;
  return { totalSpecies, ownedSpecies: owned, missingSpecies: missing, percentage };
}

// ---------------------------------------------------------------------------
// Species search + filter (Collection / Pokédex / Card Show Mode)
// ---------------------------------------------------------------------------

/**
 * Filter a list of species-ownership rows by a free-text query (name or dex
 * number, case-insensitive) and an ownership filter. Pure and allocation-light
 * so it is safe to call on every keystroke in Card Show Mode.
 */
export function filterSpecies(
  rows: SpeciesOwnership[],
  query: string,
  ownership: OwnershipFilter = "all",
): SpeciesOwnership[] {
  const trimmed = query.trim().toLowerCase();
  return rows.filter((row) => {
    if (ownership === "owned" && !row.owned) return false;
    if (ownership === "missing" && row.owned) return false;
    if (trimmed.length === 0) return true;
    if (row.species.name.toLowerCase().includes(trimmed)) return true;
    if (String(row.species.national_dex_number).includes(trimmed)) return true;
    return false;
  });
}

/**
 * Rank species for a search box: exact dex/name matches first, then prefix,
 * then substring, then dex order. Used by Card Show Mode for fast lookup.
 */
export function rankSpeciesSearch(rows: SpeciesOwnership[], query: string, limit = 30): SpeciesOwnership[] {
  const q = query.trim().toLowerCase();
  if (q.length === 0) return [];
  const scored = rows
    .map((row) => ({ row, score: scoreSpecies(row.species, q) }))
    .filter((s) => s.score < Number.POSITIVE_INFINITY)
    .sort((a, b) => a.score - b.score || a.row.species.national_dex_number - b.row.species.national_dex_number);
  return scored.slice(0, limit).map((s) => s.row);
}

function scoreSpecies(species: PokemonSpecies, q: string): number {
  const name = species.name.toLowerCase();
  const dex = String(species.national_dex_number);
  if (name === q || dex === q) return 0;
  if (name.startsWith(q) || dex.startsWith(q)) return 1;
  if (name.includes(q)) return 2;
  return Number.POSITIVE_INFINITY;
}

// ---------------------------------------------------------------------------
// Card search + filter
// ---------------------------------------------------------------------------

export function filterCards(cards: CardWithContext[], query: string): CardWithContext[] {
  const q = query.trim().toLowerCase();
  if (q.length === 0) return cards;
  return cards.filter((c) => {
    if (c.pokemon_name && c.pokemon_name.toLowerCase().includes(q)) return true;
    if (c.national_dex_number != null && String(c.national_dex_number).includes(q)) return true;
    if (c.set_name && c.set_name.toLowerCase().includes(q)) return true;
    if (c.set_code && c.set_code.toLowerCase().includes(q)) return true;
    if (c.card_number && c.card_number.toLowerCase().includes(q)) return true;
    if (c.api_card_id && c.api_card_id.toLowerCase().includes(q)) return true;
    return false;
  });
}

// ---------------------------------------------------------------------------
// Concept derivation (Free Placement)
// ---------------------------------------------------------------------------

/**
 * A placed card is a "concept" card when the local collection does not contain
 * that specific card at card level. Ownership is ALWAYS derived (never stored),
 * exactly as on desktop.
 */
export function isConceptCard(cardId: number, ownedCardIds: ReadonlySet<number>): boolean {
  return !ownedCardIds.has(cardId);
}

// ---------------------------------------------------------------------------
// Pokédex binder pagination (derived National Dex view)
// ---------------------------------------------------------------------------

export function pokedexTotalPages(pageSize: number, totalSpecies = NATIONAL_DEX_COUNT): number {
  if (pageSize <= 0) return 1;
  return Math.ceil(totalSpecies / pageSize);
}

export function pokedexPageDexRange(page: number, pageSize: number, totalSpecies = NATIONAL_DEX_COUNT): { startDex: number; endDex: number } {
  const startDex = (page - 1) * pageSize + 1;
  const endDex = Math.min(startDex + pageSize - 1, totalSpecies);
  return { startDex, endDex };
}

export interface PokedexSlotInput {
  species: PokemonSpecies;
  owned: boolean;
  representativeCard: CardWithContext | null;
  totalCards: number;
}

/**
 * Build a Pokédex binder page from pre-fetched per-dex slot inputs. The caller
 * supplies exactly the species in [startDex, endDex]; this pads to page_size
 * and computes total pages — mirroring the desktop binder_service output shape.
 */
export function buildPokedexBinderPage(
  inputsByDex: Map<number, PokedexSlotInput>,
  page: number,
  pageSize: number,
  totalSpecies = NATIONAL_DEX_COUNT,
): PokedexBinderPage {
  const totalPages = pokedexTotalPages(pageSize, totalSpecies);
  const { startDex, endDex } = pokedexPageDexRange(page, pageSize, totalSpecies);

  const slots: PokedexBinderSlot[] = [];
  for (let dex = startDex; dex <= endDex; dex++) {
    const input = inputsByDex.get(dex);
    if (!input) {
      slots.push(emptyPokedexSlot(dex));
      continue;
    }
    const hasCard = input.representativeCard !== null;
    slots.push({
      dex_number: dex,
      species_name: input.species.name,
      species_id: input.species.id,
      owned: input.owned,
      has_card: hasCard,
      card: input.representativeCard,
      total_cards: input.totalCards,
    });
  }
  while (slots.length < pageSize) {
    slots.push(emptyPokedexSlot(null));
  }

  return {
    binder_type: "POKEDEX",
    page,
    page_size: pageSize,
    total_species: totalSpecies,
    total_pages: totalPages,
    slots,
  };
}

function emptyPokedexSlot(dexNumber: number | null): PokedexBinderSlot {
  return {
    dex_number: dexNumber,
    species_name: null,
    species_id: null,
    owned: false,
    has_card: false,
    card: null,
    total_cards: 0,
  };
}

// ---------------------------------------------------------------------------
// Recommendations (pure ranking — mirrors desktop recommendation_service)
// ---------------------------------------------------------------------------

/**
 * Rank set aggregates into recommendations, replicating the desktop ordering
 * and coverage/density formulas exactly:
 *
 *   order:  missing_species_count DESC, total_cards_in_set ASC, release_date DESC
 *   coverage% = missing_species_count / total_missing * 100  (1 dp)
 *   density%  = missing_species_count / total_cards_in_set * 100 (1 dp)
 *
 * Only sets with >=1 missing species are included. Caller filters the pool by
 * promo status before passing aggregates in (Sets vs Promos), matching desktop.
 */
export function rankSetRecommendations(
  aggregates: SetAggregate[],
  totalMissing: number,
  limit = 10,
): SetRecommendation[] {
  const eligible = aggregates.filter((a) => a.missing_species_count > 0);

  eligible.sort((a, b) => {
    if (b.missing_species_count !== a.missing_species_count) {
      return b.missing_species_count - a.missing_species_count;
    }
    if (a.total_cards_in_set !== b.total_cards_in_set) {
      return a.total_cards_in_set - b.total_cards_in_set;
    }
    // release_date DESC (nulls last)
    const ra = a.release_date ?? "";
    const rb = b.release_date ?? "";
    if (ra === rb) return 0;
    return rb > ra ? 1 : -1;
  });

  return eligible.slice(0, limit).map((a, i) => ({
    rank: i + 1,
    set_id: a.set_id,
    api_set_id: a.api_set_id,
    set_name: a.set_name,
    series: a.series,
    release_date: a.release_date,
    missing_species_count: a.missing_species_count,
    total_species_in_set: a.total_species_in_set,
    total_cards_in_set: a.total_cards_in_set,
    coverage_percentage:
      totalMissing > 0 ? round1((a.missing_species_count / totalMissing) * 100) : 0,
    missing_species_density_percentage:
      a.total_cards_in_set > 0 ? round1((a.missing_species_count / a.total_cards_in_set) * 100) : 0,
  }));
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}
