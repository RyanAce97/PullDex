import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addToCollection,
  getCollection,
  removeFromCollection,
} from "../api/collection";
import { queryKeys } from "../lib/queryKeys";
import type { CollectionRead } from "../types";

/**
 * Fetches the full collection. Used to determine which cards are owned.
 */
export function useCollectionEntries() {
  return useQuery({
    queryKey: queryKeys.collection,
    queryFn: () => getCollection(10_000),
  });
}

/**
 * Mutation: add a card to the collection.
 *
 * Optimistically adds the entry to the cached collection list.
 * Invalidates progress, missing species, and recommendations on success.
 */
export function useAddToCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (cardId: number) => addToCollection(cardId),

    onMutate: async (cardId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.collection });

      const previous = queryClient.getQueryData<CollectionRead[]>(
        queryKeys.collection,
      );

      // Optimistic update: append a placeholder entry
      if (previous) {
        const optimistic: CollectionRead = {
          id: -Date.now(), // temporary negative ID
          card_id: cardId,
        };
        queryClient.setQueryData<CollectionRead[]>(queryKeys.collection, [
          ...previous,
          optimistic,
        ]);
      }

      return { previous };
    },

    onError: (_err, _cardId, context) => {
      // Roll back on failure
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.collection, context.previous);
      }
    },

    onSettled: () => {
      // Refetch to get real data and update dependent queries
      queryClient.invalidateQueries({ queryKey: queryKeys.collection });
      queryClient.invalidateQueries({ queryKey: queryKeys.progress });
      queryClient.invalidateQueries({ queryKey: queryKeys.missingSpecies });
      queryClient.invalidateQueries({ queryKey: queryKeys.speciesSummary });
      queryClient.invalidateQueries({ queryKey: queryKeys.setsSummary });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
}

/**
 * Mutation: remove a collection entry.
 *
 * Optimistically removes the entry from the cached collection list.
 * Invalidates progress, missing species, and recommendations on success.
 */
export function useRemoveFromCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (entryId: number) => removeFromCollection(entryId),

    onMutate: async (entryId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.collection });

      const previous = queryClient.getQueryData<CollectionRead[]>(
        queryKeys.collection,
      );

      // Optimistic update: remove the entry
      if (previous) {
        queryClient.setQueryData<CollectionRead[]>(
          queryKeys.collection,
          previous.filter((e) => e.id !== entryId),
        );
      }

      return { previous };
    },

    onError: (_err, _entryId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.collection, context.previous);
      }
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.collection });
      queryClient.invalidateQueries({ queryKey: queryKeys.progress });
      queryClient.invalidateQueries({ queryKey: queryKeys.missingSpecies });
      queryClient.invalidateQueries({ queryKey: queryKeys.speciesSummary });
      queryClient.invalidateQueries({ queryKey: queryKeys.setsSummary });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
}
