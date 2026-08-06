export interface CardRead {
  id: number;
  api_card_id: string | null;
  set_id: number | null;
  pokemon_species_id: number | null;
  card_number: string | null;
  rarity: string | null;
  variant: string | null;
  image_url: string | null;
}
