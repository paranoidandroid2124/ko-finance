"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchDigestPreview, type DigestPreviewParams, type DigestPreviewResponse } from "@/lib/digestApi";

export const DIGEST_PREVIEW_QUERY_KEY = ["digest", "preview"] as const;

export const useDigestPreview = (params?: DigestPreviewParams) =>
  useQuery<DigestPreviewResponse, Error>({
    queryKey: [...DIGEST_PREVIEW_QUERY_KEY, params?.timeframe ?? "daily", params?.referenceDate ?? "today"],
    queryFn: () => fetchDigestPreview(params),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
