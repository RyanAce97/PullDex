import { apiClient } from "./client";
import type { BackupResponse, ExportResponse, ImportRequest, ImportResponse, RestoreRequest, RestoreResponse } from "../types";

export async function exportCollection(): Promise<ExportResponse> {
  return apiClient.post<ExportResponse>("/data/export", {});
}

export async function importCollection(request: ImportRequest): Promise<ImportResponse> {
  return apiClient.post<ImportResponse>("/data/import", request);
}

export async function createBackup(): Promise<BackupResponse> {
  return apiClient.post<BackupResponse>("/data/backup", {});
}

export async function restoreBackup(request: RestoreRequest): Promise<RestoreResponse> {
  return apiClient.post<RestoreResponse>("/data/restore", request);
}
