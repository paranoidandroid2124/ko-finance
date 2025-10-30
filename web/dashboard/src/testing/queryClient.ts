import { QueryClient } from "@tanstack/react-query";

/**
 * Creates an in-memory QueryClient configured for deterministic
 * storybook renders and unit tests (no retries, no stale timers).
 */
export const createMockQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

