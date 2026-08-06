import { apiClient } from "./client";
import type { CollectionRead } from "../types";

// ---------------------------------------------------------------------------
// Read
// ---------------------------------------------------------------------------

export async function getCollection(limit: number = 1000): Promise<CollectionRead[]> {
  return apiClient.get<CollectionRead[]>("/collection", { limit });
}

export async function getCardEntriesForSpecies(speciesId: number): Promise<CollectionRead[]> {
  return apiClient.get<CollectionRead[]>(`/collection/species/${speciesId}/cards`);
}

// ---------------------------------------------------------------------------
// Species-level
// ---------------------------------------------------------------------------

export async function addSpeciesToCollection(speciesId: number): Promise<CollectionRead> {
  return apiClient.post<CollectionRead>("/collection/species", {
    pokemon_species_id: speciesId,
  });
}

export async function removeSpeciesFromCollection(speciesId: number): Promise<void> {
  return apiClient.delete(`/collection/species/${speciesId}`);
}

// ---------------------------------------------------------------------------
// Card-level
// ---------------------------------------------------------------------------

export async function addCardToCollection(
  cardId: number,
  quantity: number = 1,
): Promise<CollectionRead> {
  return apiClient.post<CollectionRead>("/collection/cards", {
    card_id: cardId,
    quantity,
  });
}

export async function updateCardQuantity(
  entryId: number,
  quantity: number,
): Promise<CollectionRead> {
  return apiClient.patch<CollectionRead>(`/collection/cards/${entryId}`, { quantity });
}

export async function removeFromCollection(entryId: number): Promise<void> {
  return apiClient.delete(`/collection/${entryId}`);
}
