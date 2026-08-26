/**
 * Module-level state for Binder page persistence within a session.
 *
 * The current binder page survives React component unmount/remount
 * (navigating away and back), but resets when the application is
 * fully closed and reopened (module re-evaluation).
 *
 * No localStorage, no database — purely in-memory for the SPA lifetime.
 */

let _currentPage = 1;
let _highlightDex: number | null = null;

export function getBinderPage(): number {
  return _currentPage;
}

export function setBinderPage(page: number): void {
  _currentPage = page;
}

export function getHighlightDex(): number | null {
  return _highlightDex;
}

export function setHighlightDex(dex: number | null): void {
  _highlightDex = dex;
}

export function clearHighlightDex(): void {
  _highlightDex = null;
}
