/**
 * Species detail render/interaction test. Covers:
 *  - richer card info (name, set, variant/type, number, rarity)
 *  - tapping a card image opens the zoom modal
 *  - add / remove ownership calls the mutation
 *  - "Show in Pokédex Binder" representative selection is available
 *
 * useDatabase returns a STABLE object so the data effect doesn't loop.
 */

import React from "react";
import renderer, { act } from "react-test-renderer";
import { Image, Text } from "react-native";

jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ id: "25" }),
}));
const mockDb = {};
jest.mock("../../src/db/provider", () => ({ useDatabase: () => mockDb }));

const mockMutate = jest.fn(async (fn: (db: unknown) => Promise<void>) => {
  await fn({});
});
jest.mock("../../src/hooks", () => ({
  useDataVersionValue: () => 0,
  useMutation: () => mockMutate,
}));

const mockSetBinderCard = jest.fn(async () => undefined);
const mockMarkCardOwned = jest.fn(async () => undefined);
const mockRemoveCard = jest.fn(async () => undefined);

jest.mock("../../src/db/repository", () => ({
  getSpeciesById: jest.fn(async () => ({ id: 25, national_dex_number: 25, name: "pikachu", generation: 1 })),
  getCardsForSpecies: jest.fn(async () => [
    {
      id: 102, api_card_id: "sv1-25", card_number: "025", rarity: "Rare Holo", image_url: "https://img/102.png",
      variant: "Reverse Holo", pokemon_species_id: 25, pokemon_name: "pikachu", national_dex_number: 25,
      set_id: 1, set_name: "Scarlet & Violet", set_code: "sv1", is_promo: false,
    },
    {
      id: 103, api_card_id: "svp-25", card_number: "P25", rarity: "Promo", image_url: "https://img/103.png",
      variant: null, pokemon_species_id: 25, pokemon_name: "pikachu", national_dex_number: 25,
      set_id: 2, set_name: "SV Black Star Promos", set_code: "svp", is_promo: true,
    },
  ]),
  getOwnedCardIds: jest.fn(async () => new Set([102])),
  getRepresentativeCardId: jest.fn(async () => null),
  isSpeciesOwned: jest.fn(async () => true),
  markCardOwned: (...a: unknown[]) => mockMarkCardOwned(...a),
  removeCardOwnership: (...a: unknown[]) => mockRemoveCard(...a),
  setBinderCard: (...a: unknown[]) => mockSetBinderCard(...a),
}));

import SpeciesDetail from "../../app/species/[id]";

async function renderScreen() {
  let tree!: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(<SpeciesDetail />);
  });
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  return tree;
}

function allText(tree: renderer.ReactTestRenderer): string {
  return tree.root
    .findAllByType(Text)
    .map((n) => {
      const c = n.props.children;
      return Array.isArray(c) ? c.map((x) => String(x)).join("") : String(c);
    })
    .join(" | ");
}

describe("Species detail", () => {
  beforeEach(() => jest.clearAllMocks());

  it("shows richer card info: set, variant/type, number, rarity", async () => {
    const tree = await renderScreen();
    const all = allText(tree);
    expect(all).toContain("Scarlet & Violet");
    expect(all).toContain("Reverse Holo");
    expect(all).toContain("#025");
    expect(all).toContain("Rare Holo");
    act(() => tree.unmount());
  });

  it("opens the zoom modal when a card image is tapped", async () => {
    const tree = await renderScreen();
    const zoomButtons = tree.root.findAllByProps({ accessibilityLabel: "Zoom pikachu" });
    expect(zoomButtons.length).toBeGreaterThan(0);
    await act(async () => {
      zoomButtons[0].props.onPress();
    });
    const images = tree.root.findAllByType(Image);
    // Two card thumbnails + the modal's zoomed image.
    expect(images.length).toBeGreaterThan(2);
    act(() => tree.unmount());
  });

  it("adds ownership for an unowned card", async () => {
    const tree = await renderScreen();
    const addBtn = tree.root.findByProps({ accessibilityLabel: "Add pikachu" });
    await act(async () => {
      addBtn.props.onPress();
    });
    expect(mockMarkCardOwned).toHaveBeenCalled();
    act(() => tree.unmount());
  });

  it("removes ownership for an owned card", async () => {
    const tree = await renderScreen();
    const removeBtn = tree.root.findByProps({ accessibilityLabel: "Remove pikachu" });
    await act(async () => {
      removeBtn.props.onPress();
    });
    expect(mockRemoveCard).toHaveBeenCalled();
    act(() => tree.unmount());
  });

  it("offers representative binder card selection for owned cards", async () => {
    const tree = await renderScreen();
    const all = allText(tree);
    expect(all).toContain("Show in Pokédex Binder");
    act(() => tree.unmount());
  });
});
