import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateCardData } from "../api/cardData";
import { queryKeys } from "../lib/queryKeys";

/**
 * Mutation hook that performs the real card-data update (Stage 2B).
 *
 * On success it invalidates the card-data update check and the catalogue
 * queries (sets, progress, species) so the UI reflects any newly added or
 * changed reference data without an application restart.
 *
 * Duplicate-click protection is provided by React Query's ``isPending`` flag
 * (the component disables the button while a request is in flight); the
 * backend additionally guards against concurrent updates.
 */
export function useUpdateCardData() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateCardData,
    onSuccess: (result) => {
      // Always refresh the status indicator.
      queryClient.invalidateQueries({ queryKey: queryKeys.cardDataUpdate });

      // Only refresh the (potentially large) catalogue queries when reference
      // data actually changed.
      if (result.status === "UPDATED") {
        queryClient.invalidateQueries({ queryKey: queryKeys.setsSummary });
        queryClient.invalidateQueries({ queryKey: queryKeys.progress });
        queryClient.invalidateQueries({ queryKey: queryKeys.species });
        queryClient.invalidateQueries({ queryKey: queryKeys.speciesSummary });
      }
    },
  });
}
