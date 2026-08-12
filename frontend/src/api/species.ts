import { apiClient } from "./client";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import type { PokemonSpeciesRead, SpeciesSummaryRead } from "../types";

export async function getAllSpecies(
  limit: number = NATIONAL_DEX_COUNT,
  offset: number = 0,
): Promise<PokemonSpeciesRead[]> {
  return apiClient.get<PokemonSpeciesRead[]>("/species", { limit, offset });
}

export async function getSpeciesSummary(): Promise<SpeciesSummaryRead[]> {
  return apiClient.get<SpeciesSummaryRead[]>("/species/summary");
}
