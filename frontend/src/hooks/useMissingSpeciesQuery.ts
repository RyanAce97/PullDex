import { useQuery } from "@tanstack/react-query";
import { getMissingSpecies } from "../api/progress";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import { queryKeys } from "../lib/queryKeys";

export function useMissingSpeciesQuery() {
  return useQuery({
    queryKey: queryKeys.missingSpecies,
    queryFn: async () => {
      const missing = await getMissingSpecies(NATIONAL_DEX_COUNT, 0);
      return new Set(missing.map((s) => s.id));
    },
  });
}
