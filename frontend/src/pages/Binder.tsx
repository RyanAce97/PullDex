import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useBinders, useBinderPageQuery, useAddPlacement, useMovePlacement, useRemovePlacement } from "../hooks/useBinders";
import { useSpeciesQuery } from "../hooks/useSpeciesQuery";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorState } from "../components/ErrorState";
import { BinderToolbar } from "../components/BinderToolbar";
import { BinderControls } from "../components/binder/BinderControls";
import { FreePlacementGrid } from "../components/binder/FreePlacementGrid";
import { CardPicker } from "../components/binder/CardPicker";
import { CardPreviewModal } from "../components/CardPreviewModal";
import { ApiError } from "../api/client";
import type { SearchResult } from "../components/BinderSearch";
import {
  getBinderPage as getBinderPageState,
  setBinderPage as setBinderPageState,
  setHighlightDex,
  getHighlightDex,
  clearHighlightDex,
} from "../lib/binderState";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import type {
  BinderSlot,
  CardSearchResult,
  FreePlacementPage,
  FreePlacementSlot,
  PokedexBinderPage,
} from "../types";

export function Binder() {
  const { data: binders, isLoading: bindersLoading, error: bindersError } = useBinders();

  const [selectedBinderId, setSelectedBinderId] = useState<number | null>(null);

  // Default the selection to the profile's default binder (or the first).
  useEffect(() => {
    if (!binders || binders.length === 0) return;
    if (selectedBinderId && binders.some((b) => b.id === selectedBinderId)) return;
    const def = binders.find((b) => b.is_default) ?? binders[0];
    setSelectedBinderId(def.id);
  }, [binders, selectedBinderId]);

  const selectedBinder = useMemo(
    () => binders?.find((b) => b.id === selectedBinderId) ?? null,
    [binders, selectedBinderId],
  );

  if (bindersLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-10rem)]">
        <LoadingSpinner message="Loading binders..." />
      </div>
    );
  }
  if (bindersError) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-10rem)]">
        <ErrorState message="Failed to load binders." />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)]">
      <div className="flex-shrink-0 space-y-2 pb-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-2xl font-bold">My Binder</h2>
          <BinderControls
            binders={binders ?? []}
            selectedBinderId={selectedBinderId}
            onSelect={setSelectedBinderId}
          />
        </div>
      </div>

      {selectedBinder && selectedBinder.binder_type === "POKEDEX" && (
        <PokedexBinderView binderId={selectedBinder.id} rows={selectedBinder.rows} columns={selectedBinder.columns} />
      )}
      {selectedBinder && selectedBinder.binder_type === "FREE_PLACEMENT" && (
        <FreePlacementBinderView binderId={selectedBinder.id} />
      )}
    </div>
  );
}

// ===========================================================================
// POKEDEX view (preserves original derived National-Dex binder behaviour)
// ===========================================================================

