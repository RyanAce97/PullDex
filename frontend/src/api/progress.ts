import { apiClient } from "./client";
import type { MissingSpeciesRead, ProgressRead } from "../types";

export async function getProgress(): Promise<ProgressRead> {
  return apiClient.get<ProgressRead>("/progress");
}

export async function getMissingSpecies(
  limit: number = 250,
  offset: number = 0,
): Promise<MissingSpeciesRead[]> {
  return apiClient.get<MissingSpeciesRead[]>("/progress/missing", { limit, offset });
}
