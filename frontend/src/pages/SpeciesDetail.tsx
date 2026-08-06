import { useCallback, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useSpeciesDetail } from "../hooks/useSpeciesDetail";
import {
  useAddToCollection,
  useRemoveFromCollection,
} from "../hooks/useCollection";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import type { CardRead } from "../types";

export function SpeciesDetail() {
  const { speciesId } = useParams<{ speciesId: string }>();
  const navigate = useNavigate();
  const numericId = Number(speciesId);

  const { data, isLoading, error } = useSpeciesDetail(numericId);
  const addMutation = useAddToCollection();
  const removeMutation = useRemoveFromCollection();

  // Track which card IDs have in-flight mutations to disable only those buttons.
  const [pendingCardIds, setPendingCardIds] = useState<Set<number>>(
    () => new Set(),
  );

  // Prevent double-click race conditions: track entry IDs already being removed.
  const removingEntryIds = useRef<Set<number>>(new Set());

  const handleAdd = useCallback(
    (cardId: number) => {
      if (pendingCardIds.has(cardId)) return;

      setPendingCardIds((prev) => new Set(prev).add(cardId));
      addMutation.mutate(cardId, {
        onSettled: () => {
          setPendingCardIds((prev) => {
            const next = new Set(prev);
            next.delete(cardId);
            return next;
          });
        },
      });
    },
    [addMutation, pendingCardIds],
  );

  const handleRemove = useCallback(
    (cardId: number) => {
      if (!data || pendingCardIds.has(cardId)) return;

      const entry = data.collectionEntries.find((e) => e.card_id === cardId);
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
    [data, removeMutation, pendingCardIds],
  );

  if (isLoading) {
    return <LoadingSpinner message="Loading species details..." />;
  }

  if (error) {
    return <ErrorState message="Failed to load species data." />;
  }

  if (!data) {
    return <EmptyState icon="❓" message="Species not found." />;
  }

  const { species, owned, cards, ownedCardIds } = data;

  return (
    <div className="space-y-6">
      <button
        onClick={() => navigate("/pokedex")}
        className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
      >
        ← Back to Pokédex
      </button>

      {/* Species header */}
      <div className="flex items-center gap-4">
        <span className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-gray-100 text-gray-700 text-lg font-mono font-bold">
          #{species.national_dex_number}
        </span>
        <div>
          <h2 className="text-2xl font-bold capitalize">{species.name}</h2>
          <div className="flex items-center gap-3 mt-1">
            {species.generation !== null && (
              <span className="text-sm text-gray-500">
                Generation {species.generation}
              </span>
            )}
            <span
              className={`text-xs font-semibold px-2 py-1 rounded-full ${
                owned
                  ? "bg-green-100 text-green-700"
                  : "bg-red-100 text-red-700"
              }`}
            >
              {owned ? "Owned" : "Missing"}
            </span>
          </div>
        </div>
      </div>

      {/* Cards section */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          Cards ({cards.length})
        </h3>

        {cards.length === 0 ? (
          <EmptyState
            icon="🃏"
            message="No cards found for this Pokémon in the database."
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {cards.map((card) => (
              <CardListItem
                key={card.id}
                card={card}
                isOwned={ownedCardIds.has(card.id)}
                onAdd={() => handleAdd(card.id)}
                onRemove={() => handleRemove(card.id)}
                isPending={pendingCardIds.has(card.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface CardListItemProps {
  card: CardRead;
  isOwned: boolean;
  onAdd: () => void;
  onRemove: () => void;
  isPending: boolean;
}

function CardListItem({
  card,
  isOwned,
  onAdd,
  onRemove,
  isPending,
}: CardListItemProps) {
  return (
    <div
      className={`border rounded-lg p-3 flex items-center gap-3 transition-colors ${
        isOwned ? "bg-green-50 border-green-200" : "bg-white border-gray-200"
      }`}
    >
      {card.image_url ? (
        <img
          src={card.image_url}
          alt={card.api_card_id ?? "Card"}
          className="w-16 h-22 object-contain rounded"
          loading="lazy"
        />
      ) : (
        <div className="w-16 h-22 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-xs">
          No image
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">
          {card.api_card_id ?? `Card #${card.id}`}
        </p>
        {card.card_number && (
          <p className="text-xs text-gray-500">#{card.card_number}</p>
        )}
        {card.rarity && (
          <p className="text-xs text-gray-500">{card.rarity}</p>
        )}
      </div>
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
