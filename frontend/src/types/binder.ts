// ---------------------------------------------------------------------------
// Binder entity
// ---------------------------------------------------------------------------

export type BinderType = "POKEDEX" | "FREE_PLACEMENT";

export interface Binder {
  id: number;
  profile_id: number;
  name: string;
  binder_type: BinderType;
  rows: number;
  columns: number;
  sort_order: string;
  is_default: boolean;
  created_at: string;
}

export interface BinderCreate {
  name: string;
  binder_type: BinderType;
  rows: number;
  columns: number;
  sort_order?: string;
}

export interface BinderUpdate {
  name?: string;
  rows?: number;
  columns?: number;
  sort_order?: string;
}

// ---------------------------------------------------------------------------
// POKEDEX page (derived National Dex slots) — preserves original shape.
// ---------------------------------------------------------------------------

export interface BinderCardInfo {
  id: number;
  api_card_id: string | null;
  card_number: string | null;
  rarity: string | null;
  image_url: string | null;
  set_name: string | null;
  set_code: string | null;
  quantity: number;
}

export interface BinderSlot {
  dex_number: number | null;
  species_name: string | null;
  species_id: number | null;
  owned: boolean;
  has_card: boolean;
  card: BinderCardInfo | null;
  total_cards: number;
}

export interface BinderPageResponse {
  page: number;
  page_size: number;
  total_species: number;
  total_pages: number;
  slots: BinderSlot[];
}

export interface PokedexBinderPage extends BinderPageResponse {
  binder_type: "POKEDEX";
}

// ---------------------------------------------------------------------------
// FREE_PLACEMENT page (explicit placements with derived concept status).
// ---------------------------------------------------------------------------

export interface FreePlacementCardInfo {
  card_id: number;
  api_card_id: string | null;
  card_number: string | null;
  rarity: string | null;
  image_url: string | null;
  species_id: number | null;
  pokemon_name: string | null;
  national_dex_number: number | null;
  set_name: string | null;
  set_code: string | null;
}

export interface FreePlacementSlot {
  slot: number;
  placement_id: number | null;
  card: FreePlacementCardInfo | null;
  is_concept: boolean;
}

export interface FreePlacementPage {
  binder_type: "FREE_PLACEMENT";
  page: number;
  page_size: number;
  total_pages: number;
  rows: number;
  columns: number;
  slots: FreePlacementSlot[];
}

/** Discriminated union returned by GET /binders/{id}/page. */
export type AnyBinderPage = PokedexBinderPage | FreePlacementPage;
