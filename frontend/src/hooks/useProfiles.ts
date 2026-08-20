import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  activateProfile,
  createProfile,
  deleteProfile,
  getActiveProfile,
  getProfiles,
  renameProfile,
  updateProfileSettings,
} from "../api/profiles";
import { queryKeys } from "../lib/queryKeys";
import type { ProfileCreate, ProfileRename, ProfileSettingsUpdate } from "../types";

export function useProfiles() {
  return useQuery({
    queryKey: queryKeys.profiles,
    queryFn: getProfiles,
  });
}

export function useActiveProfile() {
  return useQuery({
    queryKey: queryKeys.activeProfile,
    queryFn: getActiveProfile,
  });
}

/**
 * Invalidate all profile-scoped data when switching profiles.
 */
function useInvalidateAllProfileData() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
    queryClient.invalidateQueries({ queryKey: queryKeys.activeProfile });
    queryClient.invalidateQueries({ queryKey: queryKeys.collection });
    queryClient.invalidateQueries({ queryKey: queryKeys.progress });
    queryClient.invalidateQueries({ queryKey: queryKeys.missingSpecies });
    queryClient.invalidateQueries({ queryKey: queryKeys.speciesSummary });
    queryClient.invalidateQueries({ queryKey: queryKeys.setsSummary });
    queryClient.invalidateQueries({ queryKey: queryKeys.binder });
    queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    queryClient.invalidateQueries({ queryKey: ["collection", "species"] });
    queryClient.invalidateQueries({ queryKey: ["cards"] });
  };
}

export function useSwitchProfile() {
  const invalidateAll = useInvalidateAllProfileData();

  return useMutation({
    mutationFn: (profileId: number) => activateProfile(profileId),
    onSuccess: () => {
      invalidateAll();
    },
  });
}

export function useCreateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProfileCreate) => createProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
    },
  });
}

export function useRenameProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ profileId, data }: { profileId: number; data: ProfileRename }) =>
      renameProfile(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
      queryClient.invalidateQueries({ queryKey: queryKeys.activeProfile });
    },
  });
}

export function useUpdateProfileSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ profileId, data }: { profileId: number; data: ProfileSettingsUpdate }) =>
      updateProfileSettings(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
      queryClient.invalidateQueries({ queryKey: queryKeys.activeProfile });
      queryClient.invalidateQueries({ queryKey: queryKeys.binder });
    },
  });
}

export function useDeleteProfile() {
  const invalidateAll = useInvalidateAllProfileData();

  return useMutation({
    mutationFn: (profileId: number) => deleteProfile(profileId),
    onSuccess: () => {
      invalidateAll();
    },
  });
}
