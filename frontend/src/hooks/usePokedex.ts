import { useQuery } from "@tanstack/react-query";
import { getProgress, getMissingSpecies } from "../api/progress";
import { getAllSpecies } from "../api/species";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import { queryKeys } from "../lib/queryKeys";
import type { PokemonSpeciesRead, ProgressRead } from "../types";

interface PokedexData {
  species: PokemonSpeciesRead[];
  missingIds: Set<number>;
  progress: ProgressRead;
}

interface UsePokedexResult {
  data: PokedexData | undefined;
  isLoading: boolean;
  error: Error | null;
}

export function usePokedex(): UsePokedexResult {
  const speciesQuery = useQuery({
    queryKey: queryKeys.species,
    queryFn: () => getAllSpecies(NATIONAL_DEX_COUNT),
  });

  const missingQuery = useQuery({
    queryKey: queryKeys.missingSpecies,
    queryFn: async () => {
      const missing = await getMissingSpecies(NATIONAL_DEX_COUNT, 0);
      return new Set(missing.map((s) => s.id));
    },
  });

  const progressQuery = useQuery({
    queryKey: queryKeys.progress,
    queryFn: getProgress,
  });

  const isLoading =
    speciesQuery.isLoading || missingQuery.isLoading || progressQuery.isLoading;

  const error =
    speciesQuery.error || missingQuery.error || progressQuery.error;

  const data =
    speciesQuery.data && missingQuery.data && progressQuery.data
      ? {
          species: speciesQuery.data,
          missingIds: missingQuery.data,
          progress: progressQuery.data,
        }
      : undefined;

  return { data, isLoading, error };
}
