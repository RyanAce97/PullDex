/**
 * PullDex mobile theme. Uses the desktop PullDex indigo accent (#4f46e5) and
 * provides light/dark palettes derived from the system color scheme.
 */

import { useColorScheme } from "react-native";

export interface Theme {
  mode: "light" | "dark";
  bg: string;
  card: string;
  cardAlt: string;
  border: string;
  text: string;
  textMuted: string;
  accent: string;
  accentText: string;
  owned: string;
  ownedBg: string;
  missing: string;
  missingBg: string;
  concept: string;
}

const ACCENT = "#4f46e5"; // indigo-600 — PullDex brand

const light: Theme = {
  mode: "light",
  bg: "#f8fafc",
  card: "#ffffff",
  cardAlt: "#f1f5f9",
  border: "#e2e8f0",
  text: "#0f172a",
  textMuted: "#64748b",
  accent: ACCENT,
  accentText: "#ffffff",
  owned: "#15803d",
  ownedBg: "#dcfce7",
  missing: "#b91c1c",
  missingBg: "#fee2e2",
  concept: "#b45309",
};

const dark: Theme = {
  mode: "dark",
  bg: "#0f172a",
  card: "#1e293b",
  cardAlt: "#334155",
  border: "#334155",
  text: "#f1f5f9",
  textMuted: "#94a3b8",
  accent: "#818cf8",
  accentText: "#0f172a",
  owned: "#4ade80",
  ownedBg: "#14532d",
  missing: "#f87171",
  missingBg: "#7f1d1d",
  concept: "#fbbf24",
};

export function useTheme(): Theme {
  const scheme = useColorScheme();
  return scheme === "dark" ? dark : light;
}
