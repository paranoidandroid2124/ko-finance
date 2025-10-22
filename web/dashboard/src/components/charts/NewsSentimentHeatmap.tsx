"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { useNewsHeatmap } from "@/hooks/useNewsHeatmap";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

export function NewsSentimentHeatmap() {
  const { data, isLoading, isError } = useNewsHeatmap();

  const sectors = useMemo(() => data?.sectors ?? [], [data]);
  const buckets = useMemo(() => data?.buckets ?? [], [data]);
  const points = useMemo(() => data?.points ?? [], [data]);

  const heatmapData = useMemo(() => {
    if (!points.length) {
      return [];
    }
    return points.map((point) => [
      point.bucket_index,
      point.sector_index,
      point.sentiment ?? 0,
      point.article_count ?? 0
    ]);
  }, [points]);

  const option = useMemo(() => {
    if (!sectors.length || !buckets.length) {
      return null;
    }

    return {
      backgroundColor: "transparent",
      tooltip: {
        position: "top",
        formatter: (params: { value: [number, number, number, number] }) => {
          const timeIndex = params.value[0];
          const sectorIndex = params.value[1];
          const sentiment = params.value[2];
          const articleCount = params.value[3];
          const bucket = buckets[timeIndex];
          const label = bucket?.label ?? "";
          const hasData = articleCount > 0;
          const sectorLabel = sectors[sectorIndex] ?? "";
          return [
            `<strong>${sectorLabel}</strong>`,
            `${label} (기사 ${articleCount}건)`,
            hasData ? `평균 감성: <strong>${sentiment.toFixed(2)}</strong>` : "데이터 없음"
          ].join("<br/>");
        }
      },
      grid: {
        top: 40,
        left: 80,
        right: 80,
        bottom: 40
      },
      xAxis: {
        type: "category",
        data: buckets.map((bucket) => bucket.label),
        splitArea: { show: false },
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#94a3b8" }
      },
      yAxis: {
        type: "category",
        data: sectors,
        splitArea: { show: false },
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#94a3b8" }
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: false,
        orient: "vertical",
        right: 10,
        top: "center",
        inRange: {
          color: ["#F45B69", "#F2B636", "#2AC5A8"]
        }
      },
      series: [
        {
          name: "감성",
          type: "heatmap",
          data: heatmapData,
          label: {
            show: true,
            color: "#0f172a",
            formatter: (params: { value: [number, number, number, number] }) => {
              const articleCount = params.value[3];
              if (!articleCount) {
                return "-";
              }
              return params.value[2].toFixed(2);
            }
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: "rgba(0, 0, 0, 0.4)"
            }
          }
        }
      ]
    };
  }, [buckets, sectors, heatmapData]);

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">섹터별 뉴스 감성 Heatmap</h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 감성 흐름을 시간대별로 파악하세요.</p>
        </div>
      </div>
      <div className="mt-4 overflow-hidden rounded-lg">
        {isLoading ? (
          <div className="flex h-[260px] items-center justify-center">
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">데이터를 불러오는 중입니다...</span>
          </div>
        ) : isError ? (
          <div className="flex h-[260px] items-center justify-center">
            <span className="text-xs text-destructive">뉴스 감성 데이터를 가져오지 못했습니다.</span>
          </div>
        ) : option ? (
          <ReactECharts option={option} style={{ height: 260 }} />
        ) : (
          <div className="flex h-[260px] items-center justify-center">
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">표시할 뉴스 감성 데이터가 없습니다.</span>
          </div>
        )}
      </div>
    </div>
  );
}
