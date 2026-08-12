import { apiClient } from "./client";
import type { CardRead, CardSearchResult } from "../types";

export async function getCardsByDex(
  nationalDexNumber: number,
  limit: number = 100,
  offset: number = 0,
): Promise<CardRead[]> {
  return apiClient.get<CardRead[]>(`/cards/by-dex/${nationalDexNumber}`, {
    limit,
    offset,
  });
}

export async function searchCardsFull(
  query: string,
  limit: number = 50,
): Promise<CardSearchResult[]> {
  return apiClient.get<CardSearchResult[]>("/cards/search", { q: query, limit });
}
