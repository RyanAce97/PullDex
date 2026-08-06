import { useQuery } from "@tanstack/react-query";
import { getMissingSpeciesInSet } from "../api/recommendations";
import { queryKeys } from "../lib/queryKeys";

export function useRecommendationSpecies(setId: number) {
  return useQuery({
    queryKey: queryKeys.recommendationSpecies(setId),
    queryFn: () => getMissingSpeciesInSet(setId),
    enabled: !isNaN(setId),
  });
}
