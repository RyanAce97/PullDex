import { useState } from "react";

import { useCardDataUpdate } from "../hooks/useCardDataUpdate";
import { useUpdateCardData } from "../hooks/useUpdateCardData";
import type { CardDataUpdateStatus } from "../types";

/**
 * Card-data update status + action (Stage 2B).
 *
 * Shows an unobtrusive indicator of whether newer card *reference* data is
 * available (from the read-only Stage 1 manifest check). When an update is
 * available it offers an "Update Card Data" button that performs the real
 * update: download + validate + backup + atomic merge (handled entirely by
 * the backend). User data is never modified.
 *
 * The button is disabled while an update is in flight (duplicate-click
 * protection), a loading state is shown, and the result (success or a safe
 * failure message) is displayed. On success the catalogue queries are
 * refreshed by the mutation hook and the status re-checked.
 *
 * Resilience: while the check is loading, or if it fails entirely, this
 * component renders nothing and never blocks or breaks the surrounding UI.
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
  const updateMutation = useUpdateCardData();
  const [resultOpen, setResultOpen] = useState(false);

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

  const isUpdating = updateMutation.isPending;
  const result = updateMutation.data;

  function handleUpdateClick() {
    // Duplicate-click protection: ignore clicks while an update is running.
    if (isUpdating) return;
    updateMutation.mutate(undefined, {
      onSettled: () => setResultOpen(true),
    });
  }

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
          onClick={handleUpdateClick}
          disabled={isUpdating}
          aria-busy={isUpdating}
          className="text-xs font-medium px-2 py-1 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-1"
          data-testid="card-data-update-button"
        >
          {isUpdating && (
            <svg
              className="animate-spin h-3 w-3"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isUpdating ? "Updating…" : "Update Card Data"}
        </button>
      )}

      {isUpdating && (
        <span className="text-xs text-gray-500" data-testid="card-data-updating">
          Updating card data…
        </span>
      )}

      {resultOpen && result && (
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
              {result.success ? "Card Data Updated" : "Card Data Update Failed"}
            </h2>
            <p
              className="mt-2 text-sm text-gray-600"
              data-testid="card-data-result-message"
              data-result-status={result.status}
            >
              {result.message}
            </p>
            {result.status === "UPDATED" && (
              <p className="mt-1 text-xs text-gray-500" data-testid="card-data-result-detail">
                Now at data version {result.local_data_version}
                {typeof result.card_count === "number" && typeof result.set_count === "number"
                  ? ` — ${result.card_count.toLocaleString()} cards across ${result.set_count.toLocaleString()} sets.`
                  : "."}
              </p>
            )}
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => setResultOpen(false)}
                className="text-sm font-medium px-3 py-2 rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                data-testid="card-data-dialog-close"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {resultOpen && !result && updateMutation.isError && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          role="dialog"
          aria-modal="true"
          aria-labelledby="card-data-dialog-title"
          data-testid="card-data-update-dialog"
        >
          <div className="bg-white rounded-lg border border-gray-200 shadow-lg p-6 max-w-sm w-full mx-4">
            <h2 id="card-data-dialog-title" className="text-lg font-semibold text-gray-900">
              Card Data Update Failed
            </h2>
            <p className="mt-2 text-sm text-gray-600" data-testid="card-data-result-message">
              The card-data update could not be completed. No changes were made.
            </p>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => setResultOpen(false)}
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
