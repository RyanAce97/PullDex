import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";

import { FreePlacementGrid } from "./FreePlacementGrid";
import type { FreePlacementPage, FreePlacementSlot } from "../../types";

function card(overrides: Partial<NonNullable<FreePlacementSlot["card"]>> = {}) {
  return {
    card_id: 100,
    api_card_id: "sv1-1",
    card_number: "001/198",
    rarity: "Common",
    image_url: "https://img/1.png",
    species_id: 1,
    pokemon_name: "bulbasaur",
    national_dex_number: 1,
    set_name: "SV",
    set_code: "sv1",
    ...overrides,
  };
}

function page(slots: FreePlacementSlot[], rows = 2, columns = 2): FreePlacementPage {
  return {
    binder_type: "FREE_PLACEMENT",
    page: 1,
    page_size: rows * columns,
    total_pages: 1,
    rows,
    columns,
    slots,
  };
}

function fourSlots(overrides: Partial<Record<number, FreePlacementSlot>> = {}): FreePlacementSlot[] {
  const base: FreePlacementSlot[] = [0, 1, 2, 3].map((slot) => ({
    slot,
    placement_id: null,
    card: null,
    is_concept: false,
  }));
  return base.map((s) => overrides[s.slot] ?? s);
}

describe("FreePlacementGrid", () => {
  it("renders owned card normally (no Concept indicator, not desaturated)", () => {
    const slots = fourSlots({
      0: { slot: 0, placement_id: 10, card: card(), is_concept: false },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={vi.fn()} onRemove={vi.fn()} onView={vi.fn()} />,
    );

    const slot0 = screen.getByTestId("free-slot-0");
    expect(slot0).toHaveAttribute("data-concept", "false");
    expect(within(slot0).queryByText("Concept")).not.toBeInTheDocument();
    const img = within(slot0).getByRole("img");
    expect(img.className).not.toContain("grayscale");
  });

  it("renders concept card faded with a Concept indicator", () => {
    const slots = fourSlots({
      0: { slot: 0, placement_id: 11, card: card(), is_concept: true },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={vi.fn()} onRemove={vi.fn()} onView={vi.fn()} />,
    );

    const slot0 = screen.getByTestId("free-slot-0");
    expect(slot0).toHaveAttribute("data-concept", "true");
    expect(within(slot0).getByText("Concept")).toBeInTheDocument();
    const img = within(slot0).getByRole("img");
    expect(img.className).toContain("grayscale");
  });

  it("empty slot offers an Add card action", () => {
    const onAdd = vi.fn();
    render(
      <FreePlacementGrid page={page(fourSlots())} onAddToSlot={onAdd} onMove={vi.fn()} onRemove={vi.fn()} onView={vi.fn()} />,
    );
    fireEvent.click(screen.getByLabelText("Add card to slot 1"));
    expect(onAdd).toHaveBeenCalledWith(0);
  });

  it("clicking a filled card opens the viewer via onView", () => {
    const onView = vi.fn();
    const slots = fourSlots({
      0: { slot: 0, placement_id: 10, card: card(), is_concept: false },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={vi.fn()} onRemove={vi.fn()} onView={onView} />,
    );
    fireEvent.click(screen.getByLabelText("View bulbasaur"));
    expect(onView).toHaveBeenCalledTimes(1);
    expect(onView.mock.calls[0][0].slot).toBe(0);
  });

  it("concept card can still be viewed (viewer works, styling preserved)", () => {
    const onView = vi.fn();
    const slots = fourSlots({
      0: { slot: 0, placement_id: 11, card: card(), is_concept: true },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={vi.fn()} onRemove={vi.fn()} onView={onView} />,
    );
    fireEvent.click(screen.getByLabelText("View bulbasaur (concept)"));
    expect(onView).toHaveBeenCalledTimes(1);
  });

  it("Move does not trigger the viewer (stopPropagation)", () => {
    const onView = vi.fn();
    const onMove = vi.fn();
    const slots = fourSlots({
      0: { slot: 0, placement_id: 42, card: card(), is_concept: false },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={onMove} onRemove={vi.fn()} onView={onView} />,
    );
    fireEvent.click(screen.getByLabelText("Move bulbasaur"));
    // Arming move must NOT open the viewer.
    expect(onView).not.toHaveBeenCalled();
    // Then dropping on an empty slot moves it.
    fireEvent.click(screen.getByLabelText("Move card to slot 2"));
    expect(onMove).toHaveBeenCalledWith(42, 1);
  });

  it("Remove does not trigger the viewer (stopPropagation)", () => {
    const onView = vi.fn();
    const onRemove = vi.fn();
    const slots = fourSlots({
      0: { slot: 0, placement_id: 77, card: card(), is_concept: false },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={vi.fn()} onRemove={onRemove} onView={onView} />,
    );
    fireEvent.click(screen.getByLabelText("Remove bulbasaur"));
    expect(onRemove).toHaveBeenCalledWith(77);
    expect(onView).not.toHaveBeenCalled();
  });

  it("clicking another occupied card during Move cancels the move, then views (no lingering move)", () => {
    const onView = vi.fn();
    const onMove = vi.fn();
    const slots = fourSlots({
      0: { slot: 0, placement_id: 42, card: card({ pokemon_name: "bulbasaur" }), is_concept: false },
      1: { slot: 1, placement_id: 43, card: card({ card_id: 200, pokemon_name: "ivysaur" }), is_concept: false },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={onMove} onRemove={vi.fn()} onView={onView} />,
    );

    // Arm move on the first card → the move banner appears.
    fireEvent.click(screen.getByLabelText("Move bulbasaur"));
    expect(screen.getByText(/Select an empty slot to move the card into/i)).toBeInTheDocument();

    // Click the SECOND occupied card → should cancel move AND open the viewer.
    fireEvent.click(screen.getByLabelText("View ivysaur"));

    // Viewer opened for the clicked card.
    expect(onView).toHaveBeenCalledTimes(1);
    expect(onView.mock.calls[0][0].slot).toBe(1);
    // Move was cancelled — banner gone, no move performed.
    expect(screen.queryByText(/Select an empty slot to move the card into/i)).not.toBeInTheDocument();
    expect(onMove).not.toHaveBeenCalled();
  });

  it("clicking an empty slot during Move still performs the move (unchanged)", () => {
    const onMove = vi.fn();
    const onView = vi.fn();
    const slots = fourSlots({
      0: { slot: 0, placement_id: 42, card: card(), is_concept: false },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={onMove} onRemove={vi.fn()} onView={onView} />,
    );
    fireEvent.click(screen.getByLabelText("Move bulbasaur"));
    fireEvent.click(screen.getByLabelText("Move card to slot 3"));
    expect(onMove).toHaveBeenCalledWith(42, 2);
    expect(onView).not.toHaveBeenCalled();
  });

  it("explicit Cancel action clears Move mode", () => {
    const slots = fourSlots({
      0: { slot: 0, placement_id: 42, card: card(), is_concept: false },
    });
    render(
      <FreePlacementGrid page={page(slots)} onAddToSlot={vi.fn()} onMove={vi.fn()} onRemove={vi.fn()} onView={vi.fn()} />,
    );
    fireEvent.click(screen.getByLabelText("Move bulbasaur"));
    expect(screen.getByText(/Select an empty slot to move the card into/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText(/Select an empty slot to move the card into/i)).not.toBeInTheDocument();
  });
});
