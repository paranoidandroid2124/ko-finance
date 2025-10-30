"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef } from "react";
import type { EChartsType } from "echarts";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { PlanLock } from "@/components/ui/PlanLock";
import type { PlanTier } from "@/store/planStore";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

export type TimelineSparklinePoint = {
  date: string;
  sentimentZ?: number | null;
  priceClose?: number | null;
  volume?: number | null;
  eventType?: string | null;
  evidenceUrnIds?: string[];
};

export type TimelineSparklineProps = {
  points: TimelineSparklinePoint[];
  planTier: PlanTier;
  locked?: boolean;
  height?: number;
  highlightDate?: string;
  showVolume?: boolean;
  onHoverPoint?: (point: TimelineSparklinePoint | null) => void;
  onSelectPoint?: (point: TimelineSparklinePoint) => void;
  onRequestUpgrade?: (tier: PlanTier) => void;
};

const PLAN_DESCRIPTION: Record<PlanTier, string> = {
  free: "핵심 감성 흐름을 먼저 함께 나눠드려요. 더 살펴보고 싶을 땐 언제든 말씀 주세요.",
  pro: "감성과 가격을 나란히 살피며 오늘의 변화를 차분히 안내해 드릴게요.",
  enterprise: "감성·가격·거래량까지 한눈에 담아 조직의 걸음을 함께 챙겨드리고 있습니다.",
};

function formatDateLabel(isoDate: string) {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) {
    return isoDate;
  }
  return date.toLocaleDateString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
  });
}

