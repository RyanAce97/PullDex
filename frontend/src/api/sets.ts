import { apiClient } from "./client";
import type { SetSummaryRead } from "../types";

export async function getSetSummaries(): Promise<SetSummaryRead[]> {
  return apiClient.get<SetSummaryRead[]>("/sets/summary");
}
