import { useProgress } from "./useProgress";
import { useMissingSpeciesQuery } from "./useMissingSpeciesQuery";
import { useSpeciesQuery } from "./useSpeciesQuery";
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
  const speciesQuery = useSpeciesQuery();
  const missingQuery = useMissingSpeciesQuery();
  const progressQuery = useProgress();

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
