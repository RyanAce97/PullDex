import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";

import {
  useAddCardToCollection,
  useRemoveFromCollection,
} from "./useCollection";
import { queryKeys } from "../lib/queryKeys";

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapperFor(client: QueryClient) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client }, children);
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("useCollection — invalidates multi-binder pages on ownership change", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn(() => Promise.resolve(jsonResponse({ id: 1, card_id: 5, quantity: 1, is_binder_card: false })));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adding a card invalidates the ['binders'] key (Concept → Owned re-derives)", async () => {
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useAddCardToCollection(), {
      wrapper: wrapperFor(client),
    });

    result.current.mutate({ cardId: 5, quantity: 1 });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const keys = invalidate.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toContain(JSON.stringify(queryKeys.binders));
  });

  it("removing a card invalidates the ['binders'] key (Owned → Concept re-derives)", async () => {
    fetchSpy.mockResolvedValue(new Response(null, { status: 204 }));
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useRemoveFromCollection(), {
      wrapper: wrapperFor(client),
    });

    result.current.mutate(1);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const keys = invalidate.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toContain(JSON.stringify(queryKeys.binders));
  });
});
