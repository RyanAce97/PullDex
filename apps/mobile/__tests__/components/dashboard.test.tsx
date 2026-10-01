/**
 * Dashboard render tests. The dashboard is info-focused (mirrors desktop):
 * it shows Living Dex progress + stat cards and NO redundant navigation
 * buttons (the bottom tab bar is the primary navigation).
 */

import React from "react";
import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";

jest.mock("../../src/hooks", () => ({
  useSummary: () => ({
    progress: { totalSpecies: 1025, ownedSpecies: 200, missingSpecies: 825, percentage: 19.5 },
    totalCatalogueCards: 20783,
    totalSets: 177,
    promoSets: 35,
    ownedCardEntries: 240,
  }),
}));

import Dashboard from "../../app/(tabs)/index";

function textContent(tree: renderer.ReactTestRenderer): string[] {
  return tree.root.findAllByType(Text).map((n) => {
    const c = n.props.children;
    return Array.isArray(c) ? c.join("") : String(c);
  });
}

describe("Dashboard (info-focused)", () => {
  it("renders the Living Dex Progress heading and stat cards", () => {
    let tree: renderer.ReactTestRenderer;
    act(() => {
      tree = renderer.create(<Dashboard />);
    });
    const texts = textContent(tree!);
    expect(texts.some((s) => s.includes("Living Dex Progress"))).toBe(true);
    expect(texts).toContain("Total Species");
    expect(texts).toContain("Owned");
    expect(texts).toContain("Missing");
    expect(texts).toContain("Completion");
    // Progress numbers present.
    expect(texts.some((s) => s.includes("200 / 1025"))).toBe(true);
    act(() => tree!.unmount());
  });

  it("does not render redundant navigation buttons/quick links", () => {
    let tree: renderer.ReactTestRenderer;
    act(() => {
      tree = renderer.create(<Dashboard />);
    });
    const texts = textContent(tree!);
    // The old quick-link labels must be gone.
    expect(texts.some((s) => s.includes("Card Show Mode"))).toBe(false);
    expect(texts.some((s) => /Fast owned/.test(s))).toBe(false);
    act(() => tree!.unmount());
  });
});
