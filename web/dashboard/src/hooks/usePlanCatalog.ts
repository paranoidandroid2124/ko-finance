"use client";

import { useCallback, useEffect, useState } from "react";

import { resolveApiBase } from "@/lib/apiBase";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
import type { PlanCatalogPayload } from "@/store/planStore/types";

type UsePlanCatalogResult = {
  catalog: PlanCatalogPayload | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
};

let catalogCache: PlanCatalogPayload | null = null;
let catalogFetchPromise: Promise<PlanCatalogPayload | null> | null = null;

async function requestCatalog(signal?: AbortSignal): Promise<PlanCatalogPayload> {
  const baseUrl = resolveApiBase();
  const response = await fetchWithAuth(`${baseUrl}/api/v1/plan/catalog`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => undefined);
    const message =
      typeof detail?.detail?.message === "string"
        ? detail.detail.message
        : `failed to load plan catalog (${response.status})`;
    throw new Error(message);
  }
  const payload = (await response.json()) as PlanCatalogPayload;
  return payload;
}

async function getCatalog(signal?: AbortSignal): Promise<PlanCatalogPayload | null> {
  if (catalogCache) {
    return catalogCache;
  }
  if (catalogFetchPromise) {
    return catalogFetchPromise;
  }
  const fetchPromise = requestCatalog(signal)
    .then((payload) => {
      catalogCache = payload;
      return payload;
    })
    .finally(() => {
      catalogFetchPromise = null;
    });
  catalogFetchPromise = fetchPromise;
  return fetchPromise;
}

export function usePlanCatalog(): UsePlanCatalogResult {
  const [catalog, setCatalog] = useState<PlanCatalogPayload | null>(catalogCache);
  const [loading, setLoading] = useState<boolean>(!catalogCache);
  const [error, setError] = useState<string | null>(null);

  const fetchCatalog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await getCatalog();
      setCatalog(payload);
    } catch (err) {
      const message = err instanceof Error ? err.message : "plan catalog fetch failed";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (catalog || loading) {
      return;
    }
    const controller = new AbortController();
    getCatalog(controller.signal)
      .then((payload) => {
        setCatalog(payload);
        setError(null);
      })
      .catch((err) => {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        setError(err instanceof Error ? err.message : "plan catalog fetch failed");
      })
      .finally(() => {
        setLoading(false);
      });
    return () => controller.abort();
  }, [catalog, loading]);

  return {
    catalog,
    loading,
    error,
    refetch: fetchCatalog,
  };
}
