import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useActiveProfile } from "../hooks/useProfiles";
import { useBinderPage } from "../hooks/useBinder";
import { useSpeciesQuery } from "../hooks/useSpeciesQuery";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorState } from "../components/ErrorState";
import { BinderToolbar } from "../components/BinderToolbar";
import type { SearchResult } from "../components/BinderSearch";
import {
  getBinderPage,
  setBinderPage,
  setHighlightDex,
  getHighlightDex,
  clearHighlightDex,
} from "../lib/binderState";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import type { BinderSlot } from "../types";

export function Binder() {
  const navigate = useNavigate();
  const { data: profile } = useActiveProfile();

  const rows = profile?.binder_rows ?? 5;
  const cols = profile?.binder_columns ?? 4;
  const pageSize = rows * cols;
  const totalPages = Math.ceil(NATIONAL_DEX_COUNT / pageSize);

  // Session-persistent page state
  const [page, setPageState] = useState(() => {
    const saved = getBinderPage();
    // Clamp to valid range for current page size
    return Math.max(1, Math.min(Math.ceil(NATIONAL_DEX_COUNT / pageSize), saved));
  });

  const [selectedSlot, setSelectedSlot] = useState<BinderSlot | null>(null);
  const [highlightedDex, setHighlightedDex] = useState<number | null>(() => getHighlightDex());

  const searchInputRef = useRef<HTMLInputElement>(null);
  const binderContainerRef = useRef<HTMLDivElement>(null);

  // Sync page to module-level state
  const setPage = useCallback(
    (newPage: number) => {
      const clamped = Math.max(1, Math.min(totalPages, newPage));
      setPageState(clamped);
      setBinderPage(clamped);
    },
    [totalPages],
  );

  // Reset page when binder size changes (recalculate total pages)
  useEffect(() => {
    const newTotal = Math.ceil(NATIONAL_DEX_COUNT / pageSize);
    if (page > newTotal) {
      setPage(newTotal);
    }
  }, [pageSize, page, setPage]);

  // Clear highlight after animation
  useEffect(() => {
    if (highlightedDex !== null) {
      const timer = setTimeout(() => {
        setHighlightedDex(null);
        clearHighlightDex();
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [highlightedDex]);

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't navigate while typing in inputs
      const target = e.target as HTMLElement;
      const isInput = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT";

      // Ctrl+F always focuses search
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault();
        searchInputRef.current?.focus();
        return;
      }

      // Escape closes modal or clears search
      if (e.key === "Escape") {
        if (selectedSlot) {
          setSelectedSlot(null);
          return;
        }
        if (document.activeElement === searchInputRef.current) {
          searchInputRef.current?.blur();
          return;
        }
        return;
      }

      // Skip page navigation if focused on an input
      if (isInput) return;

      switch (e.key) {
        case "ArrowLeft":
          e.preventDefault();
          setPage(page - 1);
          break;
        case "ArrowRight":
          e.preventDefault();
          setPage(page + 1);
          break;
        case "Home":
          e.preventDefault();
          setPage(1);
          break;
        case "End":
          e.preventDefault();
          setPage(totalPages);
          break;
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [page, totalPages, selectedSlot, setPage]);

  // Data queries
  const { data, isLoading, error } = useBinderPage({ page, page_size: pageSize });
  const { data: speciesList } = useSpeciesQuery();

  // Search result handler
  function handleSearchSelect(result: SearchResult) {
    setPage(result.page);
    setHighlightDex(result.species.national_dex_number);
    setHighlightedDex(result.species.national_dex_number);
  }

  // Calculate dex range for current page
  const startDex = (page - 1) * pageSize + 1;
  const endDex = Math.min(page * pageSize, NATIONAL_DEX_COUNT);

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)]">
      {/* Header + Toolbar */}
      <div className="flex-shrink-0 space-y-2 pb-3">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">My Binder</h2>
          <p className="text-xs text-gray-400">
            {rows}&times;{cols} layout &bull; {NATIONAL_DEX_COUNT} Pokémon
          </p>
        </div>

        <BinderToolbar
          page={page}
          totalPages={totalPages}
          pageSize={pageSize}
          speciesList={speciesList ?? []}
          onPageChange={setPage}
          onSearchSelect={handleSearchSelect}
          searchInputRef={searchInputRef}
          startDex={startDex}
          endDex={endDex}
        />
      </div>

      {/* Binder content — fills remaining space */}
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

      {data && (
        <div ref={binderContainerRef} className="flex-1 min-h-0 flex items-center justify-center">
          <div
            className="bg-gradient-to-br from-slate-700 to-slate-800 rounded-xl p-3 shadow-inner w-full h-full max-h-full"
            style={{
              /* Constrain to maintain aspect ratio within available space */
              maxWidth: `calc((100vh - 12rem) * ${cols * 2.5} / ${rows * 3.5})`,
            }}
          >
            <div
              className="grid gap-2 h-full"
              style={{
                gridTemplateColumns: `repeat(${cols}, 1fr)`,
                gridTemplateRows: `repeat(${rows}, 1fr)`,
              }}
            >
              {data.slots.map((slot, index) => (
                <BinderPocket
                  key={slot.dex_number ?? `pad-${index}`}
                  slot={slot}
                  isHighlighted={slot.dex_number === highlightedDex}
                  onClick={() => {
                    if (slot.owned && slot.species_id) {
                      setSelectedSlot(slot);
                    }
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Card detail modal */}
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
    </div>
  );
}

// ---------------------------------------------------------------------------
// Binder Pocket
// ---------------------------------------------------------------------------

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

  // Padding slot (beyond 1025)
  if (slot.dex_number === null) {
    return (
      <div className="rounded-lg border-2 border-dashed border-slate-600/30 bg-slate-700/20" />
    );
  }

  // State 1: Not owned — empty pocket
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

  // State 2: Owned, but no card — owned placeholder
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

  // State 3: Owned with card — show actual card image
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

      {/* Quantity badge */}
      {slot.total_cards > 1 && (
        <span className="absolute bottom-0.5 right-0.5 bg-indigo-600 text-white text-[8px] font-bold px-1 py-0.5 rounded-full shadow-md min-w-[14px] text-center leading-none">
          &times;{slot.total_cards}
        </span>
      )}

      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors rounded" />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Slot Detail Modal
// ---------------------------------------------------------------------------

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
        {/* Card image or placeholder */}
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

        {/* Details */}
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
