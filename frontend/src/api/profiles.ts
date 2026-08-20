import { apiClient } from "./client";
import type { ProfileRead, ProfileCreate, ProfileRename, ProfileSettingsUpdate } from "../types";

export async function getProfiles(): Promise<ProfileRead[]> {
  return apiClient.get<ProfileRead[]>("/profiles");
}

export async function getActiveProfile(): Promise<ProfileRead> {
  return apiClient.get<ProfileRead>("/profiles/active");
}

export async function createProfile(data: ProfileCreate): Promise<ProfileRead> {
  return apiClient.post<ProfileRead>("/profiles", data);
}

export async function activateProfile(profileId: number): Promise<ProfileRead> {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL || window.location.origin}/profiles/${profileId}/activate`,
    { method: "PUT", headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Failed to activate profile ${profileId}`);
  }
  return response.json();
}

export async function updateProfileSettings(
  profileId: number,
  data: ProfileSettingsUpdate,
): Promise<ProfileRead> {
  return apiClient.patch<ProfileRead>(`/profiles/${profileId}`, data);
}

export async function renameProfile(profileId: number, data: ProfileRename): Promise<ProfileRead> {
  return apiClient.patch<ProfileRead>(`/profiles/${profileId}/rename`, data);
}

export async function deleteProfile(profileId: number): Promise<void> {
  return apiClient.delete(`/profiles/${profileId}`);
}
