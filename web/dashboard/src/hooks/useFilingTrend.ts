import { useQuery } from "@tanstack/react-query";

export type FilingTrendPoint = {
  date: string;
  count: number;
  rolling_average: number;
};

type FilingTrendResponse = {
  points: FilingTrendPoint[];
};

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
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
