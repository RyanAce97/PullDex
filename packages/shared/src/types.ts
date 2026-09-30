/**
 * Shared PullDex domain types.
 *
 * These mirror the existing desktop/backend models (same field names) so the
 * mobile app and any future shared consumers use ONE card model rather than a
 * second, incompatible one. Fields map 1:1 to the catalogue schema in the seed
 * database (pokemon_species, sets, cards) and the collection table.
 */

// ---------------------------------------------------------------------------
// Catalogue
// ---------------------------------------------------------------------------

export interface PokemonSpecies {
  id: number;
  national_dex_number: number;
  name: string;
  generation: number | null;
}

export interface CardSet {
  id: number;
  api_set_id: string | null;
  name: string;
  series: string;
  release_date: string | null;
  is_promo: boolean;
}

export interface Card {
  id: number;
  api_card_id: string | null;
  pokemon_species_id: number | null;
  set_id: number | null;
  card_number: string | null;
  rarity: string | null;
  variant: string | null;
  image_url: string | null;
}

/**
 * Denormalised card row for display (card joined with its species + set).
 * Matches the shape the desktop `CardSearchResult` exposes, so UI code and
 * search/filter helpers can be shared.
 */
export interface CardWithContext {
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
  is_promo: boolean;
}

// ---------------------------------------------------------------------------
// Collection
// ---------------------------------------------------------------------------

/**
 * A collection entry. Mirrors the desktop model:
 * - species-level: pokemon_species_id set, card_id null
 * - card-level: card_id set, quantity >= 1
 *
 * The mobile MVP has a single implicit local profile, so profile_id is omitted
 * (there is one collection on the device). is_binder_card selects the
 * representative card for the Pokédex binder, exactly as on desktop.
 */
export interface CollectionEntry {
  id: number;
  pokemon_species_id: number | null;
  card_id: number | null;
  quantity: number;
  is_binder_card: boolean;
}

// ---------------------------------------------------------------------------
// Pokédex / progress
// ---------------------------------------------------------------------------

export interface SpeciesOwnership {
  species: PokemonSpecies;
  owned: boolean;
  /** Number of distinct owned cards for this species. */
  ownedCardCount: number;
}

export interface CollectionProgress {
  totalSpecies: number;
  ownedSpecies: number;
  missingSpecies: number;
  /** Percentage 0–100, one decimal place. */
  percentage: number;
}

// ---------------------------------------------------------------------------
// Binder (Pokédex — derived National Dex view)
// ---------------------------------------------------------------------------

export type BinderType = "POKEDEX" | "FREE_PLACEMENT";

export interface PokedexBinderSlot {
  dex_number: number | null;
  species_name: string | null;
  species_id: number | null;
  owned: boolean;
  has_card: boolean;
  card: CardWithContext | null;
  total_cards: number;
}

export interface PokedexBinderPage {
  binder_type: "POKEDEX";
  page: number;
  page_size: number;
  total_species: number;
  total_pages: number;
  slots: PokedexBinderSlot[];
}

// ---------------------------------------------------------------------------
// Search / filter
// ---------------------------------------------------------------------------

export type OwnershipFilter = "all" | "owned" | "missing";
