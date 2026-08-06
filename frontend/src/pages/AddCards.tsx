import { useCallback, useRef, useState } from "react";
import { useCardSearch } from "../hooks/useCardSearch";
import {
  useAddCardToCollection,
  useCollectionEntries,
  useRemoveFromCollection,
} from "../hooks/useCollection";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import type { CardSearchResult } from "../types";

export function AddCards() {
  const [search, setSearch] = useState("");
  const { data: cards, isLoading, error } = useCardSearch(search);
  const { data: collection } = useCollectionEntries();

  const addMutation = useAddCardToCollection();
  const removeMutation = useRemoveFromCollection();

  const [pendingCardIds, setPendingCardIds] = useState<Set<number>>(
    () => new Set(),
  );
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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Add Cards</h2>
        <p className="text-sm text-gray-500 mt-1">
          Search by Pokémon name, card number, set code, or set name.
        </p>
      </div>

      {/* Search input */}
      <input
        type="text"
        placeholder="e.g. pikachu, sv1-25, 58/165, base set..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        autoFocus
        className="w-full rounded-md border border-gray-300 px-4 py-3 text-sm shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        aria-label="Search cards"
      />

      {/* Results */}
      {search.length < 2 && (
        <EmptyState
          icon="🔍"
          message="Type at least 2 characters to search for cards."
        />
      )}

      {search.length >= 2 && isLoading && (
        <LoadingSpinner message="Searching cards..." />
      )}

      {search.length >= 2 && error && (
        <ErrorState message="Failed to search cards." />
      )}

      {search.length >= 2 && cards && cards.length === 0 && (
        <EmptyState icon="🃏" message={`No cards found for "${search}".`} />
      )}

      {cards && cards.length > 0 && (
        <>
          <p className="text-sm text-gray-500">
            {cards.length} cards found
          </p>
          <div className="space-y-2">
            {cards.map((card) => (
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
          alt={card.api_card_id ?? "Card"}
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
          {card.card_number && <span>#{card.card_number}</span>}
          {card.rarity && <span>{card.rarity}</span>}
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
