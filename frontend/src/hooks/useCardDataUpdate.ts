import { useQuery } from "@tanstack/react-query";
import { getCardDataUpdateStatus } from "../api/cardData";
import { queryKeys } from "../lib/queryKeys";

/**
 * Read-only hook that checks whether newer card reference data is available.
 *
 * Integrated into the normal UI lifecycle (rendered in the app header) so the
 * check runs shortly after startup without blocking it. Design notes that keep
 * PullDex usable regardless of network state:
 *
 *  - The backend endpoint returns HTTP 200 for expected failures
 *    (REMOTE_UNAVAILABLE / INVALID_MANIFEST), so a network problem does not
 *    throw here and never prevents the app from loading.
 *  - `retry: false` avoids hammering the manifest on a flaky connection.
 *  - A long `staleTime` (and no refetch on focus/reconnect) means the manifest
 *    is checked at most once per app session unless explicitly invalidated —
 *    satisfying "avoid repeatedly checking during a single startup".
 *  - The query is not `enabled: false`; it starts automatically but runs in the
 *    background, so it introduces no startup delay for the rest of the UI.
 */
export function useCardDataUpdate() {
  return useQuery({
    queryKey: queryKeys.cardDataUpdate,
    queryFn: getCardDataUpdateStatus,
    // The manifest rarely changes within a session; check it once and cache.
    staleTime: Infinity,
    gcTime: Infinity,
    // Do not retry: the backend already reports unreachable/invalid states as
    // successful 200 responses, and we never want to block or spam on failure.
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  });
}
