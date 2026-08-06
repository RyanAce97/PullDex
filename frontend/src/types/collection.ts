export interface CollectionRead {
  id: number;
  card_id: number | null;
}

export interface CollectionCreate {
  card_id: number;
}
