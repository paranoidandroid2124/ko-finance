"use client";

import { HelpCircle } from "lucide-react";
import { useMemo } from "react";
import { useSectorTimeseries } from "@/hooks/useSectorTimeseries";
import type { SectorSignalPoint } from "@/hooks/useSectorSignals";

type SectorSparkCardProps = {
  point: SectorSignalPoint;
  onSelect?: (point: SectorSignalPoint) => void;
};

const CARD_WIDTH = 220;
const CARD_HEIGHT = 90;
const SPARK_HEIGHT = 48;
const GRID_ROW_COUNT = 3;
const GRID_COL_COUNT = 4;
const volumeFormatter = new Intl.NumberFormat("ko-KR");

function formatSentimentValue(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(2);
}

function formatVolumeValue(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "--";
  }
  return volumeFormatter.format(Math.round(value));
}

type InfoTooltipProps = {
  text: string;
  align?: "left" | "right" | "center";
};

function InfoTooltip({ text, align = "right" }: InfoTooltipProps) {
  const position =
    align === "center" ? "left-1/2 -translate-x-1/2" : align === "left" ? "left-0" : "right-0";
  return (
    <span className="group relative inline-flex items-center text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
      <HelpCircle className="h-3.5 w-3.5" aria-hidden />
      <span
        className={`pointer-events-none absolute top-full z-10 w-max translate-y-2 rounded-md border border-border-light bg-background-cardLight px-3 py-1 text-[11px] leading-relaxed text-text-secondaryLight opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark ${position}`}
      >
        {text}
      </span>
    </span>
  );
}

