import { useState } from "react";

import { useCardDataUpdate } from "../hooks/useCardDataUpdate";
import type { CardDataUpdateStatus } from "../types";

/**
 * Card-data update status (Stage 2A — display only).
 *
 * Shows an unobtrusive indicator of whether newer card *reference* data is
 * available, based on the read-only Stage 1 manifest check. When an update is
 * available it offers an "Update Card Data" button — but in Stage 2A that
 * button is intentionally non-functional: it neither downloads anything nor
 * modifies the database. It only opens an informational dialog.
 *
 * Resilience: while the check is loading, or if it fails entirely, this
 * component renders nothing (or a subtle "unavailable" note) and never blocks
 * or breaks the surrounding UI.
 */

/** Visual treatment + copy for each possible status. */
interface StatusPresentation {
  /** Small colored dot classes. */
  dotClass: string;
  /** Text color classes. */
  textClass: string;
  /** Whether this state is "quiet" (subtle, low-emphasis). */
  subtle: boolean;
}

const STATUS_STYLES: Record<CardDataUpdateStatus, StatusPresentation> = {
  UP_TO_DATE: {
    dotClass: "bg-green-500",
    textClass: "text-gray-500",
    subtle: true,
  },
  UPDATE_AVAILABLE: {
    dotClass: "bg-indigo-500",
    textClass: "text-indigo-700",
    subtle: false,
  },
  REMOTE_UNAVAILABLE: {
    dotClass: "bg-gray-300",
    textClass: "text-gray-400",
    subtle: true,
  },
  INVALID_MANIFEST: {
    dotClass: "bg-gray-300",
    textClass: "text-gray-400",
    subtle: true,
  },
  INCOMPATIBLE_SCHEMA: {
    dotClass: "bg-amber-500",
    textClass: "text-amber-700",
    subtle: false,
  },
};

interface StatusView {
  message: string;
  showUpdateButton: boolean;
}

/**
 * Build the human-facing message (and whether to show the update button) for a
 * given status. Kept as a pure function so it is trivially unit-testable.
 */
export function describeCardDataStatus(
  status: CardDataUpdateStatus,
  opts: {
    remoteDataVersion?: number | null;
    remoteCardCount?: number | null;
    remoteSetCount?: number | null;
  } = {},
): StatusView {
  switch (status) {
    case "UP_TO_DATE":
      return { message: "Card data is up to date", showUpdateButton: false };

    case "UPDATE_AVAILABLE": {
      const { remoteCardCount, remoteSetCount, remoteDataVersion } = opts;
      let detail = "";
      if (
        typeof remoteCardCount === "number" &&
        typeof remoteSetCount === "number"
      ) {
        const cards = remoteCardCount.toLocaleString();
        const sets = remoteSetCount.toLocaleString();
        detail = ` — ${cards} cards across ${sets} sets.`;
      } else if (typeof remoteDataVersion === "number") {
        detail = ` (data version ${remoteDataVersion}).`;
      }
      return {
        message: `New card data available${detail}`,
        showUpdateButton: true,
      };
    }

    case "REMOTE_UNAVAILABLE":
      return {
        message: "Card data update check unavailable",
        showUpdateButton: false,
      };

    case "INVALID_MANIFEST":
      return {
        message: "Card data update check failed",
        showUpdateButton: false,
      };

    case "INCOMPATIBLE_SCHEMA":
      return {
        message: "Card data update is not compatible with this version of PullDex",
        showUpdateButton: false,
      };

    default:
      // Exhaustiveness guard — an unknown status is treated as "unavailable"
      // so the UI never breaks on an unexpected value.
      return {
        message: "Card data update check unavailable",
        showUpdateButton: false,
      };
  }
}

export function CardDataStatus() {
  const { data, isLoading, isError } = useCardDataUpdate();
  const [dialogOpen, setDialogOpen] = useState(false);

  // Never block or clutter the UI while the background check is in flight.
  if (isLoading) return null;

  // If the request itself failed (should be rare — the backend maps expected
  // failures to 200), stay quiet rather than showing a broken state.
  if (isError || !data) return null;

  const style = STATUS_STYLES[data.status] ?? STATUS_STYLES.REMOTE_UNAVAILABLE;
  const view = describeCardDataStatus(data.status, {
    remoteDataVersion: data.remote_data_version,
    remoteCardCount: data.remote_card_count,
    remoteSetCount: data.remote_set_count,
  });

  return (
    <div className="flex items-center gap-2" data-testid="card-data-status">
      <span
        className={`inline-block h-2 w-2 rounded-full ${style.dotClass}`}
        aria-hidden="true"
      />
      <span
        className={`text-xs ${style.textClass}`}
        data-testid="card-data-status-message"
        data-status={data.status}
      >
        {view.message}
      </span>

      {view.showUpdateButton && (
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="text-xs font-medium px-2 py-1 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
          data-testid="card-data-update-button"
        >
          Update Card Data
        </button>
      )}

      {dialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          role="dialog"
          aria-modal="true"
          aria-labelledby="card-data-dialog-title"
          data-testid="card-data-update-dialog"
        >
          <div className="bg-white rounded-lg border border-gray-200 shadow-lg p-6 max-w-sm w-full mx-4">
            <h2
              id="card-data-dialog-title"
              className="text-lg font-semibold text-gray-900"
            >
              Card Data Update
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              Card data updates will be available in a future update.
            </p>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => setDialogOpen(false)}
                className="text-sm font-medium px-3 py-2 rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                data-testid="card-data-dialog-close"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
