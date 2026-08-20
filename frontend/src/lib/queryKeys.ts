/**
 * Centralised React Query keys.
 *
 * Every hook references these instead of inline arrays, preventing
 * key drift and making cache invalidation predictable.
 */

export const queryKeys = {
  progress: ["progress"] as const,
  missingSpecies: ["progress", "missing"] as const,

  species: ["species"] as const,
  speciesSummary: ["species", "summary"] as const,

  collection: ["collection"] as const,

  setsSummary: ["sets", "summary"] as const,

  cardsByDex: (dexNumber: number) => ["cards", "by-dex", dexNumber] as const,

  recommendations: (limit: number) => ["recommendations", limit] as const,
  recommendationSpecies: (setId: number) =>
    ["recommendations", setId, "species"] as const,

  // Profiles
  profiles: ["profiles"] as const,
  activeProfile: ["profiles", "active"] as const,

  // Binder
  binder: ["binder"] as const,
  binderCards: (params: Record<string, unknown>) => ["binder", "cards", params] as const,
} as const;
