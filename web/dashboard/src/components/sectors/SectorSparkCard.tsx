"use client";

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

function buildSparkPath(values: number[]): string {
  if (values.length === 0) {
    return "";
  }
  const minValue = Math.min(...values, 0);
  const maxValue = Math.max(...values, 0);
  const range = maxValue - minValue || 1;

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
  const values = useMemo(() => (data?.series ?? []).map((item) => item.sentMean ?? 0), [data?.series]);
  const volumes = useMemo(() => (data?.series ?? []).map((item) => item.volume ?? 0), [data?.series]);
  const sparkPath = useMemo(() => buildSparkPath(values), [values]);
  const volumeRects = useMemo(() => buildVolumeRects(volumes), [volumes]);

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
        <div className="flex flex-col items-end text-xs">
          <span
            className={`font-semibold ${
              (data?.current?.sentZ7d ?? 0) >= 0 ? "text-accent-positive" : "text-accent-negative"
            }`}
          >
            Z {data?.current?.sentZ7d?.toFixed(2) ?? "--"}
          </span>
          <span className="text-text-secondaryLight dark:text-text-secondaryDark">
            Δ7d {data?.current?.delta7d?.toFixed(2) ?? "--"}
          </span>
        </div>
      </div>

      <div className="relative h-[110px] w-full">
        <svg width={CARD_WIDTH} height={CARD_HEIGHT} viewBox={`0 0 ${CARD_WIDTH} ${CARD_HEIGHT}`} className="w-full">
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

      {isLoading ? (
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">시계열을 불러오는 중...</p>
      ) : isError ? (
        <p className="text-xs text-destructive">시계열 데이터를 표시할 수 없습니다.</p>
      ) : (
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          최근 30일 평균 감성 {point.sentimentMean?.toFixed(2) ?? "--"} · 기사량 {point.volumeSum ?? "--"}
        </p>
      )}
    </button>
  );
}
