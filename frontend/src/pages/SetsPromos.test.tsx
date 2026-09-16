import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { Sets } from "./Sets";
import { Promos } from "./Promos";
import { useSetSummaries } from "../hooks/useSetSummaries";
import type { SetSummaryRead } from "../types";

vi.mock("../hooks/useSetSummaries", () => ({
  useSetSummaries: vi.fn(),
}));

const mockedHook = vi.mocked(useSetSummaries);

function summary(overrides: Partial<SetSummaryRead>): SetSummaryRead {
  return {
    set_id: 1,
    api_set_id: "x",
    name: "X",
    series: "Test",
    release_date: "2020-01-01",
    is_promo: false,
    total_species_in_set: 5,
    owned_species_in_set: 1,
    missing_species_in_set: 4,
    ...overrides,
  };
}

const MIXED: SetSummaryRead[] = [
  summary({ set_id: 1, api_set_id: "sv1", name: "Scarlet & Violet", is_promo: false }),
  summary({ set_id: 2, api_set_id: "base1", name: "Base", is_promo: false }),
  summary({ set_id: 3, api_set_id: "svp", name: "SV Black Star Promos", is_promo: true }),
  summary({ set_id: 4, api_set_id: "mcd22", name: "McDonald's Collection 2022", is_promo: true }),
];

function renderWith(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

beforeEach(() => {
  mockedHook.mockReset();
  mockedHook.mockReturnValue({ data: MIXED, isLoading: false, error: null } as ReturnType<
    typeof useSetSummaries
  >);
});

describe("Sets page — excludes promos", () => {
  it("shows only non-promo sets", () => {
    renderWith(<Sets />);
    expect(screen.getByTestId("set-catalogue-sets")).toBeInTheDocument();
    expect(screen.getByText("Scarlet & Violet")).toBeInTheDocument();
    expect(screen.getByText("Base")).toBeInTheDocument();
    // Promo sets must NOT appear on the Sets page.
    expect(screen.queryByText("SV Black Star Promos")).not.toBeInTheDocument();
    expect(screen.queryByText("McDonald's Collection 2022")).not.toBeInTheDocument();
  });

  it("counts only the non-promo pool", () => {
    renderWith(<Sets />);
    // 2 non-promo sets.
    expect(screen.getByText(/Showing 2 sets/i)).toBeInTheDocument();
  });

  it("uses the Set Explorer heading", () => {
    renderWith(<Sets />);
    expect(screen.getByRole("heading", { name: "Set Explorer" })).toBeInTheDocument();
  });
});

describe("Promos page — only promos", () => {
  it("shows only promo sets", () => {
    renderWith(<Promos />);
    expect(screen.getByTestId("set-catalogue-promos")).toBeInTheDocument();
    expect(screen.getByText("SV Black Star Promos")).toBeInTheDocument();
    expect(screen.getByText("McDonald's Collection 2022")).toBeInTheDocument();
    // Non-promo sets must NOT appear on the Promos page.
    expect(screen.queryByText("Scarlet & Violet")).not.toBeInTheDocument();
    expect(screen.queryByText("Base")).not.toBeInTheDocument();
  });

  it("counts only the promo pool", () => {
    renderWith(<Promos />);
    expect(screen.getByText(/Showing 2 promos/i)).toBeInTheDocument();
  });

  it("uses the Promo Explorer heading", () => {
    renderWith(<Promos />);
    expect(screen.getByRole("heading", { name: "Promo Explorer" })).toBeInTheDocument();
  });

  it("shows the empty state when there are no promo sets", () => {
    mockedHook.mockReturnValue({
      data: [summary({ is_promo: false })],
      isLoading: false,
      error: null,
    } as ReturnType<typeof useSetSummaries>);
    renderWith(<Promos />);
    expect(screen.getByText("No promo sets available yet.")).toBeInTheDocument();
  });
});
