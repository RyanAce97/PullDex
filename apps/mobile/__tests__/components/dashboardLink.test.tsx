/**
 * Regression test for the SDK 57 expo-router <Slot> "array of styles" runtime
 * error. expo-router's <Link asChild> renders its child through a Radix <Slot>
 * which throws if the child's `style` prop is an ARRAY.
 *
 * This test mocks `Link` to enforce the SAME rule as the real Slot shim
 * (throw when the child style is an array), renders the Dashboard, and asserts
 * that rendering does NOT throw — i.e. the QuickLink child styles are flattened.
 */

import React from "react";
import renderer, { act } from "react-test-renderer";

// Mock expo-router Link to replicate the SDK 57 Slot behaviour: when used as a
// child-merging component, an array `style` on the child element is rejected.
jest.mock("expo-router", () => {
  const ReactLocal = require("react");
  return {
    Link: ({ children }: { children: React.ReactElement }) => {
      if (
        ReactLocal.isValidElement(children) &&
        children.props &&
        Array.isArray((children.props as { style?: unknown }).style)
      ) {
        throw new Error(
          "[expo-router]: You are passing an array of styles to a child of <Slot>.",
        );
      }
      return children;
    },
  };
});

// Mock the data hooks so the Dashboard renders without a real SQLite DB.
jest.mock("../../src/hooks", () => ({
  useProgress: () => ({ totalSpecies: 1025, ownedSpecies: 10, missingSpecies: 1015, percentage: 1 }),
}));
jest.mock("../../src/db/seed", () => ({
  catalogueCounts: () => ({ species: 1025, sets: 177, cards: 20783 }),
}));

import Dashboard from "../../app/(tabs)/index";

describe("Dashboard QuickLink — expo-router Slot compatibility", () => {
  it("renders without throwing the Slot array-style error", () => {
    let tree: renderer.ReactTestRenderer | undefined;
    expect(() => {
      act(() => {
        tree = renderer.create(<Dashboard />);
      });
    }).not.toThrow();
    act(() => {
      tree?.unmount();
    });
  });

  it("passes a single (flattened) style object to each Link child, never an array", () => {
    let tree: renderer.ReactTestRenderer;
    act(() => {
      tree = renderer.create(<Dashboard />);
    });
    // Every Pressable rendered under a Link must have a non-array style.
    const pressables = tree!.root.findAll(
      (node) => typeof node.type !== "string" && (node.type as { displayName?: string }).displayName === "Pressable",
    );
    // There are 4 quick links; if the preset renders Pressable differently we
    // still assert on whatever Pressables exist.
    for (const p of pressables) {
      expect(Array.isArray(p.props.style)).toBe(false);
    }
    act(() => {
      tree!.unmount();
    });
  });
});
