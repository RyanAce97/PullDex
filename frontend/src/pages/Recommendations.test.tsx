import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { Recommendations } from "./Recommendations";
import { useRecommendations } from "../hooks/useRecommendations";
import { queryKeys } from "../lib/queryKeys";
import type { RecommendationResponse } from "../types";

vi.mock("../hooks/useRecommendations", () => ({
  useRecommendations: vi.fn(),
}));

// Mock RecommendationCard so both tabs can be asserted to use the SAME
// component without pulling in its router/query dependencies.
vi.mock("../components/RecommendationCard", () => ({
  RecommendationCard: ({ rec }: { rec: { set_id: number; set_name: string } }) => (
    <div data-testid="recommendation-card">{rec.set_name}</div>
  ),
}));

const mockedHook = vi.mocked(useRecommendations);

function resp(names: string[]): RecommendationResponse {
  return {
    total_species: 100,
    owned_species: 40,
    total_missing_species: 60,
    recommendations: names.map((n, i) => ({
      rank: i + 1,
      set_id: i + 1,
      api_set_id: n.toLowerCase(),
      set_name: n,
      series: "Test",
      release_date: "2020-01-01",
      missing_species_count: 3 - i,
      total_species_in_set: 3,
      total_cards_in_set: 10,
      coverage_percentage: 10,
      missing_species_density_percentage: 30,
    })),
  };
}

function hookState(partial: Partial<ReturnType<typeof useRecommendations>>) {
  return { data: undefined, isLoading: false, error: null, ...partial } as ReturnType<
    typeof useRecommendations
  >;
}

function routeByPromos(
  setsData: RecommendationResponse,
  promosData: RecommendationResponse | undefined,
  promosState: Partial<ReturnType<typeof useRecommendations>> = {},
) {
  mockedHook.mockImplementation((_limit?: number, promos?: boolean) => {
    if (promos) return hookState({ data: promosData, ...promosState });
    return hookState({ data: setsData });
  });
}

beforeEach(() => {
  mockedHook.mockReset();
});

describe("Recommendations page — Sets/Promos tabs", () => {
  it("requests both pools: Sets with promos=false and Promos with promos=true", () => {
    routeByPromos(resp(["Set A"]), resp(["Promo X"]));
    render(<Recommendations />);
    expect(mockedHook).toHaveBeenCalledWith(10, false);
    expect(mockedHook).toHaveBeenCalledWith(10, true);
  });

  it("renders two tabs with Sets active by default", () => {
    routeByPromos(resp(["Set A"]), resp(["Promo X"]));
    render(<Recommendations />);
    const setsTab = screen.getByTestId("recommendation-tab-sets");
    const promosTab = screen.getByTestId("recommendation-tab-promos");
    expect(setsTab).toBeInTheDocument();
    expect(promosTab).toBeInTheDocument();
    expect(setsTab).toHaveAttribute("aria-selected", "true");
    expect(promosTab).toHaveAttribute("aria-selected", "false");
  });

  it("shows ONLY the Sets list initially (Promos not rendered)", () => {
    routeByPromos(resp(["Set A", "Set B"]), resp(["Promo X"]));
    render(<Recommendations />);
    const cards = screen.getAllByTestId("recommendation-card");
    expect(cards.map((c) => c.textContent)).toEqual(["Set A", "Set B"]);
    expect(screen.queryByText("Promo X")).not.toBeInTheDocument();
    expect(screen.getByTestId("recommendation-panel-sets")).toBeInTheDocument();
  });

  it("switching to the Promos tab shows ONLY promo cards and hides Sets", () => {
    routeByPromos(resp(["Set A"]), resp(["Promo X", "Promo Y"]));
    render(<Recommendations />);

    fireEvent.click(screen.getByTestId("recommendation-tab-promos"));

    expect(screen.getByTestId("recommendation-tab-promos")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("recommendation-panel-promos")).toBeInTheDocument();
    const cards = screen.getAllByTestId("recommendation-card");
    expect(cards.map((c) => c.textContent)).toEqual(["Promo X", "Promo Y"]);
    expect(screen.queryByText("Set A")).not.toBeInTheDocument();
  });

  it("can switch back to Sets after viewing Promos", () => {
    routeByPromos(resp(["Set A"]), resp(["Promo X"]));
    render(<Recommendations />);
    fireEvent.click(screen.getByTestId("recommendation-tab-promos"));
    expect(screen.getByText("Promo X")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("recommendation-tab-sets"));
    expect(screen.getByText("Set A")).toBeInTheDocument();
    expect(screen.queryByText("Promo X")).not.toBeInTheDocument();
  });

  it("both tabs render the SAME RecommendationCard component", () => {
    routeByPromos(resp(["Set A"]), resp(["Promo X"]));
    render(<Recommendations />);
    // Sets tab
    expect(screen.getByTestId("recommendation-card")).toHaveTextContent("Set A");
    // Promos tab
    fireEvent.click(screen.getByTestId("recommendation-tab-promos"));
    expect(screen.getByTestId("recommendation-card")).toHaveTextContent("Promo X");
  });

  it("empty Promos shows the empty-state message", () => {
    routeByPromos(resp(["Set A"]), resp([]));
    render(<Recommendations />);
    fireEvent.click(screen.getByTestId("recommendation-tab-promos"));
    expect(screen.getByTestId("recommendation-panel-promos")).toHaveTextContent(
      "No promo recommendations available yet.",
    );
  });

  it("Promos tab shows its own loading state when pending", () => {
    routeByPromos(resp(["Set A"]), undefined, { isLoading: true });
    render(<Recommendations />);
    fireEvent.click(screen.getByTestId("recommendation-tab-promos"));
    expect(screen.getByTestId("recommendation-panel-promos")).toHaveTextContent(/Loading promos/i);
  });
});

describe("queryKeys.recommendations", () => {
  it("differs between Sets (false) and Promos (true)", () => {
    expect(JSON.stringify(queryKeys.recommendations(10, false))).not.toEqual(
      JSON.stringify(queryKeys.recommendations(10, true)),
    );
    expect(queryKeys.recommendations(10, false)).toEqual(["recommendations", 10, false]);
    expect(queryKeys.recommendations(10, true)).toEqual(["recommendations", 10, true]);
  });

  it("defaults to non-promo when promos omitted", () => {
    expect(queryKeys.recommendations(10)).toEqual(["recommendations", 10, false]);
  });
});
