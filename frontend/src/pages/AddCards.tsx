import { useCallback, useEffect, useRef, useState } from "react";
import { useCardSearch, useCardFilterOptions } from "../hooks/useCardSearch";
import {
  useAddCardToCollection,
  useCollectionEntries,
  useRemoveFromCollection,
} from "../hooks/useCollection";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import type { CardSearchResult } from "../types";

const PAGE_SIZE = 50;

export function AddCards() {
  // Filter state
  const [search, setSearch] = useState("");
  const [speciesFilter, setSpeciesFilter] = useState("");
  const [setFilter, setSetFilter] = useState("");
  const [rarityFilter, setRarityFilter] = useState("");
  const [page, setPage] = useState(1);

  // Debounced search values to avoid API calls on every keystroke
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [debouncedSpecies, setDebouncedSpecies] = useState("");
  const [debouncedSet, setDebouncedSet] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setDebouncedSpecies(speciesFilter);
      setDebouncedSet(setFilter);
      setPage(1); // Reset to page 1 on filter change
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search, speciesFilter, setFilter]);

  // Rarity filter change resets page immediately (dropdown, no debounce needed)
  const handleRarityChange = (value: string) => {
    setRarityFilter(value);
    setPage(1);
  };

  const searchParams = {
    q: debouncedSearch || undefined,
    species: debouncedSpecies || undefined,
    set_name: debouncedSet || undefined,
    rarity: rarityFilter || undefined,
    page,
    page_size: PAGE_SIZE,
  };

  const { data, isLoading, error } = useCardSearch(searchParams);
  const { data: filterOptions } = useCardFilterOptions();
  const { data: collection } = useCollectionEntries();

  const addMutation = useAddCardToCollection();
  const removeMutation = useRemoveFromCollection();

  const [pendingCardIds, setPendingCardIds] = useState<Set<number>>(() => new Set());
  const removingEntryIds = useRef<Set<number>>(new Set());

  const ownedCardIds = new Set(
    (collection ?? []).map((e) => e.card_id).filter((id): id is number => id !== null),
  );

  const findEntry = (cardId: number) =>
    (collection ?? []).find((e) => e.card_id === cardId);

  const handleAdd = useCallback(
    (cardId: number) => {
      if (pendingCardIds.has(cardId)) return;
      setPendingCardIds((prev) => new Set(prev).add(cardId));
      addMutation.mutate(
        { cardId, quantity: 1 },
        {
          onSettled: () => {
            setPendingCardIds((prev) => {
              const next = new Set(prev);
              next.delete(cardId);
              return next;
            });
          },
        },
      );
    },
    [addMutation, pendingCardIds],
  );

  const handleRemove = useCallback(
    (cardId: number) => {
      if (pendingCardIds.has(cardId)) return;
      const entry = findEntry(cardId);
      if (!entry || removingEntryIds.current.has(entry.id)) return;

      removingEntryIds.current.add(entry.id);
      setPendingCardIds((prev) => new Set(prev).add(cardId));
      removeMutation.mutate(entry.id, {
        onSettled: () => {
          removingEntryIds.current.delete(entry.id);
          setPendingCardIds((prev) => {
            const next = new Set(prev);
            next.delete(cardId);
            return next;
          });
        },
      });
    },
    [removeMutation, pendingCardIds, collection],
  );

  const hasAnyCriteria = !!(debouncedSearch || debouncedSpecies || debouncedSet || rarityFilter);

  const handleClearFilters = () => {
    setSearch("");
    setSpeciesFilter("");
    setSetFilter("");
    setRarityFilter("");
    setPage(1);
    setDebouncedSearch("");
    setDebouncedSpecies("");
    setDebouncedSet("");
  };

  const hasActiveFilters = !!(search || speciesFilter || setFilter || rarityFilter);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Add Cards</h2>
        <p className="text-sm text-gray-500 mt-1">
          Search and filter cards to add to your collection.
        </p>
      </div>

      {/* Search and filter controls */}
      <div className="space-y-3">
        {/* Main search */}
        <input
          type="text"
          placeholder="Search by name, card number, set code, or set name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
          className="w-full rounded-md border border-gray-300 px-4 py-3 text-sm shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          aria-label="Search cards"
        />

        {/* Filter row */}
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Pokémon species..."
            value={speciesFilter}
            onChange={(e) => setSpeciesFilter(e.target.value)}
            className="flex-1 min-w-[150px] rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            aria-label="Filter by species"
          />
          <input
            type="text"
            placeholder="Set name..."
            value={setFilter}
            onChange={(e) => setSetFilter(e.target.value)}
            className="flex-1 min-w-[150px] rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            aria-label="Filter by set"
          />
          <select
            value={rarityFilter}
            onChange={(e) => handleRarityChange(e.target.value)}
            className="min-w-[140px] rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            aria-label="Filter by rarity"
          >
            <option value="">All rarities</option>
            {(filterOptions?.rarities ?? []).map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="px-3 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      {!hasAnyCriteria && (
        <EmptyState
          icon="🔍"
          message="Enter a search term or select filters to find cards."
        />
      )}

      {hasAnyCriteria && isLoading && (
        <LoadingSpinner message="Searching cards..." />
      )}

      {hasAnyCriteria && error && (
        <ErrorState message="Failed to search cards." />
      )}

      {hasAnyCriteria && data && data.total === 0 && (
        <EmptyState icon="🃏" message="No cards match your search criteria." />
      )}

      {data && data.total > 0 && (
        <>
          {/* Results summary and pagination info */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {data.total} {data.total === 1 ? "card" : "cards"} found
              {data.total_pages > 1 && (
                <span className="ml-1">
                  — page {data.page} of {data.total_pages}
                </span>
              )}
            </p>
          </div>

          {/* Card results */}
          <div className="space-y-2">
            {data.items.map((card) => (
              <CardResult
                key={card.id}
                card={card}
                isOwned={ownedCardIds.has(card.id)}
                isPending={pendingCardIds.has(card.id)}
                onAdd={() => handleAdd(card.id)}
                onRemove={() => handleRemove(card.id)}
              />
            ))}
          </div>

          {/* Pagination controls */}
          {data.total_pages > 1 && (
            <div className="flex items-center justify-center gap-4 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={data.page <= 1}
                className="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                ← Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {data.page} of {data.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={data.page >= data.total_pages}
                className="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

interface CardResultProps {
  card: CardSearchResult;
  isOwned: boolean;
  isPending: boolean;
  onAdd: () => void;
  onRemove: () => void;
}

function CardResult({ card, isOwned, isPending, onAdd, onRemove }: CardResultProps) {
  return (
    <div
      className={`flex items-center gap-4 rounded-lg border p-3 transition-colors ${
        isOwned ? "bg-green-50 border-green-200" : "bg-white border-gray-200"
      }`}
    >
      {/* Card image */}
      {card.image_url ? (
        <img
          src={card.image_url}
          alt={card.pokemon_name ?? card.api_card_id ?? "Card"}
          className="w-14 h-20 object-contain rounded shrink-0"
          loading="lazy"
        />
      ) : (
        <div className="w-14 h-20 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-xs shrink-0">
          No img
        </div>
      )}

      {/* Card info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {card.pokemon_name && (
            <span className="font-semibold text-gray-900 capitalize">
              {card.pokemon_name}
            </span>
          )}
          {card.national_dex_number && (
            <span className="text-xs text-gray-400 font-mono">
              #{card.national_dex_number}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 text-xs text-gray-500">
          {card.set_name && (
            <span className="font-medium">{card.set_name}</span>
          )}
          {card.set_code && (
            <span className="uppercase font-mono bg-gray-100 px-1.5 py-0.5 rounded">
              {card.set_code}
            </span>
          )}
          {card.rarity && <span>{card.rarity}</span>}
          {card.card_number && <span>#{card.card_number}</span>}
        </div>
      </div>

      {/* Owned badge */}
      {isOwned && (
        <span className="text-xs font-semibold text-green-700 bg-green-100 px-2 py-0.5 rounded-full shrink-0">
          ✓
        </span>
      )}

      {/* Action button */}
      <button
        onClick={isOwned ? onRemove : onAdd}
        disabled={isPending}
        className={`shrink-0 text-xs font-semibold px-3 py-1.5 rounded-md transition-colors disabled:opacity-50 ${
          isOwned
            ? "bg-red-100 text-red-700 hover:bg-red-200"
            : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
        }`}
        aria-label={isOwned ? "Remove from collection" : "Add to collection"}
      >
        {isPending ? "..." : isOwned ? "Remove" : "Add"}
      </button>
    </div>
  );
}
