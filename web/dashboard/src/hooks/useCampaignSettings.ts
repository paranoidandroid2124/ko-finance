"use client";

import { useQuery } from "@tanstack/react-query";

import { loadCampaignSettings, type CampaignSettings } from "@/lib/campaignSettings";

export const useCampaignSettings = () =>
  useQuery<CampaignSettings, Error>({
    queryKey: ["campaignSettings"],
    queryFn: ({ signal }) => loadCampaignSettings(signal),
    staleTime: 1000 * 60 * 10,
  });
