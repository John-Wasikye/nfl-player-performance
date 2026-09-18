import { renderHook, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

// The loader keeps a module-level cache, so each test gets a fresh copy of the module.
async function freshApi() {
  vi.resetModules();
  return import("@/lib/api");
}

describe("loading published data", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("fetches from the data base URL", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ schema_version: 1, season: 2026 }));
    const { fetchJson } = await freshApi();

    await expect(fetchJson("meta.json")).resolves.toMatchObject({ season: 2026 });
    expect(fetchMock).toHaveBeenCalledWith("/data/v1/meta.json");
  });

  it("caches a response so the same file is fetched once", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ schema_version: 1 }));
    const { fetchJson } = await freshApi();

    await Promise.all([fetchJson("meta.json"), fetchJson("meta.json")]);
    await fetchJson("meta.json");

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reports a missing file as not-found", async () => {
    fetchMock.mockResolvedValue(new Response("", { status: 404 }));
    const { fetchJson } = await freshApi();

    await expect(fetchJson("players/nobody.json")).rejects.toMatchObject({ kind: "not-found" });
  });

  it("reports a server error as a network problem", async () => {
    fetchMock.mockResolvedValue(new Response("", { status: 500 }));
    const { fetchJson } = await freshApi();

    await expect(fetchJson("meta.json")).rejects.toMatchObject({ kind: "network" });
  });

  it("reports an unreachable server as a network problem", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const { fetchJson } = await freshApi();

    await expect(fetchJson("meta.json")).rejects.toMatchObject({ kind: "network" });
  });

  it("refuses data in a format the site does not understand", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ schema_version: 2 }));
    const { fetchJson } = await freshApi();

    await expect(fetchJson("meta.json")).rejects.toMatchObject({ kind: "schema" });
  });

  it("reports data that is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>oops</html>", { status: 200 }));
    const { fetchJson } = await freshApi();

    await expect(fetchJson("meta.json")).rejects.toMatchObject({ kind: "invalid" });
  });

  it("does not cache a failure, so the next attempt retries", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(jsonResponse({ schema_version: 1, ok: true }));
    const { fetchJson } = await freshApi();

    await expect(fetchJson("meta.json")).rejects.toBeDefined();
    await expect(fetchJson("meta.json")).resolves.toMatchObject({ ok: true });
  });
});

describe("the useJson hook", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("goes from loading to loaded", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ schema_version: 1, week: 2 }));
    const { useJson } = await freshApi();

    const { result } = renderHook(() => useJson<{ week: number }>("meta.json"));
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.data).toMatchObject({ week: 2 }));
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  // Regression: React runs effects twice in development. The first run's cleanup used to abort the
  // shared cached request, so the second run waited on a request that could never finish.
  it("still loads when React mounts, unmounts, and remounts it (development behavior)", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ schema_version: 1, week: 2 }));
    const { useJson } = await freshApi();

    const { result } = renderHook(() => useJson<{ week: number }>("meta.json"), { wrapper: StrictMode });

    await waitFor(() => expect(result.current.data).toMatchObject({ week: 2 }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("surfaces an error", async () => {
    fetchMock.mockResolvedValue(new Response("", { status: 404 }));
    const { useJson } = await freshApi();

    const { result } = renderHook(() => useJson("players/x.json"));

    await waitFor(() => expect(result.current.error).toMatchObject({ kind: "not-found" }));
    expect(result.current.loading).toBe(false);
  });

  it("does nothing while the path is null", async () => {
    const { useJson } = await freshApi();

    const { result } = renderHook(() => useJson(null));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current).toEqual({ data: null, error: null, loading: false });
  });

  it("does not show the previous file's data while a new one loads", async () => {
    let release: (r: Response) => void = () => {};
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ schema_version: 1, name: "first" }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => (release = resolve)));
    const { useJson } = await freshApi();

    const { result, rerender } = renderHook(({ path }) => useJson<{ name: string }>(path), {
      initialProps: { path: "a.json" },
    });
    await waitFor(() => expect(result.current.data?.name).toBe("first"));

    rerender({ path: "b.json" });
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(true);

    release(jsonResponse({ schema_version: 1, name: "second" }));
    await waitFor(() => expect(result.current.data?.name).toBe("second"));
  });
});
