export interface ApiClientOptions {
  baseUrl?: string;
  accessToken?: string | null;
  signal?: AbortSignal;
}

export interface ApiErrorBody {
  detail?: string;
  code?: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  readonly code?: string;

  constructor(status: number, body: unknown) {
    super(
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as ApiErrorBody).detail)
        : `API request failed with status ${status}`,
    );
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    if (typeof body === "object" && body !== null && "code" in body) {
      this.code = String((body as ApiErrorBody).code);
    }
  }
}

function resolveBaseUrl(options: ApiClientOptions): string {
  const candidate = options.baseUrl ?? process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  return candidate.replace(/\/$/, "");
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  options: ApiClientOptions = {},
): Promise<T> {
  const baseUrl = resolveBaseUrl(options);
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    signal: options.signal ?? init.signal ?? null,
    headers: {
      "Content-Type": "application/json",
      ...(options.accessToken ? { Authorization: `Bearer ${options.accessToken}` } : {}),
      ...init.headers,
    },
  });

  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    throw new ApiError(response.status, body);
  }

  return body as T;
}
