import { apiClient } from "./client";
import type { MissingSpeciesRead, RecommendationResponse } from "../types";

export async function getRecommendations(
  limit: number = 10,
  promos: boolean = false,
): Promise<RecommendationResponse> {
  // FastAPI parses the boolean query param from the string "true"/"false".
  return apiClient.get<RecommendationResponse>("/recommendations", {
    limit,
    promos: promos ? "true" : "false",
  });
}

export async function getMissingSpeciesInSet(
  setId: number,
): Promise<MissingSpeciesRead[]> {
  return apiClient.get<MissingSpeciesRead[]>(`/recommendations/${setId}/species`);
}
