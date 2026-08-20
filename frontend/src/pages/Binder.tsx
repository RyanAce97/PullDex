import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useActiveProfile } from "../hooks/useProfiles";
import { useBinderPage } from "../hooks/useBinder";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorState } from "../components/ErrorState";
import type { BinderSlot } from "../types";

export function Binder() {
  const navigate = useNavigate();
  const { data: profile } = useActiveProfile();

  const rows = profile?.binder_rows ?? 5;
  const cols = profile?.binder_columns ?? 4;
  const pageSize = rows * cols;

  const [page, setPage] = useState(1);
  const [selectedSlot, setSelectedSlot] = useState<BinderSlot | null>(null);

  // Reset page when binder size changes
  useEffect(() => { setPage(1); }, [pageSize]);

  const { data, isLoading, error } = useBinderPage({ page, page_size: pageSize });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">My Binder</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            National Pokédex • {rows}×{cols} layout
            {data && ` • Page ${data.page} of ${data.total_pages}`}
          </p>
        </div>
        <div className="text-xs text-gray-400 font-mono">
          #{data ? (page - 1) * pageSize + 1 : "..."} – #{data ? Math.min(page * pageSize, 1025) : "..."}
        </div>
      </div>

      {/* Binder content */}
      {isLoading && <LoadingSpinner message="Loading binder..." />}
      {error && <ErrorState message="Failed to load binder." />}

      {data && (
        <>
          {/* Binder grid */}
          <div
            className="bg-gradient-to-br from-slate-700 to-slate-800 rounded-xl p-4 shadow-inner"
            style={{ minHeight: "400px" }}
          >
            <div
              className="grid gap-2.5"
              style={{
                gridTemplateColumns: `repeat(${cols}, 1fr)`,
                gridTemplateRows: `repeat(${rows}, 1fr)`,
              }}
            >
              {data.slots.map((slot, index) => (
                <BinderPocket
                  key={slot.dex_number ?? `pad-${index}`}
                  slot={slot}
                  onClick={() => {
                    if (slot.owned && slot.species_id) {
                      setSelectedSlot(slot);
                    }
                  }}
                />
              ))}
            </div>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => setPage(1)}
              disabled={data.page <= 1}
              className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ⟨⟨
            </button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={data.page <= 1}
              className="px-4 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Previous
            </button>
            <span className="text-sm text-gray-600 min-w-[100px] text-center">
              {data.page} / {data.total_pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
              disabled={data.page >= data.total_pages}
              className="px-4 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next →
            </button>
            <button
              onClick={() => setPage(data.total_pages)}
              disabled={data.page >= data.total_pages}
              className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ⟩⟩
            </button>
          </div>
        </>
      )}

      {/* Card detail modal */}
      {selectedSlot && selectedSlot.species_id && (
        <SlotDetailModal
          slot={selectedSlot}
          onClose={() => setSelectedSlot(null)}
          onViewDetails={() => {
            setSelectedSlot(null);
            navigate(`/pokedex/${selectedSlot.species_id}`);
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
  onClick,
}: {
  slot: BinderSlot;
  onClick: () => void;
}) {
  // Padding slot (beyond 1025)
  if (slot.dex_number === null) {
    return (
      <div className="aspect-[2.5/3.5] rounded-lg border-2 border-dashed border-slate-600/30 bg-slate-700/20" />
    );
  }

  // State 1: Not owned — empty pocket
  if (!slot.owned) {
    return (
      <div className="aspect-[2.5/3.5] rounded-lg border-2 border-dashed border-slate-500/40 bg-slate-600/30 flex flex-col items-center justify-center gap-1">
        <span className="text-slate-400/60 text-xs font-mono">#{slot.dex_number}</span>
        <span className="text-slate-400/40 text-[10px] capitalize truncate max-w-full px-1">
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
        className="aspect-[2.5/3.5] rounded-lg border-2 border-green-500/50 bg-green-900/20 flex flex-col items-center justify-center gap-1 cursor-pointer hover:border-green-400 hover:shadow-lg hover:shadow-green-500/10 transition-all"
        aria-label={`${slot.species_name} #${slot.dex_number} - owned, no card added`}
      >
        <span className="text-green-400/80 text-lg">✓</span>
        <span className="text-green-300/70 text-[10px] font-mono">#{slot.dex_number}</span>
        <span className="text-green-300/60 text-[9px] capitalize truncate max-w-full px-1">
          {slot.species_name}
        </span>
        <span className="text-green-400/50 text-[8px] mt-0.5">No card</span>
      </button>
    );
  }

  // State 3: Owned with card — show actual card image
  return (
    <button
      onClick={onClick}
      className="aspect-[2.5/3.5] rounded-lg border-2 border-slate-400/50 bg-slate-600/40 p-0.5 relative group cursor-pointer hover:border-indigo-400 hover:shadow-lg hover:shadow-indigo-500/20 transition-all overflow-hidden"
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
        <div className="w-full h-full rounded bg-slate-500/30 flex flex-col items-center justify-center text-slate-300 text-[10px] text-center p-0.5 gap-0.5">
          <span className="font-mono text-slate-400">#{slot.dex_number}</span>
          <span className="capitalize font-medium leading-tight">{slot.species_name}</span>
        </div>
      )}

      {/* Quantity badge */}
      {slot.total_cards > 1 && (
        <span className="absolute bottom-0.5 right-0.5 bg-indigo-600 text-white text-[9px] font-bold px-1 py-0.5 rounded-full shadow-md min-w-[16px] text-center leading-none">
          ×{slot.total_cards}
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
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
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
              <span className="text-3xl">✓</span>
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
              This Pokémon is marked as owned but has no card added to the collection.
              Add a card via the detail page to display it in the binder.
            </p>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-gray-100">
            <div className="flex items-center gap-2">
              {slot.has_card && (
                <>
                  <span className="text-sm text-gray-500">Total cards:</span>
                  <span className="text-lg font-bold text-indigo-600">×{slot.total_cards}</span>
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
