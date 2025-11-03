import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";

export type FilingTrendPoint = {
  date: string;
  count: number;
  rolling_average: number;
};

type FilingTrendResponse = {
  points: FilingTrendPoint[];
};

const fetchFilingTrend = async (): Promise<FilingTrendPoint[]> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/dashboard/filing-trend`);
  if (!response.ok) {
    throw new Error("공시 처리 추세 데이터를 불러오지 못했습니다.");
  }
  const payload: FilingTrendResponse = await response.json();
  return payload?.points ?? [];
};

export function useFilingTrend() {
  return useQuery({
    queryKey: ["dashboard", "filing-trend"],
    queryFn: fetchFilingTrend,
  });
}
