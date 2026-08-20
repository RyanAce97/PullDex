import { apiClient } from "./client";
import type { CardFilterOptions, CardSearchResult, PaginatedCardSearchResponse } from "../types";

export interface CardSearchParams {
  q?: string;
  species?: string;
  set_name?: string;
  rarity?: string;
  page?: number;
  page_size?: number;
}

export async function searchCards(
  params: CardSearchParams,
): Promise<PaginatedCardSearchResponse> {
  const queryParams: Record<string, string | number> = {};
  if (params.q) queryParams.q = params.q;
  if (params.species) queryParams.species = params.species;
  if (params.set_name) queryParams.set_name = params.set_name;
  if (params.rarity) queryParams.rarity = params.rarity;
  if (params.page) queryParams.page = params.page;
  if (params.page_size) queryParams.page_size = params.page_size;

  return apiClient.get<PaginatedCardSearchResponse>("/cards/search", queryParams);
}

export async function getCardsByDex(
  nationalDexNumber: number,
  limit: number = 100,
  offset: number = 0,
): Promise<CardSearchResult[]> {
  return apiClient.get<CardSearchResult[]>(`/cards/by-dex/${nationalDexNumber}`, {
    limit,
    offset,
  });
}

export async function getFilterOptions(): Promise<CardFilterOptions> {
  return apiClient.get<CardFilterOptions>("/cards/filter-options");
}
