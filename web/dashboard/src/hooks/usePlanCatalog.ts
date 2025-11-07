"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchPlanCatalog, type PlanCatalogResponse } from "@/lib/planCatalogApi";

export const PLAN_CATALOG_QUERY_KEY = ["planCatalog"];

export const usePlanCatalog = () =>
  useQuery<PlanCatalogResponse, Error>({
    queryKey: PLAN_CATALOG_QUERY_KEY,
    queryFn: ({ signal }) => fetchPlanCatalog(signal),
    staleTime: 1000 * 60 * 30,
  });
