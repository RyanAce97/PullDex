import { useQuery } from "@tanstack/react-query";
import { getFilterOptions, searchCards } from "../api/cards";
import type { CardSearchParams } from "../api/cards";

/**
 * Hook for paginated card search with filters.
 *
 * At least one of q, species, set_name, or rarity must be provided for
 * the query to be enabled.
 */
export function useCardSearch(params: CardSearchParams) {
  const hasSearchCriteria = !!(params.q || params.species || params.set_name || params.rarity);

  return useQuery({
    queryKey: ["cards", "search", params],
    queryFn: () => searchCards(params),
    enabled: hasSearchCriteria,
  });
}

/**
 * Hook for fetching available card filter options (rarities, etc.).
 */
export function useCardFilterOptions() {
  return useQuery({
    queryKey: ["cards", "filter-options"],
    queryFn: getFilterOptions,
    staleTime: 5 * 60 * 1000, // 5 minutes — rarities rarely change
  });
}
