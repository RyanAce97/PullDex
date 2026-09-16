import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "../App";
import { useSetSummaries } from "../hooks/useSetSummaries";
import { useRecommendations } from "../hooks/useRecommendations";
import { useCardDataUpdate } from "../hooks/useCardDataUpdate";
import type { SetSummaryRead, RecommendationResponse } from "../types";

// Mock the data hooks so pages render without network.
vi.mock("../hooks/useSetSummaries", () => ({ useSetSummaries: vi.fn() }));
vi.mock("../hooks/useRecommendations", () => ({ useRecommendations: vi.fn() }));
vi.mock("../hooks/useCardDataUpdate", () => ({ useCardDataUpdate: vi.fn() }));
// RecommendationCard pulls in router/query deps we don't need here.
vi.mock("../components/RecommendationCard", () => ({
  RecommendationCard: ({ rec }: { rec: { set_name: string } }) => <div>{rec.set_name}</div>,
}));

const summaries: SetSummaryRead[] = [
  {
    set_id: 1, api_set_id: "sv1", name: "Scarlet & Violet", series: "SV",
    release_date: "2023-01-01", is_promo: false,
    total_species_in_set: 5, owned_species_in_set: 1, missing_species_in_set: 4,
  },
  {
    set_id: 2, api_set_id: "svp", name: "SV Black Star Promos", series: "SV",
    release_date: "2023-01-01", is_promo: true,
    total_species_in_set: 3, owned_species_in_set: 0, missing_species_in_set: 3,
  },
];

const recResponse: RecommendationResponse = {
  total_species: 100, owned_species: 40, total_missing_species: 60,
  recommendations: [{
    rank: 1, set_id: 1, api_set_id: "sv1", set_name: "Scarlet & Violet", series: "SV",
    release_date: "2023-01-01", missing_species_count: 4, total_species_in_set: 5,
    total_cards_in_set: 10, coverage_percentage: 10, missing_species_density_percentage: 40,
  }],
};

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(useSetSummaries).mockReturnValue({ data: summaries, isLoading: false, error: null } as ReturnType<typeof useSetSummaries>);
  vi.mocked(useRecommendations).mockReturnValue({ data: recResponse, isLoading: false, error: null } as ReturnType<typeof useRecommendations>);
  // CardDataStatus renders nothing while "loading" — keeps the header simple.
  vi.mocked(useCardDataUpdate).mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null } as ReturnType<typeof useCardDataUpdate>);
});

describe("Recommendations navigation — three destinations", () => {
  it("nav exposes Recommendations, Sets and Promos as sibling destinations", () => {
    renderAt("/recommendations");
    const nav = screen.getByRole("navigation");
    // The three sibling links exist in the Recommendations dropdown group.
    expect(within(nav).getAllByRole("link", { name: "Recommendations" }).length).toBeGreaterThanOrEqual(1);
    expect(within(nav).getByRole("link", { name: "Sets" })).toHaveAttribute("href", "/sets");
    expect(within(nav).getByRole("link", { name: "Promos" })).toHaveAttribute("href", "/promos");
  });

  it("direct route /recommendations renders the Recommendations page WITH its Sets/Promos tabs", () => {
    renderAt("/recommendations");
    expect(screen.getByRole("heading", { name: "Pack Recommendations" })).toBeInTheDocument();
    // The on-page tabs still exist and work.
    expect(screen.getByTestId("recommendation-tab-sets")).toBeInTheDocument();
    expect(screen.getByTestId("recommendation-tab-promos")).toBeInTheDocument();
  });

  it("direct route /sets renders the dedicated Sets page (non-promo only)", () => {
    renderAt("/sets");
    expect(screen.getByTestId("set-catalogue-sets")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Set Explorer" })).toBeInTheDocument();
    expect(screen.getByText("Scarlet & Violet")).toBeInTheDocument();
    expect(screen.queryByText("SV Black Star Promos")).not.toBeInTheDocument();
  });

  it("direct route /promos renders the dedicated Promos page (promo only)", () => {
    renderAt("/promos");
    expect(screen.getByTestId("set-catalogue-promos")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Promo Explorer" })).toBeInTheDocument();
    expect(screen.getByText("SV Black Star Promos")).toBeInTheDocument();
    expect(screen.queryByText("Scarlet & Violet")).not.toBeInTheDocument();
  });
});

describe("Active navigation state", () => {
  function recommendationsTopLink() {
    const nav = screen.getByRole("navigation");
    // The parent/primary "Recommendations" link is the dropdown trigger.
    return within(nav).getAllByRole("link", { name: "Recommendations" })[0];
  }

  it("Recommendations parent is highlighted on /recommendations, /sets and /promos", () => {
    for (const path of ["/recommendations", "/sets", "/promos"]) {
      const { unmount } = renderAt(path);
      const link = recommendationsTopLink();
      expect(link.className).toContain("bg-indigo-100");
      unmount();
    }
  });

  it("Recommendations parent is NOT highlighted on an unrelated route", () => {
    renderAt("/collection");
    const link = recommendationsTopLink();
    expect(link.className).not.toContain("bg-indigo-100");
  });
});
