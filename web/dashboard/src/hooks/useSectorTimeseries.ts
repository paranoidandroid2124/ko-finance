import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";
import type { SectorRef } from "./useSectorSignals";

export type SectorTimeseriesPoint = {
  date: string;
  sentMean: number | null;
  volume: number;
};

export type SectorCurrentSnapshot = {
  sentZ7d: number | null;
  delta7d: number | null;
};

export type SectorTimeseriesResponse = {
  sector: SectorRef;
  series: SectorTimeseriesPoint[];
  current: SectorCurrentSnapshot;
};

async function fetchSectorTimeseries(sectorId: number, days: number): Promise<SectorTimeseriesResponse> {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/sectors/${sectorId}/timeseries?days=${days}`);
  if (!response.ok) {
    throw new Error("섹터 시계열 데이터를 불러오지 못했습니다.");
  }
  const payload = (await response.json()) as SectorTimeseriesResponse;
  payload.series = payload.series ?? [];
  return payload;
}

export function useSectorTimeseries(sectorId: number | null, days = 30) {
  return useQuery({
    queryKey: ["sectors", "timeseries", sectorId, days],
    queryFn: () => fetchSectorTimeseries(sectorId as number, days),
    enabled: Boolean(sectorId),
    staleTime: 5 * 60 * 1000,
  });
}
