import type { ApiErrorPayload } from "./contracts";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "studypilot_access_token";

let unauthorizedHandler: (() => void) | undefined;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getAccessToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function setUnauthorizedHandler(handler: (() => void) | undefined): void {
  unauthorizedHandler = handler;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: Partial<ApiErrorPayload> = {};
  try {
    payload = (await response.json()) as Partial<ApiErrorPayload>;
  } catch {
    // The stable fallback intentionally contains no response body or credentials.
  }
  return new ApiError(
    response.status,
    payload.code ?? "request_failed",
    payload.message ?? "请求失败，请稍后重试。",
    payload.request_id ?? response.headers.get("X-Request-ID") ?? "unknown",
  );
}

export const api = {
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const token = getAccessToken();
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    if (!response.ok) {
      const error = await parseError(response);
      if (response.status === 401) {
        clearAccessToken();
        unauthorizedHandler?.();
      }
      throw error;
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  },
};
