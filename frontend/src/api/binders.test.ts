import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import {
  addPlacement,
  createBinder,
  deleteBinder,
  getBinderPage,
  listBinders,
  movePlacement,
  removePlacement,
  setDefaultBinder,
} from "./binders";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("binders API client", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn(() => Promise.resolve(jsonResponse({})));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("listBinders GETs /binders", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await listBinders();
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/binders");
    // Default fetch (GET) has no explicit method in apiClient.get
    expect((init as RequestInit).method ?? "GET").toBe("GET");
  });

  it("createBinder POSTs to /binders with body", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 1 }));
    await createBinder({ name: "Trades", binder_type: "FREE_PLACEMENT", rows: 3, columns: 3 });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/binders");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toMatchObject({
      name: "Trades",
      binder_type: "FREE_PLACEMENT",
    });
  });

  it("getBinderPage GETs /binders/{id}/page?page=N", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ binder_type: "POKEDEX", slots: [] }));
    await getBinderPage(7, 3);
    const url = new URL(String(fetchSpy.mock.calls[0][0]));
    expect(url.pathname).toContain("/binders/7/page");
    expect(url.searchParams.get("page")).toBe("3");
  });

  it("setDefaultBinder POSTs to /binders/{id}/default", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 5, is_default: true }));
    await setDefaultBinder(5);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/binders/5/default");
    expect((init as RequestInit).method).toBe("POST");
  });

  it("deleteBinder DELETEs /binders/{id}", async () => {
    fetchSpy.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await deleteBinder(9);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/binders/9");
    expect((init as RequestInit).method).toBe("DELETE");
  });

  it("addPlacement POSTs to /binders/{id}/placements with card/page/slot", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 1 }));
    await addPlacement(2, { card_id: 100, page: 1, slot: 4 });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/binders/2/placements");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      card_id: 100,
      page: 1,
      slot: 4,
    });
  });

  it("movePlacement PATCHes /binders/{id}/placements/{pid}", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 3 }));
    await movePlacement(2, 3, { page: 1, slot: 8 });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/binders/2/placements/3");
    expect((init as RequestInit).method).toBe("PATCH");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ page: 1, slot: 8 });
  });

  it("removePlacement DELETEs /binders/{id}/placements/{pid}", async () => {
    fetchSpy.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await removePlacement(2, 3);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/binders/2/placements/3");
    expect((init as RequestInit).method).toBe("DELETE");
  });
});
