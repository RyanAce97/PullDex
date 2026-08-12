import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addCardToCollection,
  addSpeciesToCollection,
  getCollection,
  removeFromCollection,
  removeSpeciesFromCollection,
  updateCardQuantity,
} from "../api/collection";
import { queryKeys } from "../lib/queryKeys";
import type { CollectionRead } from "../types";

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useCollectionEntries() {
  return useQuery({
    queryKey: queryKeys.collection,
    queryFn: () => getCollection(10_000),
  });
}

// ---------------------------------------------------------------------------
// Invalidation helper
// ---------------------------------------------------------------------------

function useInvalidateCollectionRelated() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.collection });
    queryClient.invalidateQueries({ queryKey: queryKeys.progress });
    queryClient.invalidateQueries({ queryKey: queryKeys.missingSpecies });
    queryClient.invalidateQueries({ queryKey: queryKeys.speciesSummary });
    queryClient.invalidateQueries({ queryKey: queryKeys.setsSummary });
    queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    queryClient.invalidateQueries({ queryKey: ["collection", "species"] });
  };
}

// ---------------------------------------------------------------------------
// Species-level mutations
// ---------------------------------------------------------------------------

export function useAddSpeciesToCollection() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateCollectionRelated();

  return useMutation({
    mutationFn: (speciesId: number) => addSpeciesToCollection(speciesId),

    onMutate: async (speciesId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.collection });
      const previous = queryClient.getQueryData<CollectionRead[]>(queryKeys.collection);
      if (previous) {
        const optimistic: CollectionRead = {
          id: -Date.now(),
          pokemon_species_id: speciesId,
          card_id: null,
          quantity: 1,
        };
        queryClient.setQueryData<CollectionRead[]>(queryKeys.collection, [...previous, optimistic]);
      }
      return { previous };
    },

    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.collection, context.previous);
      }
    },

    onSettled: invalidate,
  });
}

export function useRemoveSpeciesFromCollection() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateCollectionRelated();

  return useMutation({
    mutationFn: (speciesId: number) => removeSpeciesFromCollection(speciesId),

    onMutate: async (speciesId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.collection });
      const previous = queryClient.getQueryData<CollectionRead[]>(queryKeys.collection);
      if (previous) {
        queryClient.setQueryData<CollectionRead[]>(
          queryKeys.collection,
          previous.filter((e) => e.pokemon_species_id !== speciesId || e.card_id !== null),
        );
      }
      return { previous };
    },

    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.collection, context.previous);
      }
    },

    onSettled: invalidate,
  });
}

// ---------------------------------------------------------------------------
// Card-level mutations
// ---------------------------------------------------------------------------

export function useAddCardToCollection() {
  const invalidate = useInvalidateCollectionRelated();

  return useMutation({
    mutationFn: ({ cardId, quantity }: { cardId: number; quantity?: number }) =>
      addCardToCollection(cardId, quantity),

    onSettled: invalidate,
  });
}

export function useUpdateCardQuantity() {
  const invalidate = useInvalidateCollectionRelated();

  return useMutation({
    mutationFn: ({ entryId, quantity }: { entryId: number; quantity: number }) =>
      updateCardQuantity(entryId, quantity),

    onSettled: invalidate,
  });
}

export function useRemoveFromCollection() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateCollectionRelated();

  return useMutation({
    mutationFn: (entryId: number) => removeFromCollection(entryId),

    onMutate: async (entryId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.collection });
      const previous = queryClient.getQueryData<CollectionRead[]>(queryKeys.collection);
      if (previous) {
        queryClient.setQueryData<CollectionRead[]>(
          queryKeys.collection,
          previous.filter((e) => e.id !== entryId),
        );
      }
      return { previous };
    },

    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.collection, context.previous);
      }
    },

    onSettled: invalidate,
  });
}
