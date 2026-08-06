import { useQuery } from "@tanstack/react-query";
import { getCardsByDex } from "../api/cards";
import { getCollection } from "../api/collection";
import { getMissingSpecies } from "../api/progress";
import { getAllSpecies } from "../api/species";
import { queryKeys } from "../lib/queryKeys";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import type { CardRead, CollectionRead, PokemonSpeciesRead } from "../types";

interface SpeciesDetailData {
  species: PokemonSpeciesRead;
  owned: boolean;
  cards: CardRead[];
  /** Collection entries for cards belonging to this species. */
  collectionEntries: CollectionRead[];
  /** Set of card IDs that are in the collection. */
  ownedCardIds: Set<number>;
}

interface UseSpeciesDetailResult {
  data: SpeciesDetailData | undefined;
  isLoading: boolean;
  error: Error | null;
}

export function useSpeciesDetail(speciesId: number): UseSpeciesDetailResult {
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

  const collectionQuery = useQuery({
    queryKey: queryKeys.collection,
    queryFn: () => getCollection(10_000),
  });

  // Find species to get its dex number for the cards query
  const species = speciesQuery.data?.find((s) => s.id === speciesId);

  const cardsQuery = useQuery({
    queryKey: queryKeys.cardsByDex(species?.national_dex_number ?? 0),
    queryFn: () => getCardsByDex(species!.national_dex_number),
    enabled: !!species,
  });

  const isLoading =
    speciesQuery.isLoading ||
    missingQuery.isLoading ||
    cardsQuery.isLoading ||
    collectionQuery.isLoading;

  const error =
    speciesQuery.error ||
    missingQuery.error ||
    cardsQuery.error ||
    collectionQuery.error;

  let data: SpeciesDetailData | undefined;

  if (species && missingQuery.data && cardsQuery.data && collectionQuery.data) {
    const cardIds = new Set(cardsQuery.data.map((c) => c.id));
    const relevantEntries = collectionQuery.data.filter(
      (e) => e.card_id !== null && cardIds.has(e.card_id),
    );
    const ownedCardIds = new Set(
      relevantEntries.map((e) => e.card_id).filter((id): id is number => id !== null),
    );

    data = {
      species,
      owned: !missingQuery.data.has(species.id),
      cards: cardsQuery.data,
      collectionEntries: relevantEntries,
      ownedCardIds,
    };
  }

  return { data, isLoading, error };
}
