import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { CardDataStatus, describeCardDataStatus } from "./CardDataStatus";
import { useCardDataUpdate } from "../hooks/useCardDataUpdate";
import { useUpdateCardData } from "../hooks/useUpdateCardData";
import type { CardDataUpdateStatusRead, CardDataUpdateResultRead } from "../types";

// Mock both hooks so component tests never touch the network.
vi.mock("../hooks/useCardDataUpdate", () => ({
  useCardDataUpdate: vi.fn(),
}));
vi.mock("../hooks/useUpdateCardData", () => ({
  useUpdateCardData: vi.fn(),
}));

const mockedCheck = vi.mocked(useCardDataUpdate);
const mockedUpdate = vi.mocked(useUpdateCardData);

function checkResult(
  partial: Partial<ReturnType<typeof useCardDataUpdate>>,
): ReturnType<typeof useCardDataUpdate> {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    ...partial,
  } as ReturnType<typeof useCardDataUpdate>;
}

/** Build a mutation-hook stand-in. */
function updateHook(
  partial: Partial<ReturnType<typeof useUpdateCardData>> = {},
): ReturnType<typeof useUpdateCardData> {
  return {
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as ReturnType<typeof useUpdateCardData>;
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

function updateResult(
  overrides: Partial<CardDataUpdateResultRead> = {},
): CardDataUpdateResultRead {
  return {
    status: "UPDATED",
    success: true,
    message: "Card data updated successfully.",
    local_data_version: 2,
    remote_data_version: 2,
    sets_created: 1,
    sets_updated: 0,
    cards_created: 120,
    cards_updated: 3,
    set_count: 178,
    card_count: 20900,
    backup_path: "/tmp/backup.db",
    error: null,
    ...overrides,
  };
}

beforeEach(() => {
  mockedCheck.mockReset();
  mockedUpdate.mockReset();
  mockedUpdate.mockReturnValue(updateHook());
});

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

  it("REMOTE_UNAVAILABLE / INVALID_MANIFEST / INCOMPATIBLE_SCHEMA are buttonless", () => {
    expect(describeCardDataStatus("REMOTE_UNAVAILABLE").showUpdateButton).toBe(false);
    expect(describeCardDataStatus("INVALID_MANIFEST").showUpdateButton).toBe(false);
    expect(describeCardDataStatus("INCOMPATIBLE_SCHEMA").showUpdateButton).toBe(false);
    expect(describeCardDataStatus("REMOTE_UNAVAILABLE").message).toBe(
      "Card data update check unavailable",
    );
    expect(describeCardDataStatus("INVALID_MANIFEST").message).toBe(
      "Card data update check failed",
    );
    expect(describeCardDataStatus("INCOMPATIBLE_SCHEMA").message).toBe(
      "Card data update is not compatible with this version of PullDex",
    );
  });
});

