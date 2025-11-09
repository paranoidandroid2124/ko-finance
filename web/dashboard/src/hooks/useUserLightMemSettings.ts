"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchUserLightMemSettings,
  updateUserLightMemSettings,
  type LightMemSettingsPayload,
  type UserLightMemSettingsResponse,
} from "@/lib/userSettingsApi";

export const USER_LIGHTMEM_SETTINGS_KEY = ["user", "settings", "lightmem"] as const;

export const useUserLightMemSettings = () =>
  useQuery<UserLightMemSettingsResponse, Error>({
    queryKey: USER_LIGHTMEM_SETTINGS_KEY,
    queryFn: () => fetchUserLightMemSettings(),
    staleTime: 60_000,
    retry: (failureCount, error) => {
      if (error.message.includes("status 400")) {
        return false;
      }
      return failureCount < 2;
    },
  });

export const useSaveUserLightMemSettings = () => {
  const queryClient = useQueryClient();
  return useMutation<UserLightMemSettingsResponse, Error, LightMemSettingsPayload>({
    mutationFn: (payload) => updateUserLightMemSettings(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(USER_LIGHTMEM_SETTINGS_KEY, data);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: USER_LIGHTMEM_SETTINGS_KEY });
    },
  });
};
