import { apiClient } from "./client";
import type { CardDataUpdateResultRead, CardDataUpdateStatusRead } from "../types";

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

/**
 * Perform the actual card-data update (Stage 2B).
 *
 * POSTs to /card-data/update, which downloads + validates the remote set
 * files, backs up the database, and atomically merges the reference data.
 * User data (collection, quantities, binder, profiles) is never modified.
 * The backend returns a structured result with a UI-safe ``message`` and
 * ``success`` flag; expected failures come back as HTTP 200 with
 * ``success: false`` rather than throwing.
 */
export async function updateCardData(): Promise<CardDataUpdateResultRead> {
  return apiClient.post<CardDataUpdateResultRead>("/card-data/update", {});
}
