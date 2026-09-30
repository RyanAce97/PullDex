import { useState } from "react";

import type { FreePlacementPage, FreePlacementSlot } from "../../types";

interface FreePlacementGridProps {
  page: FreePlacementPage;
  /** Add a card to an empty slot. */
  onAddToSlot: (slot: number) => void;
  /** Move a placement to an empty slot. */
  onMove: (placementId: number, targetSlot: number) => void;
  /** Remove a placement. */
  onRemove: (placementId: number) => void;
  /** Open the card viewer/zoom for a filled slot. */
  onView: (slot: FreePlacementSlot) => void;
}

/**
 * The grid for a FREE_PLACEMENT binder page.
 *
 * - Empty slots show an obvious "Add card" affordance.
 * - Owned cards render normally; concept (not-owned) cards render faded /
 *   desaturated with a clear "Concept" indicator.
 * - Clicking a card opens the shared card viewer (zoom). Move and Remove are
 *   hover buttons that stop propagation so they never trigger the viewer.
 * - Moving uses a simple two-step interaction (no drag-and-drop dependency):
 *   click "Move" on a card to arm it, then click any empty slot to drop it.
 * - Clicking another OCCUPIED card while Move mode is active cancels the move
 *   first, then opens the viewer — so the UI is never simultaneously viewing a
 *   card while a stale move operation lingers underneath.
 */
export function FreePlacementGrid({
  page,
  onAddToSlot,
  onMove,
  onRemove,
  onView,
}: FreePlacementGridProps) {
  const { rows, columns, slots } = page;
  const [movingPlacementId, setMovingPlacementId] = useState<number | null>(null);

  function handleEmptySlotClick(slot: number) {
    if (movingPlacementId !== null) {
      onMove(movingPlacementId, slot);
      setMovingPlacementId(null);
    } else {
      onAddToSlot(slot);
    }
  }

  function handleViewSlot(slot: FreePlacementSlot) {
    // If a Move is armed, clicking another (occupied) card must not leave the
    // move active underneath the viewer. Cancel the move first, then view.
    if (movingPlacementId !== null) {
      setMovingPlacementId(null);
    }
    onView(slot);
  }

  return (
    <div className="w-full h-full flex flex-col">
      {movingPlacementId !== null && (
        <div className="mb-2 flex items-center justify-between rounded-md bg-indigo-50 border border-indigo-200 px-3 py-1.5 text-sm text-indigo-800">
          <span>Select an empty slot to move the card into.</span>
          <button
            onClick={() => setMovingPlacementId(null)}
            className="text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Cancel
          </button>
        </div>
      )}

      <div
        className="grid gap-2 flex-1 min-h-0"
        style={{
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
        }}
      >
        {slots.map((slot) => (
          <FreeSlot
            key={slot.slot}
            slot={slot}
            isMoving={movingPlacementId === slot.placement_id && slot.placement_id !== null}
            moveModeActive={movingPlacementId !== null}
            onEmptyClick={() => handleEmptySlotClick(slot.slot)}
            onView={() => handleViewSlot(slot)}
            onStartMove={() => setMovingPlacementId(slot.placement_id)}
            onRemove={() => slot.placement_id != null && onRemove(slot.placement_id)}
          />
        ))}
      </div>
    </div>
  );
}

function FreeSlot({
  slot,
  isMoving,
  moveModeActive,
  onEmptyClick,
  onView,
  onStartMove,
  onRemove,
}: {
  slot: FreePlacementSlot;
  isMoving: boolean;
  moveModeActive: boolean;
  onEmptyClick: () => void;
  onView: () => void;
  onStartMove: () => void;
  onRemove: () => void;
}) {
  // Empty slot
  if (!slot.card) {
    return (
      <button
        onClick={onEmptyClick}
        className="rounded-lg border-2 border-dashed border-slate-500/40 bg-slate-600/20 flex flex-col items-center justify-center gap-1 text-slate-400 hover:border-indigo-400 hover:text-indigo-300 transition-colors"
        aria-label={moveModeActive ? `Move card to slot ${slot.slot + 1}` : `Add card to slot ${slot.slot + 1}`}
      >
        <span className="text-2xl leading-none">+</span>
        <span className="text-[10px]">{moveModeActive ? "Move here" : "Add card"}</span>
      </button>
    );
  }

  const card = slot.card;
  const concept = slot.is_concept;

  return (
    <button
      type="button"
      onClick={onView}
      className={`relative rounded-lg border-2 p-0.5 group overflow-hidden cursor-zoom-in text-left ${
        isMoving
          ? "border-indigo-500 ring-2 ring-indigo-400"
          : concept
            ? "border-amber-400/50 bg-slate-700/40"
            : "border-slate-400/50 bg-slate-600/40"
      }`}
      data-testid={`free-slot-${slot.slot}`}
      data-concept={concept ? "true" : "false"}
      aria-label={`View ${card.pokemon_name ?? "card"}${concept ? " (concept)" : ""}`}
    >
      {card.image_url ? (
        <img
          src={card.image_url}
          alt={card.pokemon_name ?? "Card"}
          className={`w-full h-full object-contain rounded ${concept ? "grayscale opacity-60" : ""}`}
          loading="lazy"
        />
      ) : (
        <div
          className={`w-full h-full rounded bg-slate-500/30 flex flex-col items-center justify-center text-slate-300 text-[9px] text-center p-0.5 gap-0.5 ${
            concept ? "opacity-70" : ""
          }`}
        >
          <span className="capitalize font-medium leading-tight">
            {card.pokemon_name ?? card.api_card_id}
          </span>
        </div>
      )}

      {/* Concept indicator */}
      {concept && (
        <span className="absolute top-0.5 left-0.5 bg-amber-400 text-amber-950 text-[8px] font-bold px-1 py-0.5 rounded shadow">
          Concept
        </span>
      )}

      {/* Hover actions — stopPropagation so they don't open the viewer */}
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors rounded flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100">
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.stopPropagation();
            onStartMove();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              e.stopPropagation();
              onStartMove();
            }
          }}
          className="px-1.5 py-0.5 text-[10px] font-medium bg-white/90 text-gray-800 rounded hover:bg-white cursor-pointer"
          aria-label={`Move ${card.pokemon_name ?? "card"}`}
        >
          Move
        </span>
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              e.stopPropagation();
              onRemove();
            }
          }}
          className="px-1.5 py-0.5 text-[10px] font-medium bg-red-500/90 text-white rounded hover:bg-red-600 cursor-pointer"
          aria-label={`Remove ${card.pokemon_name ?? "card"}`}
        >
          Remove
        </span>
      </div>
    </button>
  );
}
