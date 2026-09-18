"use client";

// Loading the published JSON in the browser. The base URL is configurable so the same build works
// against the local dev copy, a test fixture, or the CloudFront address in production.
import { useEffect, useState } from "react";
import { SCHEMA_VERSION } from "./types";

export const DATA_BASE = (process.env.NEXT_PUBLIC_DATA_BASE ?? "/data/v1").replace(/\/$/, "");

export class DataError extends Error {
  constructor(
    message: string,
    readonly kind: "not-found" | "network" | "schema" | "invalid",
  ) {
    super(message);
  }
}

// Responses are cached for the life of the page so switching tabs does not refetch. The cached
// request is shared between components, so it is never aborted when one of them goes away.
const cache = new Map<string, Promise<unknown>>();

export function fetchJson<T>(path: string): Promise<T> {
  const url = `${DATA_BASE}/${path}`;
  const cached = cache.get(url);
  if (cached) return cached as Promise<T>;

  const request = (async () => {
    let response: Response;
    try {
      response = await fetch(url);
    } catch {
      throw new DataError("Could not reach the data. Check your connection.", "network");
    }
    if (response.status === 404) throw new DataError("That data isn't available.", "not-found");
    if (!response.ok) throw new DataError(`The data failed to load (${response.status}).`, "network");
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new DataError("The data was not readable.", "invalid");
    }
    const version = (body as { schema_version?: number }).schema_version;
    if (version !== undefined && version !== SCHEMA_VERSION) {
      throw new DataError("The data has changed format. Please refresh the page.", "schema");
    }
    return body as T;
  })();

  // Do not keep failures: the next attempt should try again.
  request.catch(() => cache.delete(url));
  cache.set(url, request);
  return request;
}

export interface Loaded<T> {
  data: T | null;
  error: DataError | null;
  loading: boolean;
}

/** Load a published JSON file. Pass null to skip (for example while waiting on another file). */
export function useJson<T>(path: string | null): Loaded<T> {
  const [state, setState] = useState<{ path: string | null; data: T | null; error: DataError | null }>(
    { path: null, data: null, error: null },
  );

  useEffect(() => {
    if (path === null) return;
    let cancelled = false; // ignore the result if the component moved on before it arrived
    fetchJson<T>(path)
      .then((data) => !cancelled && setState({ path, data, error: null }))
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          path,
          data: null,
          error:
            error instanceof DataError ? error : new DataError("Something went wrong.", "network"),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  // While a new path loads, do not show the previous path's data as if it were current.
  const current = state.path === path;
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: path !== null && !(current && (state.data !== null || state.error !== null)),
  };
}
