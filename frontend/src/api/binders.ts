import { apiClient } from "./client";
import type {
  AnyBinderPage,
  Binder,
  BinderCreate,
  BinderUpdate,
} from "../types";

// ---------------------------------------------------------------------------
// Binder CRUD
// ---------------------------------------------------------------------------

export async function listBinders(): Promise<Binder[]> {
  return apiClient.get<Binder[]>("/binders");
}

export async function getDefaultBinder(): Promise<Binder> {
  return apiClient.get<Binder>("/binders/default");
}

export async function createBinder(data: BinderCreate): Promise<Binder> {
  return apiClient.post<Binder>("/binders", data);
}

export async function updateBinder(binderId: number, data: BinderUpdate): Promise<Binder> {
  return apiClient.patch<Binder>(`/binders/${binderId}`, data);
}

export async function setDefaultBinder(binderId: number): Promise<Binder> {
  return apiClient.post<Binder>(`/binders/${binderId}/default`, {});
}

export async function deleteBinder(binderId: number): Promise<void> {
  return apiClient.delete(`/binders/${binderId}`);
}

// ---------------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------------

export async function getBinderPage(binderId: number, page: number): Promise<AnyBinderPage> {
  return apiClient.get<AnyBinderPage>(`/binders/${binderId}/page`, { page });
}

// ---------------------------------------------------------------------------
// Placements (FREE_PLACEMENT only)
// ---------------------------------------------------------------------------

export interface PlacementBody {
  card_id: number;
  page: number;
  slot: number;
}

export async function addPlacement(binderId: number, body: PlacementBody) {
  return apiClient.post(`/binders/${binderId}/placements`, body);
}

export async function movePlacement(
  binderId: number,
  placementId: number,
  body: { page: number; slot: number },
) {
  return apiClient.patch(`/binders/${binderId}/placements/${placementId}`, body);
}

export async function removePlacement(binderId: number, placementId: number): Promise<void> {
  return apiClient.delete(`/binders/${binderId}/placements/${placementId}`);
}
