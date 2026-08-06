import { useQuery } from "@tanstack/react-query";
import { getSpeciesSummary } from "../api/species";
import { queryKeys } from "../lib/queryKeys";

export function useSpeciesSummary() {
  return useQuery({
    queryKey: queryKeys.speciesSummary,
    queryFn: getSpeciesSummary,
  });
}
