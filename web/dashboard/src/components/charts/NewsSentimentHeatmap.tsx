'use client';

import dynamic from 'next/dynamic';
import { useMemo, useState, useCallback, useEffect } from 'react';
import { shallow } from 'zustand/shallow';
import { useNewsHeatmap, type HeatmapArticle } from '@/hooks/useNewsHeatmap';
import { selectNewsFilterOptions, useNewsFilterStore } from '@/store/newsFilterStore';

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false });

const windowToMinutes = {
  '1h': 60,
  '24h': 24 * 60,
  '7d': 7 * 24 * 60,
} as const;

type SelectedHeatmapCell = {
  sectorLabel: string;
  bucketLabel: string;
  sentiment: number | null;
  articleCount: number;
  articles: HeatmapArticle[];
};

export function NewsSentimentHeatmap() {
  const { window, sectors: selectedSectors } = useNewsFilterStore(selectNewsFilterOptions, shallow);
  const windowMinutes = windowToMinutes[window] ?? windowToMinutes['24h'];

  const { data, isLoading, isError } = useNewsHeatmap({ windowMinutes });
  const [selectedCell, setSelectedCell] = useState<SelectedHeatmapCell | null>(null);

  useEffect(() => {
    setSelectedCell(null);
  }, [windowMinutes, selectedSectors]);

  const sectors = data?.sectors ?? [];
  const buckets = data?.buckets ?? [];
  const points = data?.points ?? [];

  const filteredHeatmap = useMemo(() => {
    if (!points.length || !sectors.length) {
      return { sectors, points };
    }
    const sectorFilter = new Set(selectedSectors);
    if (sectorFilter.size === 0) {
      return { sectors, points };
    }

    const filteredSectors = sectors.filter((sector) => sectorFilter.has(sector));
    const sectorIndexMap = new Map<string, number>();
    filteredSectors.forEach((sector, index) => {
      sectorIndexMap.set(sector, index);
    });

    const filteredPoints = points
      .map((point) => {
        const sectorName = sectors[point.sector_index];
        if (!sectorFilter.has(sectorName)) {
          return null;
        }
        const mappedIndex = sectorIndexMap.get(sectorName);
        if (mappedIndex === undefined) {
          return null;
        }
        return { ...point, sector_index: mappedIndex };
      })
      .filter((point): point is (typeof points)[number] => Boolean(point));

    return { sectors: filteredSectors, points: filteredPoints };
  }, [points, sectors, selectedSectors]);

  const heatmapData = useMemo(() => {
    if (!filteredHeatmap.points.length) {
      return [];
    }
    return filteredHeatmap.points.map((point) => ({
      value: [
        point.bucket_index,
        point.sector_index,
        point.sentiment ?? 0,
        point.article_count ?? 0,
      ] as [number, number, number, number],
      articles: point.articles ?? [],
      itemStyle: {
        opacity: point.article_count ? 0.95 : 0.25,
        borderRadius: 6,
        borderWidth: point.article_count ? 1 : 0,
        borderColor: 'rgba(15, 23, 42, 0.35)',
      },
    }));
  }, [filteredHeatmap.points]);

  const handleChartClick = useCallback(
    (params: { data?: { value?: [number, number, number, number]; articles?: HeatmapArticle[] } }) => {
      const dataPoint = params?.data;
      if (!dataPoint || !Array.isArray(dataPoint.value)) {
        return;
      }
      const [bucketIndex, sectorIndex, sentimentValue, articleCount] = dataPoint.value;
      const articles = Array.isArray(dataPoint.articles) ? dataPoint.articles : [];
      if (!articleCount || !articles.length) {
        setSelectedCell(null);
        return;
      }

      const bucketLabel = buckets[bucketIndex]?.label ?? '';
      const sectorLabel = filteredHeatmap.sectors[sectorIndex] ?? '';
      setSelectedCell({
        sectorLabel,
        bucketLabel,
        sentiment: typeof sentimentValue === 'number' ? sentimentValue : null,
        articleCount,
        articles,
      });
    },
    [buckets, filteredHeatmap.sectors],
  );

  const chartEvents = useMemo(() => ({ click: handleChartClick }), [handleChartClick]);

  const option = useMemo(() => {
    if (!filteredHeatmap.sectors.length || !buckets.length) {
      return null;
    }

    return {
      backgroundColor: 'transparent',
      tooltip: {
        position: 'top',
        borderRadius: 8,
        padding: [8, 10],
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        textStyle: {
          color: '#f8fafc',
          fontSize: 12,
        },
        formatter: (params: { value: [number, number, number, number] }) => {
          const [timeIndex, sectorIndex, sentiment, articleCount] = params.value;
          const bucket = buckets[timeIndex];
          const label = bucket?.label ?? '';
          const sectorLabel = filteredHeatmap.sectors[sectorIndex] ?? '';

          if (!articleCount) {
            return [
              `<strong>${sectorLabel}</strong>`,
              `${label}`,
              '<span style="color:#cbd5f5">기사 데이터가 없습니다.</span>',
            ].join('<br/>');
          }

          const sentimentValue = typeof sentiment === 'number' ? sentiment.toFixed(2) : 'N/A';
          return [
            `<strong>${sectorLabel}</strong>`,
            `${label}`,
            `기사 수: <strong>${articleCount}건</strong>`,
            `평균 감성: <strong>${sentimentValue}</strong>`,
          ].join('<br/>');
        },
      },
      grid: {
        top: 96,
        left: 96,
        right: 112,
        bottom: 56,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: buckets.map((bucket) => bucket.label),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
        axisLabel: {
          color: '#cbd5f5',
          fontSize: 11,
          interval: 0,
          margin: 16,
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'category',
        data: filteredHeatmap.sectors,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: 'transparent' } },
        axisLabel: { color: '#e2e8f0', fontSize: 11, margin: 24 },
        splitLine: { show: false },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        top: 24,
        itemWidth: 120,
        itemHeight: 12,
        text: ['긍정', '부정'],
        textStyle: {
          color: '#cbd5f5',
          fontSize: 11,
        },
        inRange: {
          color: ['#ef4444', '#facc15', '#22c55e'],
        },
        formatter: (value: number) => (typeof value === 'number' ? value.toFixed(1) : value),
      },
      series: [
        {
          name: '감성',
          type: 'heatmap',
          data: heatmapData,
          label: { show: false },
          emphasis: {
            itemStyle: {
              shadowBlur: 12,
              shadowColor: 'rgba(15, 23, 42, 0.45)',
              borderColor: '#f8fafc',
              borderWidth: 2,
            },
          },
          cursor: 'pointer',
        },
      ],
    };
  }, [buckets, filteredHeatmap.sectors, heatmapData]);

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">섹터별 뉴스 감성 히트맵</h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            선택한 기간 동안의 감성 흐름을 시간대별로 살펴보세요.
          </p>
        </div>
      </div>
      <div className="mt-4 overflow-hidden rounded-lg">
        {isLoading ? (
          <div className="flex h-[300px] items-center justify-center">
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">데이터를 불러오는 중입니다...</span>
          </div>
        ) : isError ? (
          <div className="flex h-[300px] items-center justify-center">
            <span className="text-xs text-destructive">뉴스 감성 데이터를 가져오지 못했습니다.</span>
          </div>
        ) : option ? (
          <ReactECharts option={option} style={{ height: 300 }} onEvents={chartEvents} />
        ) : (
          <div className="flex h-[300px] items-center justify-center">
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">표시할 감성 데이터가 없습니다.</span>
          </div>
        )}
      </div>

      {selectedCell && selectedCell.articles.length > 0 && (
        <div className="mt-4 space-y-3 rounded-lg border border-border-light bg-white/80 p-4 text-sm shadow-sm dark:border-border-dark dark:bg-white/5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {selectedCell.sectorLabel} · {selectedCell.bucketLabel}
              </p>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                기사 {selectedCell.articleCount}건 · 평균 감성 {selectedCell.sentiment !== null ? selectedCell.sentiment.toFixed(2) : 'N/A'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedCell(null)}
              className="rounded-md border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              닫기
            </button>
          </div>
          <ul className="space-y-3">
            {selectedCell.articles.map((article) => (
              <li
                key={article.id}
                className="rounded-lg border border-border-light bg-white/70 p-3 text-xs dark:border-border-dark dark:bg-white/10"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <button
                      type="button"
                      onClick={() => article.url && window.open(article.url, '_blank', 'noopener,noreferrer')}
                      className="text-left text-sm font-semibold text-primary underline-offset-2 hover:underline"
                    >
                      {article.title}
                    </button>
                    <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                      {article.source || '출처 미상'} · {article.publishedAt || '시간 정보 없음'}
                    </p>
                  </div>
                  {typeof article.sentiment === 'number' && (
                    <span className="rounded bg-border-light px-2 py-0.5 text-[11px] font-medium text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark">
                      {article.sentiment.toFixed(2)}
                    </span>
                  )}
                </div>
                {article.summary ? (
                  <p className="mt-2 leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">{article.summary}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
