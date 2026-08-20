import { apiClient } from "./client";
import type { BinderPageResponse } from "../types";

export interface BinderParams {
  page?: number;
  page_size?: number;
}

export async function getBinderPage(params: BinderParams): Promise<BinderPageResponse> {
  const queryParams: Record<string, string | number> = {};
  if (params.page) queryParams.page = params.page;
  if (params.page_size) queryParams.page_size = params.page_size;

  return apiClient.get<BinderPageResponse>("/binder/page", queryParams);
}

export async function setBinderCard(entryId: number): Promise<void> {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL || window.location.origin}/binder/card/${entryId}`,
    { method: "PUT", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new Error("Failed to set binder card");
}

export async function unsetBinderCard(entryId: number): Promise<void> {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL || window.location.origin}/binder/card/${entryId}`,
    { method: "DELETE", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new Error("Failed to unset binder card");
}
