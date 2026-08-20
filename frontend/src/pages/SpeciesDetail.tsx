import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getCardsByDex } from "../api/cards";
import { getCardEntriesForSpecies } from "../api/collection";
import { setBinderCard } from "../api/binder";
import { useSpeciesQuery } from "../hooks/useSpeciesQuery";
import { useMissingSpeciesQuery } from "../hooks/useMissingSpeciesQuery";
import {
  useAddCardToCollection,
  useAddSpeciesToCollection,
  useRemoveFromCollection,
  useRemoveSpeciesFromCollection,
  useUpdateCardQuantity,
} from "../hooks/useCollection";
import { queryKeys } from "../lib/queryKeys";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import type { CardSearchResult, CollectionRead } from "../types";

export function SpeciesDetail() {
  const { speciesId } = useParams<{ speciesId: string }>();
  const navigate = useNavigate();
  const numericId = Number(speciesId);

  const speciesQuery = useSpeciesQuery();
  const missingQuery = useMissingSpeciesQuery();
  const species = speciesQuery.data?.find((s) => s.id === numericId);

  const cardsQuery = useQuery({
    queryKey: queryKeys.cardsByDex(species?.national_dex_number ?? 0),
    queryFn: () => getCardsByDex(species!.national_dex_number),
    enabled: !!species,
  });

  const entriesQuery = useQuery({
    queryKey: ["collection", "species", numericId, "cards"],
    queryFn: () => getCardEntriesForSpecies(numericId),
    enabled: numericId > 0,
  });

  const addSpecies = useAddSpeciesToCollection();
  const removeSpecies = useRemoveSpeciesFromCollection();
  const addCard = useAddCardToCollection();
  const updateQuantity = useUpdateCardQuantity();
  const removeEntry = useRemoveFromCollection();

  const isLoading = speciesQuery.isLoading || missingQuery.isLoading || cardsQuery.isLoading || entriesQuery.isLoading;
  const error = speciesQuery.error || missingQuery.error || cardsQuery.error || entriesQuery.error;

  const [pendingCardIds, setPendingCardIds] = useState<Set<number>>(() => new Set());
  const [settingBinderCardId, setSettingBinderCardId] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const owned = species && missingQuery.data ? !missingQuery.data.has(species.id) : false;
  const cards = cardsQuery.data ?? [];
  const entries = entriesQuery.data ?? [];

  // Map card_id -> collection entry
  const entryByCardId = new Map<number, CollectionRead>();
  for (const e of entries) {
    if (e.card_id !== null) entryByCardId.set(e.card_id, e);
  }

  const handleAddCard = useCallback(
    (cardId: number) => {
      if (pendingCardIds.has(cardId)) return;
      setPendingCardIds((prev) => new Set(prev).add(cardId));
      addCard.mutate(
        { cardId, quantity: 1 },
        {
          onSettled: () => {
            setPendingCardIds((prev) => { const n = new Set(prev); n.delete(cardId); return n; });
          },
        },
      );
    },
    [addCard, pendingCardIds],
  );

  const handleIncrement = useCallback(
    (entry: CollectionRead) => {
      updateQuantity.mutate({ entryId: entry.id, quantity: entry.quantity + 1 });
    },
    [updateQuantity],
  );

  const handleDecrement = useCallback(
    (entry: CollectionRead) => {
      if (entry.quantity <= 1) {
        removeEntry.mutate(entry.id);
      } else {
        updateQuantity.mutate({ entryId: entry.id, quantity: entry.quantity - 1 });
      }
    },
    [updateQuantity, removeEntry],
  );

  const handleSetBinderCard = useCallback(
    async (entryId: number) => {
      setSettingBinderCardId(entryId);
      try {
        await setBinderCard(entryId);
        queryClient.invalidateQueries({ queryKey: ["collection", "species", numericId, "cards"] });
        queryClient.invalidateQueries({ queryKey: ["binder"] });
      } finally {
        setSettingBinderCardId(null);
      }
    },
    [queryClient, numericId],
  );

  if (isLoading) return <LoadingSpinner message="Loading species details..." />;
  if (error) return <ErrorState message="Failed to load species data." />;
  if (!species) return <EmptyState icon="❓" message="Species not found." />;

  return (
    <div className="space-y-6">
      <button
        onClick={() => navigate("/collection")}
        className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
      >
        ← Back to Collection
      </button>

      {/* Species header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-gray-100 text-gray-700 text-lg font-mono font-bold">
            #{species.national_dex_number}
          </span>
          <div>
            <h2 className="text-2xl font-bold capitalize">{species.name}</h2>
            <div className="flex items-center gap-3 mt-1">
              {species.generation !== null && (
                <span className="text-sm text-gray-500">Generation {species.generation}</span>
              )}
              <span
                className={`text-xs font-semibold px-2 py-1 rounded-full ${
                  owned ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                }`}
              >
                {owned ? "✓ Owned" : "Missing"}
              </span>
            </div>
          </div>
        </div>
        {/* Quick species toggle */}
        <button
          onClick={() => owned ? removeSpecies.mutate(numericId) : addSpecies.mutate(numericId)}
          disabled={addSpecies.isPending || removeSpecies.isPending}
          className={`text-sm font-semibold px-4 py-2 rounded-md transition-colors disabled:opacity-50 ${
            owned
              ? "bg-red-100 text-red-700 hover:bg-red-200"
              : "bg-indigo-600 text-white hover:bg-indigo-700"
          }`}
        >
          {owned ? "Remove from Dex" : "Mark as Owned"}
        </button>
      </div>

      {/* Tracked cards section */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          Tracked Cards ({entries.length} tracked)
        </h3>

        {entries.length > 0 && (
          <div className="space-y-2 mb-6">
            {entries.map((entry) => {
              const card = cards.find((c) => c.id === entry.card_id);
              return (
                <TrackedCardRow
                  key={entry.id}
                  entry={entry}
                  card={card}
                  onIncrement={() => handleIncrement(entry)}
                  onDecrement={() => handleDecrement(entry)}
                  onSetBinderCard={() => handleSetBinderCard(entry.id)}
                  isSettingBinder={settingBinderCardId === entry.id}
                />
              );
            })}
          </div>
        )}

        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          Available Cards ({cards.length})
        </h3>

        {cards.length === 0 ? (
          <EmptyState icon="🃏" message="No cards found for this Pokémon in the database." />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {cards.map((card) => (
              <AvailableCardItem
                key={card.id}
                card={card}
                isTracked={entryByCardId.has(card.id)}
                quantity={entryByCardId.get(card.id)?.quantity ?? 0}
                isPending={pendingCardIds.has(card.id)}
                onAdd={() => handleAddCard(card.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function TrackedCardRow({
  entry,
  card,
  onIncrement,
  onDecrement,
  onSetBinderCard,
  isSettingBinder,
}: {
  entry: CollectionRead;
  card: CardSearchResult | undefined;
  onIncrement: () => void;
  onDecrement: () => void;
  onSetBinderCard: () => void;
  isSettingBinder: boolean;
}) {
  return (
    <div className={`flex items-center gap-3 rounded-lg p-3 ${entry.is_binder_card ? "bg-indigo-50 border border-indigo-200" : "bg-green-50 border border-green-200"}`}>
      {card?.image_url ? (
        <img src={card.image_url} alt={card.pokemon_name ?? "Card"} className="w-12 h-16 object-contain rounded" loading="lazy" />
      ) : (
        <div className="w-12 h-16 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-xs">
          No img
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-gray-900 capitalize truncate">
            {card?.pokemon_name ?? `Card #${entry.card_id}`}
          </p>
          {entry.is_binder_card && (
            <span className="text-xs font-semibold text-indigo-600 bg-indigo-100 px-1.5 py-0.5 rounded">
              ★ Binder
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-0.5 text-xs text-gray-500">
          {card?.set_name && <span className="font-medium">{card.set_name}</span>}
          {card?.rarity && <span>{card.rarity}</span>}
          {card?.card_number && <span>#{card.card_number}</span>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {!entry.is_binder_card && (
          <button
            onClick={onSetBinderCard}
            disabled={isSettingBinder}
            className="text-[10px] font-medium text-indigo-600 hover:text-indigo-800 disabled:opacity-50 whitespace-nowrap"
            title="Show in Binder"
          >
            ★ Binder
          </button>
        )}
        <button
          onClick={onDecrement}
          className="w-7 h-7 flex items-center justify-center rounded bg-gray-200 text-gray-700 hover:bg-gray-300 font-bold text-sm"
          aria-label="Decrease quantity"
        >
          −
        </button>
        <span className="text-sm font-semibold w-6 text-center">{entry.quantity}</span>
        <button
          onClick={onIncrement}
          className="w-7 h-7 flex items-center justify-center rounded bg-gray-200 text-gray-700 hover:bg-gray-300 font-bold text-sm"
          aria-label="Increase quantity"
        >
          +
        </button>
      </div>
    </div>
  );
}

function AvailableCardItem({
  card,
  isTracked,
  quantity,
  isPending,
  onAdd,
}: {
  card: CardSearchResult;
  isTracked: boolean;
  quantity: number;
  isPending: boolean;
  onAdd: () => void;
}) {
  return (
    <div
      className={`border rounded-lg p-3 flex flex-col gap-2 transition-colors ${
        isTracked ? "bg-green-50 border-green-200" : "bg-white border-gray-200"
      }`}
    >
      <div className="flex items-start gap-3">
        {card.image_url ? (
          <img src={card.image_url} alt={card.pokemon_name ?? "Card"} className="w-14 h-20 object-contain rounded shrink-0" loading="lazy" />
        ) : (
          <div className="w-14 h-20 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-xs shrink-0">No img</div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 capitalize truncate">
            {card.pokemon_name ?? card.api_card_id ?? `Card #${card.id}`}
          </p>
          {card.set_name && (
            <p className="text-xs text-gray-600 font-medium truncate">{card.set_name}</p>
          )}
          {card.rarity && (
            <p className="text-xs text-gray-500">{card.rarity}</p>
          )}
          {card.card_number && (
            <p className="text-xs text-gray-400">#{card.card_number}</p>
          )}
        </div>
      </div>
      <div className="flex items-center justify-between mt-auto">
        {isTracked ? (
          <span className="text-xs font-semibold text-green-700 bg-green-100 px-2 py-1 rounded-full">
            ×{quantity}
          </span>
        ) : (
          <button
            onClick={onAdd}
            disabled={isPending}
            className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded-md bg-indigo-100 text-indigo-700 hover:bg-indigo-200 disabled:opacity-50"
          >
            {isPending ? "..." : "Add"}
          </button>
        )}
        {card.set_code && (
          <span className="text-xs font-mono text-gray-400 uppercase">{card.set_code}</span>
        )}
      </div>
    </div>
  );
}
