import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { CardDataStatus, describeCardDataStatus } from "./CardDataStatus";
import { useCardDataUpdate } from "../hooks/useCardDataUpdate";
import type { CardDataUpdateStatusRead } from "../types";

// Mock the data hook so component tests never touch the network. Each test
// drives a specific status through this mock.
vi.mock("../hooks/useCardDataUpdate", () => ({
  useCardDataUpdate: vi.fn(),
}));

const mockedHook = vi.mocked(useCardDataUpdate);

/** Build a hook return value in the "success" shape TanStack Query would give. */
function hookResult(
  partial: Partial<ReturnType<typeof useCardDataUpdate>>,
): ReturnType<typeof useCardDataUpdate> {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    // Only the fields the component reads matter; cast the rest.
    ...partial,
  } as ReturnType<typeof useCardDataUpdate>;
}

function statusData(
  overrides: Partial<CardDataUpdateStatusRead> = {},
): CardDataUpdateStatusRead {
  return {
    status: "UP_TO_DATE",
    local_data_version: 1,
    remote_data_version: 1,
    remote_schema_version: 1,
    remote_set_count: 178,
    remote_card_count: 20900,
    update_available: false,
    error: null,
    sets: [],
    ...overrides,
  };
}

describe("describeCardDataStatus (pure)", () => {
  it("UP_TO_DATE has no button", () => {
    const v = describeCardDataStatus("UP_TO_DATE");
    expect(v.message).toBe("Card data is up to date");
    expect(v.showUpdateButton).toBe(false);
  });

  it("UPDATE_AVAILABLE includes card/set counts and shows a button", () => {
    const v = describeCardDataStatus("UPDATE_AVAILABLE", {
      remoteCardCount: 20900,
      remoteSetCount: 178,
    });
    expect(v.message).toContain("New card data available");
    expect(v.message).toContain("20,900 cards");
    expect(v.message).toContain("178 sets");
    expect(v.showUpdateButton).toBe(true);
  });

  it("UPDATE_AVAILABLE falls back to data version when counts absent", () => {
    const v = describeCardDataStatus("UPDATE_AVAILABLE", {
      remoteDataVersion: 2,
    });
    expect(v.message).toContain("data version 2");
    expect(v.showUpdateButton).toBe(true);
  });

  it("REMOTE_UNAVAILABLE is subtle and buttonless", () => {
    const v = describeCardDataStatus("REMOTE_UNAVAILABLE");
    expect(v.message).toBe("Card data update check unavailable");
    expect(v.showUpdateButton).toBe(false);
  });

  it("INVALID_MANIFEST is generic and buttonless", () => {
    const v = describeCardDataStatus("INVALID_MANIFEST");
    expect(v.message).toBe("Card data update check failed");
    expect(v.showUpdateButton).toBe(false);
  });

  it("INCOMPATIBLE_SCHEMA explains incompatibility, no button", () => {
    const v = describeCardDataStatus("INCOMPATIBLE_SCHEMA");
    expect(v.message).toBe(
      "Card data update is not compatible with this version of PullDex",
    );
    expect(v.showUpdateButton).toBe(false);
  });
});