export function TimelineSparkline({
  points,
  planTier,
  locked,
  height = 260,
  highlightDate,
  showVolume = planTier !== "free",
  onHoverPoint,
  onSelectPoint,
  onRequestUpgrade,
}: TimelineSparklineProps) {
  const hasData = points.length > 0;
  const prefersReducedMotion = usePrefersReducedMotion();
  const chartInstanceRef = useRef<EChartsType | null>(null);
  const highlightIndex = useMemo(() => {
    if (!highlightDate) {
      return -1;
    }
    return points.findIndex((point) => point.date === highlightDate);
  }, [points, highlightDate]);

  useEffect(() => {
    const chartInstance = chartInstanceRef.current;
    if (!chartInstance || !hasData || locked) {
      return;
    }

    const lineSeriesIndexes = [0, 1];

    if (highlightIndex >= 0) {
      lineSeriesIndexes.forEach((seriesIndex) => {
        chartInstance.dispatchAction({
          type: "highlight",
          seriesIndex,
          dataIndex: highlightIndex,
        });
      });
      chartInstance.dispatchAction({
        type: "showTip",
        seriesIndex: 0,
        dataIndex: highlightIndex,
      });
    } else {
      chartInstance.dispatchAction({ type: "hideTip" });
      lineSeriesIndexes.forEach((seriesIndex) => {
        chartInstance.dispatchAction({
          type: "downplay",
          seriesIndex,
        });
      });
    }
  }, [highlightIndex, hasData, locked]);

  const handleChartReady = useCallback((instance: EChartsType) => {
    chartInstanceRef.current = instance;
  }, []);

  const option = useMemo(() => {
    if (!hasData || locked) {
      return null;
    }

    const categories = points.map((point) => formatDateLabel(point.date));
    const sentiment = points.map((point) =>
      typeof point.sentimentZ === "number" ? Number(point.sentimentZ.toFixed(2)) : null,
    );
    const prices = points.map((point) =>
      typeof point.priceClose === "number" ? Number(point.priceClose.toFixed(2)) : null,
    );
    const volumes = points.map((point) => (typeof point.volume === "number" ? Math.round(point.volume) : null));
    const highlightCategory = highlightIndex >= 0 ? categories[highlightIndex] : undefined;
    const lineHighlight =
      highlightCategory !== undefined
        ? {
            symbol: "none" as const,
            lineStyle: { color: "rgba(56, 189, 248, 0.7)", width: 1.5, type: "dashed" as const },
            data: [{ xAxis: highlightCategory }],
            silent: true,
          }
        : undefined;

    return {
      backgroundColor: "transparent",
      animation: !prefersReducedMotion,
      animationDuration: prefersReducedMotion ? 0 : 200,
      animationDurationUpdate: prefersReducedMotion ? 0 : 320,
      animationEasing: "cubicOut",
      animationEasingUpdate: "cubicOut",
      grid: {
        top: 32,
        left: 16,
        right: planTier === "free" ? 16 : 40,
        bottom: showVolume ? 40 : 20,
        containLabel: true,
      },
      legend: {
        data: ["감성 온도", "가격", ...(showVolume ? ["거래량"] : [])],
        textStyle: { color: "#94a3b8", fontSize: 11 },
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        borderWidth: 0,
        textStyle: { color: "#e2e8f0", fontSize: 11 },
        formatter: (params: Array<{ seriesName: string; value: number | null; dataIndex: number }>) => {
          const index = params?.[0]?.dataIndex ?? 0;
          const source = points[index];
          const dateLabel = source
            ? new Date(source.date).toLocaleDateString("ko-KR", {
                year: "numeric",
                month: "long",
                day: "numeric",
                weekday: "short",
              })
            : categories[index] ?? "";

          const rows = params.map((item) => {
            if (item.value === null || item.value === undefined) {
              return `${item.seriesName}: 데이터 준비 중`;
            }
            const formatted =
              item.seriesName === "감성 온도"
                ? item.value.toFixed(2)
                : item.seriesName === "거래량"
                ? item.value.toLocaleString()
                : item.value.toLocaleString(undefined, { maximumFractionDigits: 2 });
            return `${item.seriesName}: <strong>${formatted}</strong>`;
          });

          if (source?.eventType) {
            rows.push(`기록된 소식: ${source.eventType}`);
          }
          if (source?.evidenceUrnIds && source.evidenceUrnIds.length) {
            rows.push(`함께 읽을 문장: ${source.evidenceUrnIds.length}개`);
          }

          return [`<strong>${dateLabel}</strong>`, ...rows].join("<br/>");
        },
      },
      axisPointer: {
        type: "line",
        lineStyle: {
          color: "rgba(94, 234, 212, 0.6)",
          width: 1,
          type: "dashed",
        },
      },
      xAxis: {
        type: "category",
        data: categories,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "rgba(148,163,184,0.3)" } },
        axisLabel: { color: "#94a3b8", fontSize: 10 },
        axisTick: { show: false },
        axisPointer:
          highlightCategory !== undefined
            ? {
                value: highlightCategory,
                lineStyle: { color: "rgba(56, 189, 248, 0.7)", width: 1.4, type: "dashed" },
              }
            : undefined,
      },
      yAxis: [
        {
          type: "value",
          name: "감성 온도",
          position: "left",
          alignTicks: true,
          axisLine: { show: false },
          axisLabel: { color: "#94a3b8", fontSize: 10 },
          splitLine: { lineStyle: { color: "rgba(148,163,184,0.12)" } },
        },
        {
          type: "value",
          name: "가격",
          position: "right",
          alignTicks: true,
          axisLine: { show: false },
          axisLabel: { color: "#94a3b8", fontSize: 10 },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        {
          type: "inside",
          start: 0,
          end: 100,
          zoomLock: planTier === "free",
        },
        {
          type: "slider",
          show: false,
        },
      ],
      series: [
        {
          name: "감성 온도",
          type: "line",
          smooth: true,
          data: sentiment,
          yAxisIndex: 0,
          connectNulls: true,
          lineStyle: { width: 2.4, color: "#38BDF8" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(56, 189, 248, 0.35)" },
                { offset: 1, color: "rgba(15, 23, 42, 0)" },
              ],
            },
          },
          symbol: "none",
          markLine: lineHighlight,
        },
        {
          name: "가격",
          type: "line",
          smooth: true,
          data: prices,
          yAxisIndex: 1,
          connectNulls: true,
          lineStyle: { width: 2, color: "#F97316" },
          symbol: "none",
          markLine: lineHighlight,
        },
        ...(showVolume
          ? [
              {
                name: "거래량",
                type: "bar",
                data: volumes,
                yAxisIndex: 0,
                barWidth: "60%",
                itemStyle: { color: "rgba(94, 234, 212, 0.35)" },
                silent: true,
              },
            ]
          : []),
      ],
      visualMap: highlightIndex >= 0
        ? [
            {
              type: "piecewise",
              show: false,
              dimension: 0,
              pieces: [
                {
                  lt: highlightIndex,
                  color: "#38BDF8",
                },
                {
                  gte: highlightIndex,
                  color: "#0EA5E9",
                },
              ],
            },
          ]
        : undefined,
    };
  }, [hasData, locked, points, planTier, showVolume, highlightIndex, prefersReducedMotion]);

  const handleMouseOver = useMemo(
    () => ({
      mouseover: (event: { dataIndex?: number }) => {
        if (typeof event.dataIndex !== "number") {
          return;
        }
        onHoverPoint?.(points[event.dataIndex] ?? null);
      },
      globalout: () => {
        onHoverPoint?.(null);
      },
      click: (event: { dataIndex?: number }) => {
        if (typeof event.dataIndex !== "number") {
          return;
        }
        const point = points[event.dataIndex];
        if (point) {
          onSelectPoint?.(point);
        }
      },
    }),
    [onHoverPoint, onSelectPoint, points],
  );

  return (
    <section className="relative rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
            감성·가격 추이 살펴보기
          </h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{PLAN_DESCRIPTION[planTier]}</p>
        </div>
        <span className="rounded-md border border-border-light px-2 py-1 text-[11px] font-semibold uppercase text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          {planTier}
        </span>
      </header>

      <div className="mt-4">
        {locked ? (
          <PlanLock
            requiredTier="pro"
            currentTier={planTier}
            description="Pro 이상 플랜에서 감성·가격 타임라인과 증거 연동을 함께 확인할 수 있습니다."
            onUpgrade={onRequestUpgrade}
            className="flex h-[240px] flex-col justify-center"
          />
        ) : !hasData ? (
          <div className="flex h-[240px] items-center justify-center rounded-lg border border-dashed border-border-light text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            아직 보여드릴 타임라인이 없어요. 잠시 뒤 다시 살펴볼까요?
          </div>
        ) : option ? (
          <ReactECharts
            option={option}
            style={{ height }}
            notMerge
            lazyUpdate
            onEvents={handleMouseOver}
            onChartReady={handleChartReady}
            theme="light"
          />
        ) : (
          <div className="flex h-[240px] items-center justify-center rounded-lg border border-border-light text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            차트를 잠시 불러오지 못했어요. 새로고침 후 다시 도와드릴게요.
          </div>
        )}
      </div>
    </section>
  );
}


