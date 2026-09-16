import { apiClient } from "./client";
import type { CardDataUpdateStatusRead } from "../types";

/**
 * Fetch the read-only card-data update status.
 *
 * Calls the existing Stage 1 endpoint GET /card-data/update-check, which
 * compares the remote manifest against the local card-data version. This is
 * a *read-only* diagnostic: it never downloads set files or modifies the
 * database. The backend maps network/parse failures to explicit statuses
 * (REMOTE_UNAVAILABLE / INVALID_MANIFEST) and returns HTTP 200, so a failed
 * check does not surface as an error here.
 */
export async function getCardDataUpdateStatus(): Promise<CardDataUpdateStatusRead> {
  return apiClient.get<CardDataUpdateStatusRead>("/card-data/update-check");
}
