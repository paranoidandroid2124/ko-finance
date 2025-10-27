"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import type { PlanTier } from "@/components/evidence";

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
  onRequestUpgrade?: () => void;
};

const PLAN_DESCRIPTION: Record<PlanTier, string> = {
  free: "가격·거래량 축은 Pro 이상에서 활성화됩니다.",
  pro: "감성·가격 추세를 함께 검토할 수 있습니다.",
  enterprise: "감성·가격·거래량을 모두 표시합니다.",
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
  const highlightIndex = useMemo(() => {
    if (!highlightDate) {
      return -1;
    }
    return points.findIndex((point) => point.date === highlightDate);
  }, [points, highlightDate]);

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

    return {
      backgroundColor: "transparent",
      grid: {
        top: 32,
        left: 16,
        right: planTier === "free" ? 16 : 40,
        bottom: showVolume ? 40 : 20,
        containLabel: true,
      },
      legend: {
        data: ["감성 지수", "가격", ...(showVolume ? ["거래량"] : [])],
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
              return `${item.seriesName}: 데이터 없음`;
            }
            const formatted =
              item.seriesName === "감성 지수"
                ? item.value.toFixed(2)
                : item.seriesName === "거래량"
                ? item.value.toLocaleString()
                : item.value.toLocaleString(undefined, { maximumFractionDigits: 2 });
            return `${item.seriesName}: <strong>${formatted}</strong>`;
          });

          if (source?.eventType) {
            rows.push(`이벤트: ${source.eventType}`);
          }
          if (source?.evidenceUrnIds && source.evidenceUrnIds.length) {
            rows.push(`관련 근거: ${source.evidenceUrnIds.length}개`);
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
      },
      yAxis: [
        {
          type: "value",
          name: "감성",
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
          name: "감성 지수",
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
  }, [hasData, locked, points, planTier, showVolume, highlightIndex]);

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
            타임라인 감성·가격 추이
          </h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{PLAN_DESCRIPTION[planTier]}</p>
        </div>
        <span className="rounded-md border border-border-light px-2 py-1 text-[11px] font-semibold uppercase text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          {planTier}
        </span>
      </header>

      <div className="mt-4">
        {locked ? (
          <div className="flex h-[240px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border-light/80 bg-white/70 text-center text-sm text-text-secondaryLight dark:border-border-dark/70 dark:bg-white/10 dark:text-text-secondaryDark">
            <p className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
              상위 플랜 전용 타임라인
            </p>
            <p className="text-xs leading-5">
              감성 지수와 가격 스파크라인은 Pro 이상에서 사용할 수 있어요. 업그레이드하고 시장 반응을 한눈에 확인해 보세요.
            </p>
            {onRequestUpgrade ? (
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white transition-motion-fast hover:bg-primary-hover"
                onClick={onRequestUpgrade}
              >
                업그레이드 문의
              </button>
            ) : null}
          </div>
        ) : !hasData ? (
          <div className="flex h-[240px] items-center justify-center rounded-lg border border-dashed border-border-light text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            표시할 타임라인 데이터가 없습니다.
          </div>
        ) : option ? (
          <ReactECharts
            option={option}
            style={{ height }}
            notMerge
            lazyUpdate
            onEvents={handleMouseOver}
            theme="light"
          />
        ) : (
          <div className="flex h-[240px] items-center justify-center rounded-lg border border-border-light text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            차트를 불러오지 못했습니다.
          </div>
        )}
      </div>
    </section>
  );
}
