import dynamic from "next/dynamic";
import { useMemo } from "react";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const SECTORS = ["반도체", "에너지", "금융", "바이오", "소비재", "모빌리티"];
const TIMES = ["-60분", "-45분", "-30분", "-15분", "현재"];

const MOCK_MATRIX = [
  [0, 0, -0.3],
  [0, 1, -0.1],
  [0, 2, 0.05],
  [0, 3, 0.2],
  [0, 4, 0.35],
  [1, 0, -0.6],
  [1, 1, -0.2],
  [1, 2, 0.1],
  [1, 3, 0.18],
  [1, 4, 0.25],
  [2, 0, -0.2],
  [2, 1, -0.05],
  [2, 2, 0.15],
  [2, 3, 0.25],
  [2, 4, 0.4],
  [3, 0, -0.15],
  [3, 1, -0.05],
  [3, 2, 0.08],
  [3, 3, 0.12],
  [3, 4, 0.2],
  [4, 0, -0.4],
  [4, 1, -0.3],
  [4, 2, -0.15],
  [4, 3, 0.05],
  [4, 4, 0.12],
  [5, 0, -0.1],
  [5, 1, -0.02],
  [5, 2, 0.16],
  [5, 3, 0.28],
  [5, 4, 0.32]
];

export function NewsSentimentHeatmap() {
  const option = useMemo(
    () => ({
      backgroundColor: "transparent",
      tooltip: {
        position: "top",
        formatter: (params: { value: [number, number, number] }) => {
          const value = params.value[2];
          return `${SECTORS[params.value[1]]}<br/>${TIMES[params.value[0]]}: <strong>${value.toFixed(
            2
          )}</strong>`;
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
        data: TIMES,
        splitArea: { show: false },
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#94a3b8" }
      },
      yAxis: {
        type: "category",
        data: SECTORS,
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
          data: MOCK_MATRIX,
          label: {
            show: true,
            color: "#0f172a",
            formatter: (params: { value: [number, number, number] }) => params.value[2].toFixed(2)
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: "rgba(0, 0, 0, 0.4)"
            }
          }
        }
      ]
    }),
    []
  );

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">섹터별 뉴스 감성 Heatmap</h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 1시간 흐름</p>
        </div>
      </div>
      <div className="mt-4 overflow-hidden rounded-lg">
        <ReactECharts option={option} style={{ height: 260 }} />
      </div>
    </div>
  );
}