function buildSparkPath(values: number[], minValue: number, range: number): string {
  if (values.length === 0) {
    return "";
  }

  return values
    .map((value, index) => {
      const x = values.length === 1 ? CARD_WIDTH : (index / (values.length - 1)) * CARD_WIDTH;
      const normalized = (value - minValue) / range;
      const y = SPARK_HEIGHT - normalized * SPARK_HEIGHT;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildVolumeRects(volumes: number[]): { x: number; height: number; width: number }[] {
  if (volumes.length === 0) {
    return [];
  }
  const maxVolume = Math.max(...volumes, 1);
  const barWidth = CARD_WIDTH / Math.max(volumes.length, 1);

  return volumes.map((volume, index) => {
    const ratio = volume / maxVolume;
    const height = Math.max(2, ratio * 24);
    return {
      x: index * barWidth,
      height,
      width: barWidth - 1.5,
    };
  });
}

export function SectorSparkCard({ point, onSelect }: SectorSparkCardProps) {
  const { data, isLoading, isError } = useSectorTimeseries(point.sector.id, 30);
  const stats = useMemo(() => {
    const series = data?.series ?? [];
    if (!series.length) {
      return {
        sentiments: [] as number[],
        volumes: [] as number[],
        first: null as number | null,
        last: null as number | null,
        maxValue: 0,
        minValue: 0,
        average: null as number | null,
        totalVolume: 0,
        range: 1,
      };
    }
    const sentiments = series.map((item) => item.sentMean ?? 0);
    const volumes = series.map((item) => item.volume ?? 0);
    const first = sentiments[0] ?? null;
    const last = sentiments[sentiments.length - 1] ?? null;
    const maxValue = Math.max(...sentiments);
    const minValue = Math.min(...sentiments);
    const average = sentiments.reduce((sum, value) => sum + value, 0) / sentiments.length;
    const totalVolume = volumes.reduce((sum, value) => sum + value, 0);
    const range = maxValue - minValue || 1;
    return {
      sentiments,
      volumes,
      first,
      last,
      maxValue,
      minValue,
      average,
      totalVolume,
      range,
    };
  }, [data?.series]);
  const sparkPath = useMemo(() => buildSparkPath(stats.sentiments, stats.minValue, stats.range), [stats]);
  const volumeRects = useMemo(() => buildVolumeRects(stats.volumes), [stats.volumes]);
  const zeroLineY = useMemo(() => {
    if (!stats.sentiments.length) {
      return null;
    }
    if (stats.minValue > 0 || stats.maxValue < 0) {
      return null;
    }
    const normalized = (0 - stats.minValue) / stats.range;
    return SPARK_HEIGHT - normalized * SPARK_HEIGHT;
  }, [stats]);
  const sentimentZValue = data?.current?.sentZ7d ?? point.sentimentZ ?? null;
  const delta7dValue = data?.current?.delta7d ?? point.deltaSentiment7d ?? null;
  const sentimentZClass =
    sentimentZValue == null
      ? "text-text-secondaryLight dark:text-text-secondaryDark"
      : sentimentZValue >= 0
        ? "text-accent-positive"
        : "text-accent-negative";
  const deltaClass =
    delta7dValue == null
      ? "text-text-secondaryLight dark:text-text-secondaryDark"
      : "text-text-primaryLight dark:text-text-primaryDark";
  const hasSparkData = stats.sentiments.length > 0;

  const handleSelect = () => {
    if (onSelect) {
      onSelect(point);
    }
  };

  return (
    <button
      type="button"
      onClick={handleSelect}
      className="flex w-full flex-col gap-3 rounded-xl border border-border-light bg-background-cardLight p-4 text-left shadow-card transition hover:border-primary hover:shadow-lg dark:border-border-dark dark:bg-background-cardDark"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">{point.sector.slug}</p>
          <h4 className="text-sm font-semibold">{point.sector.name}</h4>
        </div>
        <div className="flex flex-col items-end gap-1 text-xs">
          <div className="flex items-center gap-1 text-text-secondaryLight dark:text-text-secondaryDark">
            <span>감성 Z</span>
            <span className={`font-semibold ${sentimentZClass}`}>{formatSentimentValue(sentimentZValue)}</span>
            <InfoTooltip text="감성 Z는 최근 평균 감성이 과거 평균 대비 얼마나 이례적인지를 나타냅니다." />
          </div>
          <div className="flex items-center gap-1 text-text-secondaryLight dark:text-text-secondaryDark">
            <span>Δ7d</span>
            <span className={`font-semibold ${deltaClass}`}>{formatSentimentValue(delta7dValue)}</span>
            <InfoTooltip text="Δ7d는 일주일 전과 비교했을 때 평균 감성이 얼마나 변했는지를 뜻합니다." />
          </div>
        </div>
      </div>

      <div className="space-y-1">
        <div className="relative h-[110px] w-full">
          <svg width={CARD_WIDTH} height={CARD_HEIGHT} viewBox={`0 0 ${CARD_WIDTH} ${CARD_HEIGHT}`} className="w-full">
            <g aria-hidden>
              <line
                x1={16}
                y1={4}
                x2={16}
                y2={SPARK_HEIGHT}
                stroke="rgba(148,163,184,0.35)"
                strokeWidth={1.25}
              />
              <line
                x1={16}
                y1={SPARK_HEIGHT}
                x2={CARD_WIDTH - 6}
                y2={SPARK_HEIGHT}
                stroke="rgba(148,163,184,0.35)"
                strokeWidth={1.25}
              />
              {Array.from({ length: GRID_ROW_COUNT }, (_, idx) => {
                const y = SPARK_HEIGHT - ((idx + 1) / (GRID_ROW_COUNT + 1)) * (SPARK_HEIGHT - 8);
                return (
                  <line
                    key={`grid-row-${idx}`}
                    x1={16}
                    y1={y}
                    x2={CARD_WIDTH - 6}
                    y2={y}
                    stroke="rgba(148,163,184,0.18)"
                    strokeWidth={1}
                    strokeDasharray="3 5"
                  />
                );
              })}
              {Array.from({ length: GRID_COL_COUNT }, (_, idx) => {
                const x = 16 + ((idx + 1) / (GRID_COL_COUNT + 1)) * (CARD_WIDTH - 22);
                return (
                  <line
                    key={`grid-col-${idx}`}
                    x1={x}
                    y1={4}
                    x2={x}
                    y2={SPARK_HEIGHT}
                    stroke="rgba(148,163,184,0.18)"
                    strokeWidth={1}
                    strokeDasharray="3 5"
                  />
                );
              })}
            </g>
            <g transform={`translate(0 ${CARD_HEIGHT - 28})`}>
              {volumeRects.map((rect, index) => (
                <rect
                  key={`vol-${index}`}
                  x={rect.x}
                  y={24 - rect.height}
                  width={rect.width}
                  height={rect.height}
                  fill="rgba(148, 163, 184, 0.35)"
                />
              ))}
            </g>
            <g transform="translate(0 0)">
              <line x1={0} y1={SPARK_HEIGHT} x2={CARD_WIDTH} y2={SPARK_HEIGHT} stroke="rgba(148,163,184,0.25)" strokeWidth={1} />
              {typeof zeroLineY === "number" ? (
                <line
                  x1={0}
                  y1={zeroLineY}
                  x2={CARD_WIDTH}
                  y2={zeroLineY}
                  stroke="rgba(248,250,252,0.35)"
                  strokeDasharray="4 3"
                  strokeWidth={1}
                />
              ) : null}
              <path
                d={sparkPath}
                fill="none"
                stroke="url(#sparkGradient)"
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <defs>
                <linearGradient id="sparkGradient" x1="0" x2="1" y1="0" y2="0">
                  <stop offset="0%" stopColor="#38bdf8" />
                  <stop offset="100%" stopColor="#6366f1" />
                </linearGradient>
              </defs>
            </g>
          </svg>
        </div>
        <div className="flex items-center justify-between text-[10px] font-semibold tracking-[0.08em] text-text-tertiaryLight dark:text-text-tertiaryDark">
          <span>평균 감성</span>
          <span>기사량</span>
          <span>최근 30일</span>
        </div>
      </div>

      {isLoading ? (
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">시계열을 불러오는 중...</p>
      ) : isError ? (
        <p className="text-xs text-destructive">시계열 데이터를 표시할 수 없습니다.</p>
      ) : hasSparkData ? (
        <div className="space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <p>
            최근 30일 감성 {formatSentimentValue(stats.first)} → {formatSentimentValue(stats.last)}
          </p>
          <p>
            평균 {formatSentimentValue(stats.average)} · 최고 {formatSentimentValue(stats.maxValue)} · 최저{" "}
            {formatSentimentValue(stats.minValue)}
          </p>
          <p>기사량 합계 {formatVolumeValue(stats.totalVolume)}</p>
        </div>
      ) : (
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 30일 감성 데이터가 없습니다.</p>
      )}
    </button>
  );
}
