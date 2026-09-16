import { useQuery } from "@tanstack/react-query";
import { getRecommendations } from "../api/recommendations";
import { queryKeys } from "../lib/queryKeys";

export function useRecommendations(limit: number = 10, promos: boolean = false) {
  return useQuery({
    queryKey: queryKeys.recommendations(limit, promos),
    queryFn: () => getRecommendations(limit, promos),
  });
}
