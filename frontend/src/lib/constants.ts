/** Maximum number of Pokémon species in the National Pokédex. */
export const NATIONAL_DEX_COUNT = 1025;

/** Binder grid layout bounds (rows and columns), inclusive. */
export const MIN_BINDER_DIMENSION = 2;
export const MAX_BINDER_DIMENSION = 5;

/** Useful preset layouts offered in the binder create/manage UI. */
export const BINDER_LAYOUT_PRESETS: { rows: number; columns: number; label: string }[] = [
  { rows: 3, columns: 3, label: "3×3" },
  { rows: 3, columns: 4, label: "3×4" },
  { rows: 3, columns: 5, label: "3×5" },
  { rows: 4, columns: 3, label: "4×3" },
  { rows: 4, columns: 4, label: "4×4" },
  { rows: 4, columns: 5, label: "4×5" },
];
