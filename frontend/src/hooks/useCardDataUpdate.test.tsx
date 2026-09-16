import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";

import { useCardDataUpdate } from "./useCardDataUpdate";
import type { CardDataUpdateStatusRead } from "../types";

function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client }, children);
}

const UP_TO_DATE: CardDataUpdateStatusRead = {
  status: "UP_TO_DATE",
  local_data_version: 1,
  remote_data_version: 1,
  remote_schema_version: 1,
  remote_set_count: 178,
  remote_card_count: 20900,
  update_available: false,
  error: null,
  sets: [],
};

describe("useCardDataUpdate", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the read-only /card-data/update-check endpoint exactly once", async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify(UP_TO_DATE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { result } = renderHook(() => useCardDataUpdate(), { wrapper: wrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("UP_TO_DATE");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const calledUrl = String(fetchSpy.mock.calls[0][0]);
    expect(calledUrl).toContain("/card-data/update-check");

    // Read-only: it must be a GET (never a POST/PUT/PATCH/DELETE that could
    // trigger an update or a database write).
    const init = fetchSpy.mock.calls[0][1] as RequestInit | undefined;
    const method = (init?.method ?? "GET").toUpperCase();
    expect(method).toBe("GET");
  });

  it("REMOTE_UNAVAILABLE (mapped to HTTP 200) does not surface as an error", async () => {
    fetchSpy.mockResolvedValue(
      new Response(
        JSON.stringify({
          ...UP_TO_DATE,
          status: "REMOTE_UNAVAILABLE",
          remote_data_version: null,
          error: "Could not reach card-data manifest",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const { result } = renderHook(() => useCardDataUpdate(), { wrapper: wrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.isError).toBe(false);
    expect(result.current.data?.status).toBe("REMOTE_UNAVAILABLE");
  });
});