describe("CardDataStatus (component)", () => {
  beforeEach(() => {
    mockedHook.mockReset();
  });

  it("renders nothing while the check is loading (non-blocking startup)", () => {
    mockedHook.mockReturnValue(hookResult({ isLoading: true }));
    const { container } = render(<CardDataStatus />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing if the request itself errors (app stays usable)", () => {
    mockedHook.mockReturnValue(hookResult({ isError: true, error: new Error("x") }));
    const { container } = render(<CardDataStatus />);
    expect(container).toBeEmptyDOMElement();
  });

  it("UP_TO_DATE renders the up-to-date message and no update button", () => {
    mockedHook.mockReturnValue(hookResult({ data: statusData({ status: "UP_TO_DATE" }) }));
    render(<CardDataStatus />);
    expect(screen.getByText("Card data is up to date")).toBeInTheDocument();
    expect(screen.queryByTestId("card-data-update-button")).not.toBeInTheDocument();
  });

  it("UPDATE_AVAILABLE renders message with counts and an Update button", () => {
    mockedHook.mockReturnValue(
      hookResult({
        data: statusData({
          status: "UPDATE_AVAILABLE",
          remote_data_version: 2,
          remote_card_count: 20900,
          remote_set_count: 178,
          update_available: true,
        }),
      }),
    );
    render(<CardDataStatus />);
    const msg = screen.getByTestId("card-data-status-message");
    expect(msg).toHaveTextContent("New card data available");
    expect(msg).toHaveTextContent("20,900 cards across 178 sets");
    expect(screen.getByTestId("card-data-update-button")).toHaveTextContent(
      "Update Card Data",
    );
  });

  it("shows the Update button ONLY for UPDATE_AVAILABLE", () => {
    const nonUpdate: CardDataUpdateStatusRead["status"][] = [
      "UP_TO_DATE",
      "REMOTE_UNAVAILABLE",
      "INVALID_MANIFEST",
      "INCOMPATIBLE_SCHEMA",
    ];
    for (const status of nonUpdate) {
      mockedHook.mockReturnValue(hookResult({ data: statusData({ status }) }));
      const { unmount } = render(<CardDataStatus />);
      expect(screen.queryByTestId("card-data-update-button")).not.toBeInTheDocument();
      unmount();
    }
  });

  it("REMOTE_UNAVAILABLE renders a subtle status without breaking the UI", () => {
    mockedHook.mockReturnValue(
      hookResult({ data: statusData({ status: "REMOTE_UNAVAILABLE", remote_data_version: null }) }),
    );
    render(<CardDataStatus />);
    expect(screen.getByText("Card data update check unavailable")).toBeInTheDocument();
  });

  it("INVALID_MANIFEST renders a safe generic status (no crash)", () => {
    mockedHook.mockReturnValue(hookResult({ data: statusData({ status: "INVALID_MANIFEST" }) }));
    render(<CardDataStatus />);
    expect(screen.getByText("Card data update check failed")).toBeInTheDocument();
  });

  it("INCOMPATIBLE_SCHEMA is displayed safely", () => {
    mockedHook.mockReturnValue(hookResult({ data: statusData({ status: "INCOMPATIBLE_SCHEMA" }) }));
    render(<CardDataStatus />);
    expect(
      screen.getByText(
        "Card data update is not compatible with this version of PullDex",
      ),
    ).toBeInTheDocument();
  });
});

describe("CardDataStatus — Stage 2A button is non-functional", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockedHook.mockReset();
    // Spy on fetch to prove NO network download happens on click.
    fetchSpy = vi.fn(() =>
      Promise.resolve(new Response("{}", { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("clicking Update Card Data only shows an informational dialog", () => {
    mockedHook.mockReturnValue(
      hookResult({
        data: statusData({ status: "UPDATE_AVAILABLE", update_available: true }),
      }),
    );
    render(<CardDataStatus />);

    fireEvent.click(screen.getByTestId("card-data-update-button"));

    const dialog = screen.getByTestId("card-data-update-dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveTextContent(
      "Card data updates will be available in a future update.",
    );
  });

  it("clicking Update Card Data performs NO network request (no download)", () => {
    mockedHook.mockReturnValue(
      hookResult({
        data: statusData({ status: "UPDATE_AVAILABLE", update_available: true }),
      }),
    );
    render(<CardDataStatus />);

    fireEvent.click(screen.getByTestId("card-data-update-button"));

    // The whole point of Stage 2A: the button downloads nothing and hits no
    // endpoint. fetch must never be called as a result of the click.
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("the dialog can be closed again", () => {
    mockedHook.mockReturnValue(
      hookResult({
        data: statusData({ status: "UPDATE_AVAILABLE", update_available: true }),
      }),
    );
    render(<CardDataStatus />);

    fireEvent.click(screen.getByTestId("card-data-update-button"));
    expect(screen.getByTestId("card-data-update-dialog")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("card-data-dialog-close"));
    expect(screen.queryByTestId("card-data-update-dialog")).not.toBeInTheDocument();
  });
});
