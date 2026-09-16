import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";

import { useUpdateCardData } from "./useUpdateCardData";
import { queryKeys } from "../lib/queryKeys";
import type { CardDataUpdateResultRead } from "../types";

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapperFor(client: QueryClient) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client }, children);
}

const UPDATED: CardDataUpdateResultRead = {
  status: "UPDATED",
  success: true,
  message: "Card data updated successfully.",
  local_data_version: 2,
  remote_data_version: 2,
  sets_created: 1,
  sets_updated: 0,
  cards_created: 10,
  cards_updated: 2,
  set_count: 178,
  card_count: 20900,
  backup_path: "/tmp/b.db",
  error: null,
};

describe("useUpdateCardData", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs to /card-data/update", async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify(UPDATED), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const client = makeClient();
    const { result } = renderHook(() => useUpdateCardData(), {
      wrapper: wrapperFor(client),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("UPDATED");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/card-data/update");
    expect((init as RequestInit).method).toBe("POST");
  });

  it("invalidates the catalogue queries after a successful UPDATED result", async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify(UPDATED), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateCardData(), {
      wrapper: wrapperFor(client),
    });

    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const invalidatedKeys = invalidate.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(invalidatedKeys).toContain(JSON.stringify(queryKeys.cardDataUpdate));
    expect(invalidatedKeys).toContain(JSON.stringify(queryKeys.setsSummary));
    expect(invalidatedKeys).toContain(JSON.stringify(queryKeys.progress));
  });

  it("does NOT invalidate the catalogue on a non-UPDATED result", async () => {
    fetchSpy.mockResolvedValue(
      new Response(
        JSON.stringify({ ...UPDATED, status: "ALREADY_UP_TO_DATE" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateCardData(), {
      wrapper: wrapperFor(client),
    });

    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const invalidatedKeys = invalidate.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(invalidatedKeys).toContain(JSON.stringify(queryKeys.cardDataUpdate));
    expect(invalidatedKeys).not.toContain(JSON.stringify(queryKeys.setsSummary));
  });
});
