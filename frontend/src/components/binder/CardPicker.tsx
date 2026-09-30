import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useCardSearch } from "../../hooks/useCardSearch";
import { getCollection } from "../../api/collection";
import { queryKeys } from "../../lib/queryKeys";
import type { CardSearchResult } from "../../types";

interface CardPickerProps {
  /** Called with the chosen card. */
  onSelect: (card: CardSearchResult) => void;
  onClose: () => void;
  /** Title shown in the modal header (e.g. "Add card to page 1, slot 3"). */
  title?: string;
  /** Error message to surface (e.g. a 409 from the server). */
  errorMessage?: string | null;
}

/**
 * Modal that searches the FULL card catalogue (owned and unowned) so the user
 * can place any card into a FREE_PLACEMENT binder. Owned cards and concept
 * (not-owned) cards are clearly distinguished.
 *
 * Ownership is derived from the profile's card-level Collection entries.
 */
export function CardPicker({ onSelect, onClose, title, errorMessage }: CardPickerProps) {
  const [query, setQuery] = useState("");

  // Debounce the query a little to avoid a request per keystroke.
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(t);
  }, [query]);

  const { data, isLoading } = useCardSearch({ q: debounced, page: 1, page_size: 40 });

  // Owned card ids (card-level Collection entries) → distinguish owned/concept.
  const { data: collection } = useQuery({
    queryKey: queryKeys.collection,
    queryFn: () => getCollection(1000),
  });
  const ownedCardIds = useMemo(() => {
    const set = new Set<number>();
    (collection ?? []).forEach((entry) => {
      if (entry.card_id != null) set.add(entry.card_id);
    });
    return set;
  }, [collection]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const results = data?.items ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Add a card"
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col overflow-hidden">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-lg font-bold text-gray-900">{title ?? "Add a card"}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="p-4 border-b border-gray-100">
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search the full card catalogue…"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            aria-label="Search cards"
          />
          {errorMessage && (
            <p className="mt-2 text-sm text-red-600" role="alert">
              {errorMessage}
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {debounced.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-8">
              Start typing to search for a card.
            </p>
          )}
          {debounced.length > 0 && isLoading && (
            <p className="text-sm text-gray-500 text-center py-8">Searching…</p>
          )}
          {debounced.length > 0 && !isLoading && results.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-8">No cards found.</p>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {results.map((card) => {
              const owned = ownedCardIds.has(card.id);
              return (
                <button
                  key={card.id}
                  onClick={() => onSelect(card)}
                  className="text-left rounded-lg border border-gray-200 hover:border-indigo-400 hover:shadow-md transition-all overflow-hidden bg-white group"
                  aria-label={`${card.pokemon_name ?? "Card"} — ${owned ? "owned" : "not owned (concept)"}`}
                >
                  <div className="relative aspect-[3/4] bg-slate-100 flex items-center justify-center">
                    {card.image_url ? (
                      <img
                        src={card.image_url}
                        alt={card.pokemon_name ?? "Card"}
                        className={`w-full h-full object-contain ${owned ? "" : "grayscale opacity-70"}`}
                        loading="lazy"
                      />
                    ) : (
                      <span className="text-xs text-gray-400 p-2 text-center">
                        {card.pokemon_name ?? card.api_card_id}
                      </span>
                    )}
                    <span
                      className={`absolute top-1 right-1 text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${
                        owned
                          ? "bg-green-100 text-green-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {owned ? "Owned" : "Concept"}
                    </span>
                  </div>
                  <div className="p-1.5">
                    <p className="text-xs font-medium text-gray-900 capitalize truncate">
                      {card.pokemon_name ?? "—"}
                    </p>
                    <p className="text-[10px] text-gray-500 truncate">
                      {card.set_name ?? card.set_code ?? ""}
                      {card.card_number ? ` · ${card.card_number}` : ""}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
