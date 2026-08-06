export interface CollectionRead {
  id: number;
  pokemon_species_id: number | null;
  card_id: number | null;
  quantity: number;
}

export interface CollectionSpeciesCreate {
  pokemon_species_id: number;
}

export interface CollectionCardCreate {
  card_id: number;
  quantity?: number;
}

export interface CollectionCardUpdate {
  quantity: number;
}
