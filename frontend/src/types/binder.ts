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
