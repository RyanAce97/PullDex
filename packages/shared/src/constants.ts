/**
 * Shared PullDex constants. Kept in sync with the desktop frontend/backend so
 * both platforms use the same values.
 */

/** Total species in the National Pokédex (matches desktop NATIONAL_DEX_COUNT). */
export const NATIONAL_DEX_COUNT = 1025;

/** Binder grid layout bounds (rows and columns), inclusive. */
export const MIN_BINDER_DIMENSION = 2;
export const MAX_BINDER_DIMENSION = 5;

/** Default Pokédex binder layout (matches desktop profile defaults). */
export const DEFAULT_BINDER_ROWS = 5;
export const DEFAULT_BINDER_COLUMNS = 4;

/** Useful preset binder layouts (mirrors desktop BINDER_LAYOUT_PRESETS). */
export const BINDER_LAYOUT_PRESETS: { rows: number; columns: number; label: string }[] = [
  { rows: 3, columns: 3, label: "3×3" },
  { rows: 3, columns: 4, label: "3×4" },
  { rows: 3, columns: 5, label: "3×5" },
  { rows: 4, columns: 3, label: "4×3" },
  { rows: 4, columns: 4, label: "4×4" },
  { rows: 4, columns: 5, label: "4×5" },
];

/** Valid binder sort orders (mirrors desktop VALID_BINDER_SORTS). */
export const VALID_BINDER_SORTS = ["dex_number", "set", "card_number", "recent"] as const;
