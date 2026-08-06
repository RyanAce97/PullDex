import { apiClient } from "./client";
import type { CollectionRead } from "../types";

export async function getCollection(
  limit: number = 250,
  offset: number = 0,
): Promise<CollectionRead[]> {
  return apiClient.get<CollectionRead[]>("/collection", { limit, offset });
}

export async function addToCollection(cardId: number): Promise<CollectionRead> {
  return apiClient.post<CollectionRead>("/collection", { card_id: cardId });
}

export async function removeFromCollection(entryId: number): Promise<void> {
  return apiClient.delete(`/collection/${entryId}`);
}
