"use client";

import dynamic from "next/dynamic";
import { HelpCircle } from "lucide-react";
import { useMemo } from "react";
import type { SectorSignalPoint } from "@/hooks/useSectorSignals";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

type SectorHotspotScatterProps = {
  points: SectorSignalPoint[];
  isLoading?: boolean;
  onSelect?: (point: SectorSignalPoint) => void;
};

const POSITIVE_COLOR = "#22c55e";
const NEGATIVE_COLOR = "#ef4444";

type ScatterDatum = {
  value: [number, number, number];
  symbolSize: number;
  itemStyle: { color: string };
  point: SectorSignalPoint;
};

type ScatterEventParams = {
  data?: ScatterDatum;
};

export function SectorHotspotScatter({ points, isLoading = false, onSelect }: SectorHotspotScatterProps) {
  const chartData = useMemo<ScatterDatum[]>(() => {
    return points.map((point) => {
      const size = Math.min(26, 12 + Math.abs(point.deltaSentiment7d ?? 0) * 18);
      const sentimentValue = point.sentimentMean ?? 0;
      const volumeValue = point.volumeZ ?? 0;
      return {
        value: [sentimentValue, volumeValue, size],
        symbolSize: size,
        itemStyle: {
          color: sentimentValue >= 0 ? POSITIVE_COLOR : NEGATIVE_COLOR,
        },
        point,
      };
    });
  }, [points]);

  const option = useMemo(() => {
    return {
      backgroundColor: "transparent",
      grid: {
        top: 32,
        right: 24,
        bottom: 48,
        left: 56,
        containLabel: true,
      },
      xAxis: {
        type: "value",
        name: "평균 감성",
        nameLocation: "middle",
        nameGap: 28,
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.5)" } },
        axisLabel: { color: "#cbd5f5" },
        splitLine: {
          show: true,
          lineStyle: { type: "dashed", color: "rgba(148, 163, 184, 0.25)" },
        },
      },
      yAxis: {
        type: "value",
        name: "기사량 Z",
        nameLocation: "middle",
        nameGap: 32,
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.5)" } },
        axisLabel: { color: "#cbd5f5" },
        splitLine: {
          show: true,
          lineStyle: { type: "dashed", color: "rgba(148, 163, 184, 0.25)" },
        },
      },
      tooltip: {
        trigger: "item",
        formatter: (params: ScatterEventParams) => {
          const payload = params?.data?.point;
          if (!payload) return "";
          const top = payload.topArticle;
          const headline = top?.title ? `<br/><span style="color:#94a3b8">Top: ${top.title}</span>` : "";
          const delta =
            payload.deltaSentiment7d != null ? `<br/>Δ감성(7d): ${payload.deltaSentiment7d.toFixed(2)}` : "";
          const meanSentiment = payload.sentimentMean?.toFixed(2) ?? "0.00";
          const sentimentZ = payload.sentimentZ?.toFixed(2) ?? "0.00";
          const volumeZ = payload.volumeZ?.toFixed(2) ?? "0.00";
          return `
            <strong>${payload.sector.name}</strong><br/>
            평균 감성: ${meanSentiment}<br/>
            감성 Z: ${sentimentZ}<br/>
            기사량 Z: ${volumeZ}
            ${delta}
            ${headline}
          `;
        },
      },
      series: [
        {
          type: "scatter",
          data: chartData,
          emphasis: {
            focus: "series",
            scale: true,
            itemStyle: {
              shadowBlur: 10,
              shadowColor: "rgba(148, 163, 184, 0.35)",
            },
          },
          markLine: {
            silent: true,
            lineStyle: {
              color: "rgba(148, 163, 184, 0.35)",
              type: "dashed",
            },
            data: [
              { xAxis: 0 },
              { yAxis: 0 },
            ],
          },
        },
      ],
    };
  }, [chartData]);

  const handleClick = (params: ScatterEventParams) => {
    const payload = params?.data?.point;
    if (payload && onSelect) {
      onSelect(payload);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[360px] w-full items-center justify-center rounded-xl border border-border-light bg-background-cardLight shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <span className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">섹터 신호를 불러오는 중...</span>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">섹터 핫스팟 (평균 감성 × 기사량)</h3>
          <span className="group relative inline-flex items-center text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
            <HelpCircle className="h-3.5 w-3.5" aria-hidden />
            <span className="pointer-events-none absolute left-1/2 top-full z-10 w-max -translate-x-1/2 translate-y-2 rounded-md border border-border-light bg-background-cardLight px-3 py-1 text-[11px] text-text-secondaryLight opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
              감성 Z는 과거 평균 대비 감성이 얼마나 이례적인지를, 기사량 Z는 기사 건수가 얼마나 이례적인지를 보여 줍니다. X축은 평균 감성,
              원 크기는 7일 감성 변화량입니다.
            </span>
          </span>
        </div>
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          사분면을 참고해 지금 주목할 섹터를 빠르게 파악하세요. X축은 평균 감성, 원 크기는 7일 감성 변화량입니다.
        </p>
      </div>
      {!points.length ? (
        <div className="flex h-[320px] items-center justify-center rounded-lg border border-dashed border-border-light text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          표시할 섹터 데이터가 아직 없습니다. 집계가 완료되면 자동으로 나타납니다.
        </div>
      ) : (
        <ReactECharts option={option} style={{ height: 320 }} onEvents={{ click: handleClick }} />
      )}
    </div>
  );
}
