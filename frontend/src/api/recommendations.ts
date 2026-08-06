import { apiClient } from "./client";
import type { MissingSpeciesRead, RecommendationResponse } from "../types";

export async function getRecommendations(
  limit: number = 10,
): Promise<RecommendationResponse> {
  return apiClient.get<RecommendationResponse>("/recommendations", { limit });
}

export async function getMissingSpeciesInSet(
  setId: number,
): Promise<MissingSpeciesRead[]> {
  return apiClient.get<MissingSpeciesRead[]>(`/recommendations/${setId}/species`);
}
