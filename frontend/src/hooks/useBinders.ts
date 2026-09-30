import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addPlacement,
  createBinder,
  deleteBinder,
  getBinderPage,
  listBinders,
  movePlacement,
  removePlacement,
  setDefaultBinder,
  updateBinder,
} from "../api/binders";
import type { PlacementBody } from "../api/binders";
import { queryKeys } from "../lib/queryKeys";
import type { AnyBinderPage, BinderCreate, BinderUpdate } from "../types";

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useBinders() {
  return useQuery({
    queryKey: queryKeys.binders,
    queryFn: listBinders,
  });
}

export function useBinderPageQuery(binderId: number | null, page: number) {
  return useQuery<AnyBinderPage>({
    queryKey: binderId ? queryKeys.binderPage(binderId, page) : ["binders", "none", page],
    queryFn: () => getBinderPage(binderId as number, page),
    enabled: binderId !== null,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/** Invalidate everything that depends on the set of binders. */
function useInvalidateBinders() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.binders });
    queryClient.invalidateQueries({ queryKey: queryKeys.binder });
  };
}

export function useCreateBinder() {
  const invalidate = useInvalidateBinders();
  return useMutation({
    mutationFn: (data: BinderCreate) => createBinder(data),
    onSuccess: invalidate,
  });
}

export function useUpdateBinder() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateBinders();
  return useMutation({
    mutationFn: ({ binderId, data }: { binderId: number; data: BinderUpdate }) =>
      updateBinder(binderId, data),
    onSuccess: (_res, vars) => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["binders", vars.binderId] });
    },
  });
}

export function useSetDefaultBinder() {
  const invalidate = useInvalidateBinders();
  return useMutation({
    mutationFn: (binderId: number) => setDefaultBinder(binderId),
    onSuccess: invalidate,
  });
}

export function useDeleteBinder() {
  const invalidate = useInvalidateBinders();
  return useMutation({
    mutationFn: (binderId: number) => deleteBinder(binderId),
    onSuccess: invalidate,
  });
}

export function useAddPlacement(binderId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PlacementBody) => addPlacement(binderId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["binders", binderId] });
    },
  });
}

export function useMovePlacement(binderId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      placementId,
      page,
      slot,
    }: {
      placementId: number;
      page: number;
      slot: number;
    }) => movePlacement(binderId, placementId, { page, slot }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["binders", binderId] });
    },
  });
}

export function useRemovePlacement(binderId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (placementId: number) => removePlacement(binderId, placementId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["binders", binderId] });
    },
  });
}
