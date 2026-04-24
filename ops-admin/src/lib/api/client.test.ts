import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiError } from "./client";

const originalFetch = globalThis.fetch;

interface MockResponseInit {
  ok: boolean;
  status: number;
  body: unknown;
  contentType?: string;
}

function mockFetch(init: MockResponseInit) {
  return vi.fn(async () =>
    ({
      ok: init.ok,
      status: init.status,
      headers: new Headers({
        "content-type": init.contentType ?? "application/json",
      }),
      json: async () => init.body,
      text: async () => String(init.body),
    }) as unknown as Response,
  ) as unknown as typeof fetch;
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_BACKEND_URL", "http://backend.test");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("resolves JSON body on success and passes bearer token", async () => {
    globalThis.fetch = mockFetch({ ok: true, status: 200, body: { foo: "bar" } });

    const result = await apiFetch<{ foo: string }>(
      "/api/v1/sample",
      {},
      { accessToken: "token-123" },
    );

    expect(result).toEqual({ foo: "bar" });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/v1/sample",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer token-123" }),
      }),
    );
  });

  it("throws ApiError with detail message for 4xx", async () => {
    globalThis.fetch = mockFetch({
      ok: false,
      status: 401,
      body: { detail: "Token expired", code: "E_AUTH" },
    });

    await expect(apiFetch("/api/v1/secret", {}, {})).rejects.toSatisfy((error) => {
      return (
        error instanceof ApiError &&
        error.status === 401 &&
        error.message === "Token expired" &&
        error.code === "E_AUTH"
      );
    });
  });

  it("strips trailing slash from baseUrl", async () => {
    globalThis.fetch = mockFetch({ ok: true, status: 200, body: { ok: true } });

    await apiFetch("/api/v1/ping", {}, { baseUrl: "http://custom.test/" });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://custom.test/api/v1/ping",
      expect.any(Object),
    );
  });
});
