"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchDsarRequests,
  createDsarRequest,
  type DsarRequest,
  type DsarRequestListResponse,
  type DsarRequestType,
} from "@/lib/accountApi";

export const DSAR_REQUESTS_KEY = ["account", "dsar", "requests"] as const;

export const useDsarRequests = () =>
  useQuery<DsarRequestListResponse, Error>({
    queryKey: DSAR_REQUESTS_KEY,
    queryFn: () => fetchDsarRequests(),
    staleTime: 30_000,
  });

export const useCreateDsarRequest = () => {
  const queryClient = useQueryClient();
  return useMutation<DsarRequest, Error, { requestType: DsarRequestType; note?: string }>({
    mutationFn: (payload) => createDsarRequest(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: DSAR_REQUESTS_KEY });
    },
  });
};
