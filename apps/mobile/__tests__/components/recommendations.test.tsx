/**
 * Recommendations screen render test. Mirrors desktop terminology ("Pack
 * Recommendations", coverage %, density %, missing species). Mocks the DB layer
 * so it renders a known ranked set without SQLite.
 *
 * Note: useDatabase returns a STABLE object so effects don't re-run every
 * render (a fresh object each call causes an infinite fetch loop under act).
 */

import React from "react";
import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

const mockDb = {};
jest.mock("../../src/db/provider", () => ({ useDatabase: () => mockDb }));

jest.mock("../../src/hooks", () => ({
  useDataVersionValue: () => 0,
  useSummary: () => ({
    progress: { totalSpecies: 1025, ownedSpecies: 100, missingSpecies: 925, percentage: 9.8 },
    totalCatalogueCards: 20783,
    totalSets: 177,
    promoSets: 35,
    ownedCardEntries: 120,
  }),
}));

const REC = {
  rank: 1,
  set_id: 1,
  api_set_id: "sv1",
  set_name: "Scarlet & Violet",
  series: "SV",
  release_date: "2023-03-31",
  missing_species_count: 42,
  total_species_in_set: 100,
  total_cards_in_set: 250,
  coverage_percentage: 4.5,
  missing_species_density_percentage: 16.8,
};

jest.mock("../../src/db/repository", () => ({
  getSetRecommendations: jest.fn(async (_db: unknown, promos: boolean) => ({
    totalMissing: 925,
    recommendations: promos ? [] : [REC],
  })),
  getMissingSpeciesInSet: jest.fn(async () => [
    { id: 4, national_dex_number: 4, name: "charmander", generation: 1 },
  ]),
}));

import Recommendations from "../../app/(tabs)/recommendations";

const METRICS = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 },
};

function texts(tree: renderer.ReactTestRenderer): string {
  return tree.root
    .findAllByType(Text)
    .map((n) => {
      const c = n.props.children;
      return Array.isArray(c) ? c.map((x) => String(x)).join("") : String(c);
    })
    .join(" | ");
}

async function flush() {
  // Let the screen's async effect (getSetRecommendations) resolve + re-render.
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("Recommendations screen", () => {
  it("renders Pack Recommendations with a ranked set, coverage and density", async () => {
    let tree!: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(
        <SafeAreaProvider initialMetrics={METRICS}>
          <Recommendations />
        </SafeAreaProvider>,
      );
    });
    await flush();

    const all = texts(tree);
    expect(all).toContain("Pack Recommendations");
    expect(all).toContain("Scarlet & Violet");
    expect(all).toContain("42");
    expect(all).toContain("4.5%");
    expect(all).toContain("16.8%");
    expect(all).toContain("Sets");
    expect(all).toContain("Promos");
    act(() => tree.unmount());
  });
});
