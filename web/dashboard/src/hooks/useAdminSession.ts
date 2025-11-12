"use client";

import { useQuery } from "@tanstack/react-query";

import {
  AdminUnauthorizedError,
  fetchAdminSession,
  type AdminSessionInfo,
} from "@/lib/adminApi";

export const ADMIN_SESSION_QUERY_KEY = ["admin", "session"];

type UseAdminSessionResult = ReturnType<typeof useQuery<AdminSessionInfo, Error>>;

export const useAdminSession = (): UseAdminSessionResult & { isUnauthorized: boolean } => {
  const query = useQuery<AdminSessionInfo, Error>({
    queryKey: ADMIN_SESSION_QUERY_KEY,
    queryFn: fetchAdminSession,
    staleTime: 2 * 60_000,
    retry: (failureCount, error) => {
      if (error instanceof AdminUnauthorizedError) {
        return false;
      }
      return failureCount < 2;
    },
  });

  const isUnauthorized =
    query.error instanceof AdminUnauthorizedError || (!query.isLoading && !query.data);

  return {
    ...query,
    isUnauthorized,
  };
};
