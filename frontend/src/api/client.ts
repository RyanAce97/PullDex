/**
 * Base API client for PullDex.
 *
 * All endpoint modules import `apiClient` and call its methods.
 * Centralises baseURL, headers, and error handling in one place.
 *
 * The backend URL is read from the VITE_API_URL environment variable.
 * - In development: set to http://localhost:8000
 * - In production/desktop: empty string (same-origin requests)
 */

const BASE_URL = import.meta.env.VITE_API_URL || "";

/**
 * Build a full URL string from a path and optional query params.
 * When BASE_URL is empty, uses the current page origin (same-origin).
 */
function buildUrl(path: string, params?: Record<string, string | number>): string {
  const base = BASE_URL || window.location.origin;
  const url = new URL(path, base);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.set(key, String(value));
    });
  }
  return url.toString();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown,
  ) {
    super(`API error ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, response.statusText, body);
  }
  return response.json() as Promise<T>;
}

export const apiClient = {
  async get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
    const response = await fetch(buildUrl(path, params), {
      headers: { Accept: "application/json" },
    });
    return handleResponse<T>(response);
  },

  async post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(buildUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });
    return handleResponse<T>(response);
  },

  async delete(path: string): Promise<void> {
    const response = await fetch(buildUrl(path), {
      method: "DELETE",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(response.status, response.statusText, body);
    }
  },

  async patch<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(buildUrl(path), {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });
    return handleResponse<T>(response);
  },
};