function PokedexBinderView({
  binderId,
  rows,
  columns,
}: {
  binderId: number;
  rows: number;
  columns: number;
}) {
  const navigate = useNavigate();
  const pageSize = rows * columns;
  const totalPages = Math.ceil(NATIONAL_DEX_COUNT / pageSize);

  const [page, setPageInternal] = useState(() => {
    const saved = getBinderPageState();
    return Math.max(1, Math.min(totalPages, saved));
  });
  const [selectedSlot, setSelectedSlot] = useState<BinderSlot | null>(null);
  const [highlightedDex, setHighlightedDex] = useState<number | null>(() => getHighlightDex());

  const setPage = (newPage: number) => {
    const clamped = Math.max(1, Math.min(totalPages, newPage));
    setPageInternal(clamped);
    setBinderPageState(clamped);
  };

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [totalPages]);

  useEffect(() => {
    if (highlightedDex !== null) {
      const timer = setTimeout(() => {
        setHighlightedDex(null);
        clearHighlightDex();
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [highlightedDex]);

  const { data, isLoading, error } = useBinderPageQuery(binderId, page);
  const pokedexData = data && (data as PokedexBinderPage).binder_type === "POKEDEX" ? (data as PokedexBinderPage) : null;
  const { data: speciesList } = useSpeciesQuery();

  function handleSearchSelect(result: SearchResult) {
    setPage(result.page);
    setHighlightDex(result.species.national_dex_number);
    setHighlightedDex(result.species.national_dex_number);
  }

  const startDex = (page - 1) * pageSize + 1;
  const endDex = Math.min(page * pageSize, NATIONAL_DEX_COUNT);

  return (
    <>
      <div className="flex-shrink-0 pb-3">
        <BinderToolbar
          page={page}
          totalPages={totalPages}
          pageSize={pageSize}
          speciesList={speciesList ?? []}
          onPageChange={setPage}
          onSearchSelect={handleSearchSelect}
          searchInputRef={{ current: null }}
          startDex={startDex}
          endDex={endDex}
        />
      </div>

      {isLoading && (
        <div className="flex-1 flex items-center justify-center">
          <LoadingSpinner message="Loading binder..." />
        </div>
      )}
      {error && (
        <div className="flex-1 flex items-center justify-center">
          <ErrorState message="Failed to load binder." />
        </div>
      )}

      {pokedexData && (
        <div className="flex-1 min-h-0 flex items-center justify-center">
          <div
            className="bg-gradient-to-br from-slate-700 to-slate-800 rounded-xl p-3 shadow-inner w-full h-full max-h-full"
            style={{ maxWidth: `calc((100vh - 12rem) * ${columns * 2.5} / ${rows * 3.5})` }}
          >
            <div
              className="grid gap-2 h-full"
              style={{
                gridTemplateColumns: `repeat(${columns}, 1fr)`,
                gridTemplateRows: `repeat(${rows}, 1fr)`,
              }}
            >
              {pokedexData.slots.map((slot, index) => (
                <BinderPocket
                  key={slot.dex_number ?? `pad-${index}`}
                  slot={slot}
                  isHighlighted={slot.dex_number === highlightedDex}
                  onClick={() => {
                    if (slot.owned && slot.species_id) setSelectedSlot(slot);
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {selectedSlot && selectedSlot.species_id && (
        <SlotDetailModal
          slot={selectedSlot}
          onClose={() => setSelectedSlot(null)}
          onViewDetails={() => {
            setSelectedSlot(null);
            navigate(`/pokedex/${selectedSlot.species_id}`, { state: { from: "/binder" } });
          }}
        />
      )}
    </>
  );
}

// ===========================================================================
// FREE_PLACEMENT view
// ===========================================================================

function FreePlacementBinderView({ binderId }: { binderId: number }) {
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [pickerSlot, setPickerSlot] = useState<number | null>(null);
  const [placementError, setPlacementError] = useState<string | null>(null);
  const [viewingSlot, setViewingSlot] = useState<FreePlacementSlot | null>(null);

  const { data, isLoading, error } = useBinderPageQuery(binderId, page);
  const freeData =
    data && (data as FreePlacementPage).binder_type === "FREE_PLACEMENT"
      ? (data as FreePlacementPage)
      : null;

  const addMut = useAddPlacement(binderId);
  const moveMut = useMovePlacement(binderId);
  const removeMut = useRemovePlacement(binderId);

  // The last page a user can navigate to. Cards can be placed on a new page
  // beyond the current maximum, so we always allow going at least one past the
  // highest occupied page.
  const maxOccupiedPage = freeData?.total_pages ?? 1;
  const lastNavigablePage = Math.max(maxOccupiedPage, page);

  function goToPage(target: number) {
    const clamped = Math.max(1, target);
    setPage(clamped);
    setPageInput(String(clamped));
  }

  // Keep the page input in sync when the page changes programmatically.
  if (pageInput !== String(page) && document.activeElement?.getAttribute("data-free-page-input") !== "true") {
    setPageInput(String(page));
  }

  function handleAddToSlot(slot: number) {
    setPlacementError(null);
    setPickerSlot(slot);
  }

  function handleSelectCard(card: CardSearchResult) {
    if (pickerSlot === null) return;
    addMut.mutate(
      { card_id: card.id, page, slot: pickerSlot },
      {
        onSuccess: () => {
          setPickerSlot(null);
          setPlacementError(null);
        },
        onError: (err) => {
          setPlacementError(
            err instanceof ApiError
              ? ((err.body as { detail?: string })?.detail ?? "Failed to add card.")
              : "Failed to add card.",
          );
        },
      },
    );
  }

  function handleMove(placementId: number, targetSlot: number) {
    setPlacementError(null);
    moveMut.mutate(
      { placementId, page, slot: targetSlot },
      {
        onError: (err) => {
          setPlacementError(
            err instanceof ApiError
              ? ((err.body as { detail?: string })?.detail ?? "Failed to move card.")
              : "Failed to move card.",
          );
        },
      },
    );
  }

  function handleRemove(placementId: number) {
    setPlacementError(null);
    removeMut.mutate(placementId);
  }

  return (
    <>
      <div className="flex-shrink-0 pb-3 flex items-center gap-3 flex-wrap">
        {/* Full pager (no Pokémon search — Free Placement holds arbitrary cards) */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => goToPage(1)}
            disabled={page <= 1}
            className="p-1.5 text-sm rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="First page"
            title="First page"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4 2v12l-2-1V3l2-1zm2 6l6-5v10l-6-5z" />
            </svg>
          </button>
          <button
            onClick={() => goToPage(page - 1)}
            disabled={page <= 1}
            className="p-1.5 text-sm rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Previous page"
            title="Previous page"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
              <path d="M10 2L4 8l6 6V2z" />
            </svg>
          </button>
          <span className="flex items-center gap-1 text-sm text-gray-600">
            <span className="text-gray-400">Page</span>
            <input
              type="text"
              inputMode="numeric"
              data-free-page-input="true"
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              onBlur={() => {
                const parsed = parseInt(pageInput, 10);
                if (isNaN(parsed)) {
                  setPageInput(String(page));
                } else {
                  goToPage(parsed);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  const parsed = parseInt(pageInput, 10);
                  if (!isNaN(parsed)) goToPage(parsed);
                  (e.target as HTMLInputElement).blur();
                }
              }}
              className="w-10 text-center px-1 py-0.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              aria-label="Page number"
            />
            <span className="text-gray-400">/ {lastNavigablePage}</span>
          </span>
          <button
            onClick={() => goToPage(page + 1)}
            className="p-1.5 text-sm rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50"
            aria-label="Next page"
            title="Next page"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
              <path d="M6 2l6 6-6 6V2z" />
            </svg>
          </button>
          <button
            onClick={() => goToPage(lastNavigablePage)}
            disabled={page >= lastNavigablePage}
            className="p-1.5 text-sm rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Last page"
            title="Last page"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
              <path d="M12 2v12l2-1V3l-2-1zm-2 6L4 3v10l6-5z" />
            </svg>
          </button>
        </div>
        {placementError && (
          <span className="text-sm text-red-600" role="alert">
            {placementError}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex-1 flex items-center justify-center">
          <LoadingSpinner message="Loading binder..." />
        </div>
      )}
      {error && (
        <div className="flex-1 flex items-center justify-center">
          <ErrorState message="Failed to load binder." />
        </div>
      )}

      {freeData && (
        <div className="flex-1 min-h-0 flex items-center justify-center">
          <div
            className="bg-gradient-to-br from-slate-700 to-slate-800 rounded-xl p-3 shadow-inner w-full h-full max-h-full"
            style={{
              maxWidth: `calc((100vh - 12rem) * ${freeData.columns * 2.5} / ${freeData.rows * 3.5})`,
            }}
          >
            <FreePlacementGrid
              page={freeData}
              onAddToSlot={handleAddToSlot}
              onMove={handleMove}
              onRemove={handleRemove}
              onView={(slot) => setViewingSlot(slot)}
            />
          </div>
        </div>
      )}

      {pickerSlot !== null && (
        <CardPicker
          title={`Add a card to page ${page}, slot ${pickerSlot + 1}`}
          errorMessage={placementError}
          onSelect={handleSelectCard}
          onClose={() => {
            setPickerSlot(null);
            setPlacementError(null);
          }}
        />
      )}

      {/* Card viewer/zoom — reuses the shared CardPreviewModal. Works for
          concept cards too (they still render their Concept styling in the grid). */}
      {viewingSlot?.card?.image_url && (
        <CardPreviewModal
          imageUrl={viewingSlot.card.image_url}
          alt={viewingSlot.card.pokemon_name ?? "Card"}
          details={{
            name: viewingSlot.card.pokemon_name,
            setName: viewingSlot.card.set_name,
            setCode: viewingSlot.card.set_code,
            rarity: viewingSlot.card.rarity,
            cardNumber: viewingSlot.card.card_number,
            dexNumber: viewingSlot.card.national_dex_number,
          }}
          onClose={() => setViewingSlot(null)}
        />
      )}
    </>
  );
}

// ===========================================================================
// POKEDEX pocket + detail modal (unchanged rendering)
// ===========================================================================

function BinderPocket({
  slot,
  isHighlighted,
  onClick,
}: {
  slot: BinderSlot;
  isHighlighted: boolean;
  onClick: () => void;
}) {
  const highlightClass = isHighlighted
    ? "ring-2 ring-yellow-400 ring-offset-1 ring-offset-slate-700 animate-pulse"
    : "";

  if (slot.dex_number === null) {
    return <div className="rounded-lg border-2 border-dashed border-slate-600/30 bg-slate-700/20" />;
  }

  if (!slot.owned) {
    return (
      <div
        className={`rounded-lg border-2 border-dashed border-slate-500/40 bg-slate-600/30 flex flex-col items-center justify-center gap-0.5 overflow-hidden ${highlightClass}`}
      >
        <span className="text-slate-400/60 text-[10px] font-mono">#{slot.dex_number}</span>
        <span className="text-slate-400/40 text-[9px] capitalize truncate max-w-full px-1">
          {slot.species_name}
        </span>
      </div>
    );
  }

  if (!slot.has_card) {
    return (
      <button
        onClick={onClick}
        className={`rounded-lg border-2 border-green-500/50 bg-green-900/20 flex flex-col items-center justify-center gap-0.5 cursor-pointer hover:border-green-400 hover:shadow-lg hover:shadow-green-500/10 transition-all overflow-hidden ${highlightClass}`}
        aria-label={`${slot.species_name} #${slot.dex_number} - owned, no card added`}
      >
        <span className="text-green-400/80 text-base">&#10003;</span>
        <span className="text-green-300/70 text-[9px] font-mono">#{slot.dex_number}</span>
        <span className="text-green-300/60 text-[8px] capitalize truncate max-w-full px-1">
          {slot.species_name}
        </span>
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      className={`rounded-lg border-2 border-slate-400/50 bg-slate-600/40 p-0.5 relative group cursor-pointer hover:border-indigo-400 hover:shadow-lg hover:shadow-indigo-500/20 transition-all overflow-hidden ${highlightClass}`}
      aria-label={`${slot.species_name ?? "Pokémon"} #${slot.dex_number} - click for details`}
    >
      {slot.card?.image_url ? (
        <img
          src={slot.card.image_url}
          alt={slot.species_name ?? "Card"}
          className="w-full h-full object-contain rounded"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full rounded bg-slate-500/30 flex flex-col items-center justify-center text-slate-300 text-[9px] text-center p-0.5 gap-0.5">
          <span className="font-mono text-slate-400">#{slot.dex_number}</span>
          <span className="capitalize font-medium leading-tight">{slot.species_name}</span>
        </div>
      )}
      {slot.total_cards > 1 && (
        <span className="absolute bottom-0.5 right-0.5 bg-indigo-600 text-white text-[8px] font-bold px-1 py-0.5 rounded-full shadow-md min-w-[14px] text-center leading-none">
          &times;{slot.total_cards}
        </span>
      )}
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors rounded" />
    </button>
  );
}

function SlotDetailModal({
  slot,
  onClose,
  onViewDetails,
}: {
  slot: BinderSlot;
  onClose: () => void;
  onViewDetails: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
        <div className="bg-gradient-to-br from-slate-100 to-slate-200 p-6 flex items-center justify-center">
          {slot.has_card && slot.card?.image_url ? (
            <img
              src={slot.card.image_url}
              alt={slot.species_name ?? "Card"}
              className="max-h-72 object-contain rounded-lg shadow-lg"
            />
          ) : slot.has_card ? (
            <div className="w-48 h-64 bg-slate-300 rounded-lg flex items-center justify-center text-slate-500">
              No image available
            </div>
          ) : (
            <div className="w-48 h-64 bg-green-50 border-2 border-green-200 rounded-lg flex flex-col items-center justify-center text-green-700 gap-2">
              <span className="text-3xl">&#10003;</span>
              <span className="text-sm font-medium">Owned</span>
              <span className="text-xs text-green-600">No card added</span>
            </div>
          )}
        </div>

        <div className="p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-gray-900 capitalize">
              {slot.species_name ?? "Unknown"}
            </h3>
            <span className="text-sm text-gray-400 font-mono">#{slot.dex_number}</span>
          </div>

          {slot.has_card && slot.card && (
            <div className="grid grid-cols-2 gap-2 text-sm">
              {slot.card.set_name && (
                <div>
                  <span className="text-gray-500">Set</span>
                  <p className="font-medium text-gray-900">{slot.card.set_name}</p>
                </div>
              )}
              {slot.card.set_code && (
                <div>
                  <span className="text-gray-500">Set Code</span>
                  <p className="font-medium text-gray-900 uppercase">{slot.card.set_code}</p>
                </div>
              )}
              {slot.card.rarity && (
                <div>
                  <span className="text-gray-500">Rarity</span>
                  <p className="font-medium text-gray-900">{slot.card.rarity}</p>
                </div>
              )}
              {slot.card.card_number && (
                <div>
                  <span className="text-gray-500">Card Number</span>
                  <p className="font-medium text-gray-900">#{slot.card.card_number}</p>
                </div>
              )}
            </div>
          )}

          {!slot.has_card && (
            <p className="text-sm text-gray-500">
              This Pokémon is marked as owned but has no card added to the collection. Add a
              card via the detail page to display it in the binder.
            </p>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-gray-100">
            <div className="flex items-center gap-2">
              {slot.has_card && (
                <>
                  <span className="text-sm text-gray-500">Total cards:</span>
                  <span className="text-lg font-bold text-indigo-600">&times;{slot.total_cards}</span>
                </>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={onViewDetails}
                className="px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-md hover:bg-indigo-100 transition-colors"
              >
                {slot.has_card ? "Manage Cards" : "Add Card"}
              </button>
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-sm font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
