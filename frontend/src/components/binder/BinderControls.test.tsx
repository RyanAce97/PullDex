import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { BinderControls } from "./BinderControls";
import type { Binder } from "../../types";

// Mock the binder mutation hooks so the component can render without a
// QueryClient. Each returns a stub mutation object.
vi.mock("../../hooks/useBinders", () => {
  const stub = () => ({ mutate: vi.fn(), isPending: false });
  return {
    useCreateBinder: stub,
    useUpdateBinder: stub,
    useSetDefaultBinder: stub,
    useDeleteBinder: stub,
  };
});

function binder(overrides: Partial<Binder>): Binder {
  return {
    id: 1,
    profile_id: 1,
    name: "Pokédex Binder",
    binder_type: "POKEDEX",
    rows: 3,
    columns: 3,
    sort_order: "dex_number",
    is_default: true,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("BinderControls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a selector listing all binders", () => {
    const binders = [
      binder({ id: 1, name: "Pokédex Binder", is_default: true }),
      binder({ id: 2, name: "Trades", binder_type: "FREE_PLACEMENT", is_default: false }),
    ];
    render(<BinderControls binders={binders} selectedBinderId={1} onSelect={vi.fn()} />);

    const select = screen.getByLabelText("Select binder") as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Pokédex Binder/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Trades/ })).toBeInTheDocument();
  });

  it("selecting a different binder calls onSelect", () => {
    const onSelect = vi.fn();
    const binders = [
      binder({ id: 1, name: "A" }),
      binder({ id: 2, name: "B", is_default: false }),
    ];
    render(<BinderControls binders={binders} selectedBinderId={1} onSelect={onSelect} />);
    fireEvent.change(screen.getByLabelText("Select binder"), { target: { value: "2" } });
    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it("disables Delete and explains when only one binder exists", () => {
    const binders = [binder({ id: 1, name: "Only", is_default: true })];
    render(<BinderControls binders={binders} selectedBinderId={1} onSelect={vi.fn()} />);

    // Open the manage modal.
    fireEvent.click(screen.getByRole("button", { name: "Manage Binders" }));

    const deleteBtn = screen.getByRole("button", { name: "Delete" });
    expect(deleteBtn).toBeDisabled();
    expect(
      screen.getByText(/must create another binder before you can delete/i),
    ).toBeInTheDocument();
  });

  it("enables Delete when multiple binders exist", () => {
    const binders = [
      binder({ id: 1, name: "A", is_default: true }),
      binder({ id: 2, name: "B", is_default: false }),
    ];
    render(<BinderControls binders={binders} selectedBinderId={1} onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Manage Binders" }));

    const deleteButtons = screen.getAllByRole("button", { name: "Delete" });
    expect(deleteButtons.length).toBe(2);
    deleteButtons.forEach((btn) => expect(btn).not.toBeDisabled());
  });

  it("create modal offers both types when no Pokédex binder exists yet", () => {
    // Only a Free Placement binder present -> Pokédex option should be available.
    const binders = [binder({ id: 1, name: "Trades", binder_type: "FREE_PLACEMENT", is_default: true })];
    render(<BinderControls binders={binders} selectedBinderId={1} onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "+ Create Binder" }));
    expect(screen.getByRole("button", { name: "Pokédex" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Free Placement" })).toBeInTheDocument();
  });

  it("create modal hides the Pokédex type when a Pokédex binder already exists", () => {
    // Default binder is POKEDEX -> a second one is not allowed, option hidden.
    render(
      <BinderControls
        binders={[binder({ id: 1 })]}
        selectedBinderId={1}
        onSelect={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "+ Create Binder" }));
    expect(screen.queryByRole("button", { name: "Pokédex" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Free Placement" })).toBeInTheDocument();
    expect(screen.getByText(/only have one/i)).toBeInTheDocument();
  });
});
