import type { ApiErrorPayload } from "./contracts";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "studypilot_access_token";

let unauthorizedHandler: (() => void) | undefined;

function handleUnauthorized(): void {
  clearAccessToken();
  unauthorizedHandler?.();
}

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
        handleUnauthorized();
      }
      throw error;
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  },
};

export function uploadFile<T>(
  path: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}${path}`);
    request.setRequestHeader("Accept", "application/json");
    const token = getAccessToken();
    if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });
    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) {
        try {
          const data = JSON.parse(request.responseText) as T;
          onProgress(100);
          resolve(data);
        } catch {
          reject(
            new ApiError(
              request.status,
              "invalid_response",
              "服务器返回了无法识别的数据。",
              request.getResponseHeader("X-Request-ID") ?? "unknown",
            ),
          );
        }
        return;
      }
      let payload: Partial<ApiErrorPayload> = {};
      try {
        payload = JSON.parse(request.responseText) as Partial<ApiErrorPayload>;
      } catch {
        // Use the stable fallback below for non-JSON proxy or network responses.
      }
      if (request.status === 401) handleUnauthorized();
      reject(
        new ApiError(
          request.status,
          payload.code ?? "upload_failed",
          payload.message ?? "上传失败，请稍后重试。",
          payload.request_id ?? request.getResponseHeader("X-Request-ID") ?? "unknown",
        ),
      );
    });
    request.addEventListener("error", () => {
      reject(new ApiError(0, "network_error", "网络连接失败，请重试。", "unknown"));
    });
    request.addEventListener("abort", () => {
      reject(new ApiError(0, "upload_cancelled", "上传已取消。", "unknown"));
    });
    const formData = new FormData();
    formData.append("file", file);
    request.send(formData);
  });
}
