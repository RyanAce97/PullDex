/**
 * Settings screen render test. Verifies the Pokédex binder layout config,
 * appearance (theme) info, catalogue/app info, and the deferred backup + Sync
 * "coming soon" placeholder. Mocks DB/hooks so no SQLite is needed.
 */

import React from "react";
import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";

jest.mock("../../src/db/provider", () => ({ useDatabase: () => ({}) }));

const mockSave = jest.fn(async () => undefined);
jest.mock("../../src/hooks", () => ({
  useBinderLayout: () => ({ layout: { rows: 5, columns: 4 }, save: mockSave }),
  useSummary: () => ({
    progress: { totalSpecies: 1025, ownedSpecies: 100, missingSpecies: 925, percentage: 9.8 },
    totalCatalogueCards: 20783,
    totalSets: 177,
    promoSets: 35,
    ownedCardEntries: 120,
  }),
}));

jest.mock("../../src/db/repository", () => ({
  getCatalogueGeneratedAt: jest.fn(async () => "2026-01-01T00:00:00Z"),
}));

import Settings from "../../app/(tabs)/settings";

function texts(tree: renderer.ReactTestRenderer): string {
  return tree.root
    .findAllByType(Text)
    .map((n) => {
      const c = n.props.children;
      return Array.isArray(c) ? c.map((x) => String(x)).join("") : String(c);
    })
    .join(" | ");
}

describe("Settings screen", () => {
  it("shows binder layout config, theme, catalogue info, deferred backup + sync", async () => {
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(<Settings />);
    });
    await act(async () => {
      await Promise.resolve();
    });
    const all = texts(tree!);
    expect(all).toContain("Pokédex Binder Layout");
    expect(all).toContain("cards per page");
    expect(all).toContain("Appearance");
    expect(all).toContain("Catalogue & App");
    expect(all).toContain("Backup & Restore");
    expect(all).toContain("Sync");
    expect(all).toContain("Coming soon");
    // Catalogue counts surfaced.
    expect(all).toContain("177");
    act(() => tree!.unmount());
  });
});
