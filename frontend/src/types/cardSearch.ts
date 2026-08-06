export interface CardSearchResult {
  id: number;
  api_card_id: string | null;
  card_number: string | null;
  rarity: string | null;
  image_url: string | null;
  pokemon_name: string | null;
  national_dex_number: number | null;
  set_name: string | null;
  set_code: string | null;
}
