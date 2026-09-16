import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import { getRecommendations } from "./recommendations";
import type { RecommendationResponse } from "../types";

const EMPTY: RecommendationResponse = {
  total_species: 0,
  owned_species: 0,
  total_missing_species: 0,
  recommendations: [],
};

describe("getRecommendations — promos query param", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(EMPTY), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("Sets (default) sends promos=false", async () => {
    await getRecommendations(10, false);
    const url = new URL(String(fetchSpy.mock.calls[0][0]));
    expect(url.pathname).toContain("/recommendations");
    expect(url.searchParams.get("promos")).toBe("false");
    expect(url.searchParams.get("limit")).toBe("10");
  });

  it("Promos sends promos=true", async () => {
    await getRecommendations(10, true);
    const url = new URL(String(fetchSpy.mock.calls[0][0]));
    expect(url.searchParams.get("promos")).toBe("true");
  });

  it("defaults to promos=false when omitted", async () => {
    await getRecommendations();
    const url = new URL(String(fetchSpy.mock.calls[0][0]));
    expect(url.searchParams.get("promos")).toBe("false");
  });
});