describe("CardDataStatus — rendering", () => {
  it("renders nothing while the check is loading (non-blocking startup)", () => {
    mockedCheck.mockReturnValue(checkResult({ isLoading: true }));
    const { container } = render(<CardDataStatus />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing if the check request errors (app stays usable)", () => {
    mockedCheck.mockReturnValue(checkResult({ isError: true, error: new Error("x") }));
    const { container } = render(<CardDataStatus />);
    expect(container).toBeEmptyDOMElement();
  });

  it("UP_TO_DATE shows the message and no update button", () => {
    mockedCheck.mockReturnValue(checkResult({ data: statusData({ status: "UP_TO_DATE" }) }));
    render(<CardDataStatus />);
    expect(screen.getByText("Card data is up to date")).toBeInTheDocument();
    expect(screen.queryByTestId("card-data-update-button")).not.toBeInTheDocument();
  });

  it("UPDATE_AVAILABLE shows message with counts and an Update button", () => {
    mockedCheck.mockReturnValue(
      checkResult({
        data: statusData({
          status: "UPDATE_AVAILABLE",
          remote_data_version: 2,
          update_available: true,
        }),
      }),
    );
    render(<CardDataStatus />);
    expect(screen.getByTestId("card-data-status-message")).toHaveTextContent(
      "New card data available",
    );
    expect(screen.getByTestId("card-data-update-button")).toHaveTextContent(
      "Update Card Data",
    );
  });

  it("shows the Update button ONLY for UPDATE_AVAILABLE", () => {
    for (const status of ["UP_TO_DATE", "REMOTE_UNAVAILABLE", "INVALID_MANIFEST", "INCOMPATIBLE_SCHEMA"] as const) {
      mockedCheck.mockReturnValue(checkResult({ data: statusData({ status }) }));
      const { unmount } = render(<CardDataStatus />);
      expect(screen.queryByTestId("card-data-update-button")).not.toBeInTheDocument();
      unmount();
    }
  });

  it("REMOTE_UNAVAILABLE / INVALID_MANIFEST / INCOMPATIBLE_SCHEMA render safely", () => {
    for (const [status, text] of [
      ["REMOTE_UNAVAILABLE", "Card data update check unavailable"],
      ["INVALID_MANIFEST", "Card data update check failed"],
      ["INCOMPATIBLE_SCHEMA", "Card data update is not compatible with this version of PullDex"],
    ] as const) {
      mockedCheck.mockReturnValue(checkResult({ data: statusData({ status }) }));
      const { unmount } = render(<CardDataStatus />);
      expect(screen.getByText(text)).toBeInTheDocument();
      unmount();
    }
  });
});

describe("CardDataStatus — update flow (Stage 2B)", () => {
  function availableCheck() {
    mockedCheck.mockReturnValue(
      checkResult({
        data: statusData({ status: "UPDATE_AVAILABLE", remote_data_version: 2, update_available: true }),
      }),
    );
  }

  it("clicking Update Card Data starts the update (calls mutate)", () => {
    availableCheck();
    const mutate = vi.fn();
    mockedUpdate.mockReturnValue(updateHook({ mutate }));

    render(<CardDataStatus />);
    fireEvent.click(screen.getByTestId("card-data-update-button"));

    expect(mutate).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state while updating and disables the button", () => {
    availableCheck();
    mockedUpdate.mockReturnValue(updateHook({ isPending: true }));

    render(<CardDataStatus />);
    const button = screen.getByTestId("card-data-update-button");
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Updating");
    expect(screen.getByTestId("card-data-updating")).toBeInTheDocument();
  });

  it("duplicate-click protection: a click while pending does not call mutate", () => {
    availableCheck();
    const mutate = vi.fn();
    mockedUpdate.mockReturnValue(updateHook({ mutate, isPending: true }));

    render(<CardDataStatus />);
    // Button is disabled while pending; force the handler anyway to prove the
    // in-handler guard also protects against a double submit.
    fireEvent.click(screen.getByTestId("card-data-update-button"));
    expect(mutate).not.toHaveBeenCalled();
  });

  it("renders a success dialog when a result is present and opened", () => {
    availableCheck();
    // Provide a mutate stub that invokes the onSettled callback so the dialog opens.
    const mutate = vi.fn((_vars: unknown, opts?: { onSettled?: () => void }) => {
      opts?.onSettled?.();
    });
    mockedUpdate.mockReturnValue(
      updateHook({ mutate, isSuccess: true, data: updateResult({ status: "UPDATED", local_data_version: 2 }) }),
    );

    render(<CardDataStatus />);
    fireEvent.click(screen.getByTestId("card-data-update-button"));

    const dialog = screen.getByTestId("card-data-update-dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByTestId("card-data-result-message")).toHaveTextContent(
      "Card data updated successfully.",
    );
    expect(screen.getByTestId("card-data-result-detail")).toHaveTextContent(
      "data version 2",
    );
  });

  it("renders a safe failure dialog on a failed update result", () => {
    availableCheck();
    const mutate = vi.fn((_vars: unknown, opts?: { onSettled?: () => void }) => {
      opts?.onSettled?.();
    });
    mockedUpdate.mockReturnValue(
      updateHook({
        mutate,
        isSuccess: true,
        data: updateResult({
          status: "DATABASE_UPDATE_FAILED",
          success: false,
          message: "The card-data update could not be applied; no changes were made.",
          error: "some internal reason",
        }),
      }),
    );

    render(<CardDataStatus />);
    fireEvent.click(screen.getByTestId("card-data-update-button"));

    expect(screen.getByTestId("card-data-update-dialog")).toHaveTextContent(
      "Card Data Update Failed",
    );
    expect(screen.getByTestId("card-data-result-message")).toHaveTextContent(
      "could not be applied",
    );
    // No detail line for non-UPDATED results.
    expect(screen.queryByTestId("card-data-result-detail")).not.toBeInTheDocument();
  });

  it("the result dialog can be closed", () => {
    availableCheck();
    const mutate = vi.fn((_vars: unknown, opts?: { onSettled?: () => void }) => {
      opts?.onSettled?.();
    });
    mockedUpdate.mockReturnValue(
      updateHook({ mutate, isSuccess: true, data: updateResult() }),
    );

    render(<CardDataStatus />);
    fireEvent.click(screen.getByTestId("card-data-update-button"));
    expect(screen.getByTestId("card-data-update-dialog")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("card-data-dialog-close"));
    expect(screen.queryByTestId("card-data-update-dialog")).not.toBeInTheDocument();
  });
});
