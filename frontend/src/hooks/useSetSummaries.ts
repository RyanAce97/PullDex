import { useQuery } from "@tanstack/react-query";
import { getSetSummaries } from "../api/sets";
import { queryKeys } from "../lib/queryKeys";

export function useSetSummaries() {
  return useQuery({
    queryKey: queryKeys.setsSummary,
    queryFn: getSetSummaries,
  });
}
