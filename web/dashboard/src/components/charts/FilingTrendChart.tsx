import dynamic from "next/dynamic";
import { useMemo } from "react";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const MOCK_DATA = {
  dates: ["월", "화", "수", "목", "금", "토", "일"],
  filings: [12, 18, 15, 22, 19, 9, 13],
  avg: [14, 16, 14, 17, 16, 12, 14]
};

export function FilingTrendChart() {
  const option = useMemo(
    () => ({
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis"
      },
      legend: {
        data: ["처리", "7일 평균"],
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
        data: MOCK_DATA.dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#94a3b8" }
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
        axisLabel: { color: "#94a3b8" }
      },
      series: [
        {
          name: "처리",
          type: "line",
          smooth: true,
          data: MOCK_DATA.filings,
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
          data: MOCK_DATA.avg,
          lineStyle: { width: 2, color: "#38BDF8", type: "dashed" },
          symbol: "none"
        }
      ]
    }),
    []
  );

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">공시 처리 추이</h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 7일간 DART Watcher+ 처리량</p>
        </div>
      </div>
      <div className="mt-4">
        <ReactECharts option={option} style={{ height: 260 }} />
      </div>
    </div>
  );
}

