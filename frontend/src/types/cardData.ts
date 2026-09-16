/**
 * Types for the card-data updater (Stage 2A — status display only).
 *
 * These mirror the backend `CardDataUpdateStatusRead` schema returned by
 * GET /card-data/update-check. Stage 2A only *reads* this status to inform
 * the user; it performs no download and no card-data mutation.
 */

/** All possible outcomes of a read-only card-data update check. */
export type CardDataUpdateStatus =
  | "UP_TO_DATE"
  | "UPDATE_AVAILABLE"
  | "REMOTE_UNAVAILABLE"
  | "INVALID_MANIFEST"
  | "INCOMPATIBLE_SCHEMA";

/** Per-set metadata carried from the remote manifest (unused in Stage 2A UI). */
export interface RemoteSetInfo {
  id: string;
  name: string;
  file: string;
  version: number;
  sha256: string;
  card_count: number;
}

/** Result of a read-only card-data update check. */
export interface CardDataUpdateStatusRead {
  status: CardDataUpdateStatus;
  local_data_version: number;
  remote_data_version: number | null;
  remote_schema_version: number | null;
  remote_set_count: number | null;
  remote_card_count: number | null;
  update_available: boolean;
  error: string | null;
  sets: RemoteSetInfo[];
}

/** Possible outcomes of an actual card-data update (Stage 2B). */
export type CardDataUpdateResultStatus =
  | "UPDATED"
  | "ALREADY_UP_TO_DATE"
  | "REMOTE_UNAVAILABLE"
  | "INVALID_MANIFEST"
  | "INCOMPATIBLE_SCHEMA"
  | "DOWNLOAD_FAILED"
  | "HASH_MISMATCH"
  | "INVALID_SET_DATA"
  | "DATABASE_BACKUP_FAILED"
  | "DATABASE_UPDATE_FAILED";

/** Result of performing an actual card-data update (Stage 2B). */
export interface CardDataUpdateResultRead {
  status: CardDataUpdateResultStatus;
  success: boolean;
  message: string;
  local_data_version: number;
  remote_data_version: number | null;
  sets_created: number;
  sets_updated: number;
  cards_created: number;
  cards_updated: number;
  set_count: number | null;
  card_count: number | null;
  backup_path: string | null;
  error: string | null;
}
