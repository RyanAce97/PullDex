import { useQuery } from "@tanstack/react-query";
import { getAllSpecies } from "../api/species";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import { queryKeys } from "../lib/queryKeys";

export function useSpeciesQuery() {
  return useQuery({
    queryKey: queryKeys.species,
    queryFn: () => getAllSpecies(NATIONAL_DEX_COUNT),
  });
}
