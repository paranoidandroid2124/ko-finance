"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { useFilingTrend } from "@/hooks/useFilingTrend";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const weekdayFormatter = new Intl.DateTimeFormat("ko-KR", { weekday: "short" });
const dateFormatter = new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric" });

function formatCategory(dateString: string) {
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) {
    return dateString;
  }
  return `${weekdayFormatter.format(date)} (${dateFormatter.format(date)})`;
}

export function FilingTrendChart() {
  const { data, isLoading, isError } = useFilingTrend();
  const points = useMemo(() => data ?? [], [data]);

  const option = useMemo(() => {
    if (!points.length) {
      return null;
    }

    const categories = points.map((point) => formatCategory(point.date));
    const counts = points.map((point) => point.count);
    const averages = points.map((point) => Number(point.rolling_average.toFixed(2)));

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        formatter: (params: Array<{ seriesName: string; value: number; dataIndex?: number }>) => {
          const index = params?.[0]?.dataIndex ?? 0;
          const rawDate = points[index]?.date;
          const formattedDate = rawDate
            ? new Date(rawDate).toLocaleDateString("ko-KR", {
                year: "numeric",
                month: "long",
                day: "numeric",
                weekday: "long"
              })
            : categories[index] ?? "";

          return [
            `<strong>${formattedDate}</strong>`,
            ...params.map((item) => {
              const formattedValue =
                item.seriesName === "7일 평균" ? item.value.toFixed(2) : Math.round(item.value).toString();
              return `${item.seriesName}: <strong>${formattedValue}건</strong>`;
            })
          ].join("<br/>");
        }
      },
      legend: {
        data: ["처리 건수", "7일 평균"],
        textStyle: { color: "#94a3b8" }
      },
      grid: {
        top: 40,
        left: 20,
        right: 20,
        bottom: 20,
        containLabel: true
      },
      xAxis: {
        type: "category",
        data: categories,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: {
          color: "#94a3b8",
          rotate: 0
        }
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
        axisLabel: { color: "#94a3b8" }
      },
      series: [
        {
          name: "처리 건수",
          type: "line",
          smooth: true,
          data: counts,
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(91, 123, 255, 0.4)" },
                { offset: 1, color: "rgba(91, 123, 255, 0.05)" }
              ]
            }
          },
          lineStyle: { width: 3, color: "#5B7BFF" },
          symbol: "circle",
          symbolSize: 8
        },
        {
          name: "7일 평균",
          type: "line",
          smooth: true,
          data: averages,
          lineStyle: { width: 2, color: "#38BDF8", type: "dashed" },
          symbol: "none"
        }
      ]
    };
  }, [points]);

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">공시 처리 추이</h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 7일간 처리 건수와 7일 이동평균</p>
        </div>
      </div>
      <div className="mt-4 min-h-[260px]">
        {isLoading ? (
          <div className="flex h-[260px] items-center justify-center">
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">데이터를 불러오는 중입니다...</span>
          </div>
        ) : isError ? (
          <div className="flex h-[260px] items-center justify-center">
            <span className="text-xs text-destructive">공시 추세 데이터를 가져오지 못했습니다.</span>
          </div>
        ) : option ? (
          <ReactECharts option={option} style={{ height: 260 }} />
        ) : (
          <div className="flex h-[260px] items-center justify-center">
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">표시할 공시 데이터가 없습니다.</span>
          </div>
        )}
      </div>
    </div>
  );
}
