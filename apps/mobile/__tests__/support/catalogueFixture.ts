// Tiny catalogue snapshot used by DB tests in place of the bundled 3.9 MB JSON.
// Shape matches assets/catalogue/catalogue.json.
export default {
  schema_version: 1,
  generated_at: "2026-01-01T00:00:00Z",
  counts: { species: 3, sets: 2, cards: 4 },
  species: [
    { id: 1, national_dex_number: 1, name: "bulbasaur", generation: 1 },
    { id: 4, national_dex_number: 4, name: "charmander", generation: 1 },
    { id: 25, national_dex_number: 25, name: "pikachu", generation: 1 },
  ],
  sets: [
    { id: 1, api_set_id: "sv1", name: "Scarlet & Violet", series: "SV", release_date: "2023-03-31", is_promo: false },
    { id: 2, api_set_id: "svp", name: "SV Black Star Promos", series: "SV", release_date: null, is_promo: true },
  ],
  cards: [
    { id: 100, api_card_id: "sv1-1", pokemon_species_id: 1, set_id: 1, card_number: "001", rarity: "Common", variant: null, image_url: "https://img/100.png" },
    { id: 101, api_card_id: "sv1-4", pokemon_species_id: 4, set_id: 1, card_number: "004", rarity: "Common", variant: null, image_url: "https://img/101.png" },
    { id: 102, api_card_id: "sv1-25", pokemon_species_id: 25, set_id: 1, card_number: "025", rarity: "Rare", variant: null, image_url: "https://img/102.png" },
    { id: 103, api_card_id: "svp-25", pokemon_species_id: 25, set_id: 2, card_number: "P25", rarity: "Promo", variant: null, image_url: "https://img/103.png" },
  ],
};
