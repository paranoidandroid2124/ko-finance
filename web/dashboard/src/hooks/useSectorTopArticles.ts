import { useQuery } from "@tanstack/react-query";
import type { SectorRef, SectorTopArticle } from "./useSectorSignals";

export type SectorTopArticlesResponse = {
  sector: SectorRef;
  items: SectorTopArticle[];
};

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
};

async function fetchSectorTopArticles(sectorId: number, hours: number, limit: number): Promise<SectorTopArticlesResponse> {
  const baseUrl = resolveApiBase();
  const response = await fetch(
    `${baseUrl}/api/v1/sectors/${sectorId}/top-articles?hours=${hours}&limit=${limit}`
  );
  if (!response.ok) {
    throw new Error("섹터 주요 기사를 불러오지 못했습니다.");
  }
  const payload = (await response.json()) as SectorTopArticlesResponse;
  payload.items = payload.items ?? [];
  return payload;
}

export function useSectorTopArticles(sectorId: number | null, hours = 72, limit = 3) {
  return useQuery({
    queryKey: ["sectors", "top-articles", sectorId, hours, limit],
    queryFn: () => fetchSectorTopArticles(sectorId as number, hours, limit),
    enabled: Boolean(sectorId),
    staleTime: 10 * 60 * 1000,
  });
}
