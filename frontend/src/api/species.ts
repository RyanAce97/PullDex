import { apiClient } from "./client";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import type { PokemonSpeciesRead } from "../types";
import type { SpeciesSummaryRead } from "../types";

export async function getAllSpecies(
  limit: number = NATIONAL_DEX_COUNT,
  offset: number = 0,
): Promise<PokemonSpeciesRead[]> {
  return apiClient.get<PokemonSpeciesRead[]>("/species", { limit, offset });
}

export async function searchSpecies(
  name: string,
  limit: number = 50,
): Promise<PokemonSpeciesRead[]> {
  return apiClient.get<PokemonSpeciesRead[]>("/species", { name, limit });
}

export async function getSpeciesSummary(): Promise<SpeciesSummaryRead[]> {
  return apiClient.get<SpeciesSummaryRead[]>("/species/summary");
}
