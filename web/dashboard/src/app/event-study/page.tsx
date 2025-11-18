"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { FilterChip } from "@/components/ui/FilterChip";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  useEventStudyBoard,
  useEventStudyEventDetail,
  type EventStudyBoardResponse,
  type EventStudyEvent,
  type EventStudyEventDetailResponse,
} from "@/hooks/useEventStudy";
import {
  EvidencePanel,
  type EvidenceItem,
  type EvidencePanelStatus,
} from "@/components/evidence/EvidencePanel";
import { usePlanTier } from "@/store/planStore";
import type { PlanTier } from "@/store/planStore/types";
import { EventStudyBoardHeader, RestatementRadarFooter } from "@/components/legal";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const EVENT_TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "BUYBACK", label: "자사주 매입" },
  { value: "SEO", label: "유상증자" },
  { value: "DIVIDEND", label: "배당" },
  { value: "RESTATEMENT", label: "정정 공시" },
  { value: "CONTRACT", label: "대형 계약" },
  { value: "MNA", label: "M&A" },
];

const CAP_BUCKET_OPTIONS = [
  { value: "ALL", label: "전체" },
  { value: "LARGE", label: "대형" },
  { value: "MID", label: "중형" },
  { value: "SMALL", label: "소형" },
];

const RANGE_OPTIONS = [
  { value: 7, label: "7일" },
  { value: 30, label: "30일" },
  { value: 90, label: "90일" },
];

const formatDate = (input: Date) => input.toISOString().slice(0, 10);
const formatPercent = (value?: number | null, digits = 2) =>
  value == null ? "—" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
export default function EventStudyBoardPage() {
  const [rangePreset, setRangePreset] = useState(30);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [capBucket, setCapBucket] = useState("ALL");
  const [sectorInput, setSectorInput] = useState("");
  const [minSalience, setMinSalience] = useState(0);
  const [selectedReceipt, setSelectedReceipt] = useState<string | null>(null);
  const planTier = usePlanTier();

  const endDate = useMemo(() => new Date(), []);
  const startDate = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() - rangePreset);
    return date;
  }, [rangePreset]);

  const boardQuery = useMemo(
    () => ({
      startDate: formatDate(startDate),
      endDate: formatDate(endDate),
      eventTypes: selectedTypes.length ? selectedTypes : undefined,
      capBuckets: capBucket === "ALL" ? undefined : [capBucket],
      sectorSlugs: sectorInput.trim() ? [sectorInput.trim()] : undefined,
      minSalience: minSalience > 0 ? minSalience : undefined,
      limit: 50,
      offset: 0,
    }),
    [startDate, endDate, selectedTypes, capBucket, sectorInput, minSalience],
  );

  const { data, isLoading, isError } = useEventStudyBoard(boardQuery);
  const detailParams = useMemo(() => ({ windowKey: data?.window.key }), [data?.window.key]);
  const { data: detail, isLoading: isDetailLoading } = useEventStudyEventDetail(selectedReceipt, detailParams, {
    enabled: Boolean(selectedReceipt),
  });

  const handleToggleEventType = (value: string) => {
    setSelectedTypes((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value],
    );
  };

  const handleSelectEvent = (event: EventStudyEvent) => {
    setSelectedReceipt(event.receiptNo);
  };

  return (
    <AppShell title="Event Study 보드" description="기간별 이벤트 성과와 근거를 한눈에 살펴보세요.">
      <div className="flex flex-col gap-6">
        <FilterPanel
          rangePreset={rangePreset}
          onRangeChange={setRangePreset}
          selectedTypes={selectedTypes}
          onToggleEventType={handleToggleEventType}
          capBucket={capBucket}
          onCapBucketChange={setCapBucket}
          sectorInput={sectorInput}
          onSectorInputChange={setSectorInput}
          minSalience={minSalience}
          onSalienceChange={setMinSalience}
        />
        <EventStudyBoardHeader className="text-xs text-muted-foreground" />
        {isLoading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            데이터를 불러오는 중입니다...
          </div>
        ) : isError ? (
          <EmptyState title="보드를 불러오지 못했습니다." body="잠시 후 다시 시도해주세요." />
        ) : !data || data.events.total === 0 ? (
          <EmptyState title="표시할 이벤트가 없습니다." body="필터를 변경해 다시 검색해 보세요." />
        ) : (
          <>
            <SummarySection board={data} />
            <HeatmapSection board={data} />
            {data.restatementHighlights.length > 0 ? (
              <RestatementSection highlights={data.restatementHighlights} onSelectEvent={handleSelectEvent} />
            ) : null}
            <EventTable
              board={data}
              selectedReceipt={selectedReceipt}
              onSelectEvent={handleSelectEvent}
              isDetailLoading={isDetailLoading}
              detail={detail}
              planTier={planTier}
            />
          </>
        )}
      </div>
    </AppShell>
  );
}

type FilterPanelProps = {
  rangePreset: number;
  onRangeChange: (value: number) => void;
  selectedTypes: string[];
  onToggleEventType: (value: string) => void;
  capBucket: string;
  onCapBucketChange: (value: string) => void;
  sectorInput: string;
  onSectorInputChange: (value: string) => void;
  minSalience: number;
  onSalienceChange: (value: number) => void;
};

function FilterPanel({
  rangePreset,
  onRangeChange,
  selectedTypes,
  onToggleEventType,
  capBucket,
  onCapBucketChange,
  sectorInput,
  onSectorInputChange,
  minSalience,
  onSalienceChange,
}: FilterPanelProps) {
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold text-muted-foreground">기간</span>
        {RANGE_OPTIONS.map((option) => (
          <FilterChip
            key={option.value}
            label={option.label}
            selected={rangePreset === option.value}
            onClick={() => onRangeChange(option.value)}
          />
        ))}
      </div>
      <div className="mt-4">
        <span className="mb-2 block text-sm font-semibold text-muted-foreground">이벤트 타입</span>
        <div className="flex flex-wrap gap-2">
          {EVENT_TYPE_OPTIONS.map((option) => (
            <FilterChip
              key={option.value}
              label={option.label}
              selected={selectedTypes.includes(option.value)}
              onClick={() => onToggleEventType(option.value)}
            />
          ))}
        </div>
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <label className="flex flex-col gap-2 text-sm font-medium">
          시가총액 구간
          <select
            className="rounded-xl border border-border bg-transparent px-3 py-2 text-base"
            value={capBucket}
            onChange={(event) => onCapBucketChange(event.target.value)}
          >
            {CAP_BUCKET_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm font-medium">
          섹터 필터(슬러그)
          <input
            type="text"
            placeholder="semiconductor, mobile..."
            className="rounded-xl border border-border bg-transparent px-3 py-2 text-base"
            value={sectorInput}
            onChange={(event) => onSectorInputChange(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-2 text-sm font-medium">
          최소 Salience
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minSalience}
            onChange={(event) => onSalienceChange(Number(event.target.value))}
          />
          <span className="text-xs text-muted-foreground">{(minSalience * 100).toFixed(0)}% 이상</span>
        </label>
      </div>
    </section>
  );
}

type SummarySectionProps = {
  board: EventStudyBoardResponse;
};

function SummarySection({ board }: SummarySectionProps) {
  if (!board.summary.length) {
    return null;
  }
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">요약</p>
          <p className="text-lg font-semibold">{board.window.label} 윈도우</p>
        </div>
        <p className="text-xs text-muted-foreground">업데이트: {new Date(board.asOf).toLocaleString()}</p>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {board.summary.map((item) => (
          <div key={`${item.eventType}-${item.capBucket ?? "all"}`} className="rounded-2xl border border-border p-4">
            <p className="text-sm font-semibold uppercase text-muted-foreground">{item.eventType}</p>
            <p className="text-2xl font-bold text-primary">{formatPercent(item.meanCaar)}</p>
            <div className="mt-2 text-sm text-muted-foreground">
              <div>Hit Rate: {formatPercent(item.hitRate, 1)}</div>
              <div>샘플: {item.n.toLocaleString()}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

type RestatementSectionProps = {
  highlights: EventStudyEvent[];
  onSelectEvent: (event: EventStudyEvent) => void;
};

function RestatementSection({ highlights, onSelectEvent }: RestatementSectionProps) {
  const subset = highlights.slice(0, 4);
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">정정 공시 하이라이트</p>
          <p className="text-lg font-semibold">최근 정정 이벤트</p>
        </div>
        <p className="text-xs text-muted-foreground">정정 이벤트 {highlights.length.toLocaleString()}건</p>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {subset.map((event) => (
          <button
            key={event.receiptNo}
            type="button"
            onClick={() => onSelectEvent(event)}
            className="flex flex-col rounded-2xl border border-destructive/60 bg-destructive/5 px-4 py-3 text-left transition hover:border-destructive hover:bg-destructive/10"
          >
            <div className="text-xs font-semibold text-destructive">정정</div>
            <div className="text-base font-semibold">{event.corpName ?? event.ticker ?? "알 수 없음"}</div>
            <div className="text-sm text-muted-foreground">{event.eventType}</div>
            <div className="mt-2 flex items-center justify-between text-sm">
              <span>{event.eventDate ?? "—"}</span>
              <span className="font-semibold text-destructive">{formatPercent(event.caar)}</span>
            </div>
          </button>
        ))}
      </div>
      <RestatementRadarFooter className="mt-4 text-[11px] text-muted-foreground" />
    </section>
  );
}

type HeatmapSectionProps = {
  board: EventStudyBoardResponse;
};

function HeatmapSection({ board }: HeatmapSectionProps) {
  if (!board.heatmap.length) {
    return null;
  }
  const grouped = board.heatmap.reduce<Record<string, typeof board.heatmap>>((acc, bucket) => {
    acc[bucket.eventType] = acc[bucket.eventType] || [];
    acc[bucket.eventType].push(bucket);
    return acc;
  }, {});
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="text-sm font-medium text-muted-foreground">히트맵 (주차별 평균 CAAR)</p>
      <div className="mt-4 space-y-4">
        {Object.entries(grouped).map(([eventType, buckets]) => (
          <div key={eventType}>
            <p className="mb-2 text-sm font-semibold">{eventType}</p>
            <div className="grid gap-3 md:grid-cols-3">
              {buckets.map((bucket) => (
                <div key={`${eventType}-${bucket.bucketStart}`} className="rounded-xl border border-border p-3">
                  <p className="text-xs text-muted-foreground">
                    {bucket.bucketStart} ~ {bucket.bucketEnd}
                  </p>
                  <p className="text-lg font-bold">{formatPercent(bucket.avgCaar)}</p>
                  <p className="text-xs text-muted-foreground">
                    {bucket.count.toLocaleString()}건 · 정정 비중 {formatPercent(bucket.restatementRatio, 1)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

type EventTableProps = {
  board: EventStudyBoardResponse;
  selectedReceipt: string | null;
  onSelectEvent: (event: EventStudyEvent) => void;
  detail?: ReturnType<typeof useEventStudyEventDetail>["data"];
  isDetailLoading: boolean;
  planTier: PlanTier;
};

function EventTable({ board, selectedReceipt, onSelectEvent, detail, isDetailLoading, planTier }: EventTableProps) {
  return (
    <section className="grid gap-6 lg:grid-cols-[2fr,1fr]">
      <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-3">날짜</th>
              <th className="px-4 py-3">회사</th>
              <th className="px-4 py-3">이벤트</th>
              <th className="px-4 py-3">CAAR</th>
              <th className="px-4 py-3">Salience</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {board.events.events.map((event) => (
              <tr
                key={event.receiptNo}
                className={`cursor-pointer ${selectedReceipt === event.receiptNo ? "bg-muted/40" : "hover:bg-muted/20"}`}
                onClick={() => onSelectEvent(event)}
              >
                <td className="px-4 py-3">{event.eventDate ?? "—"}</td>
                <td className="px-4 py-3">
                  <div className="font-semibold">{event.corpName ?? event.ticker ?? "알 수 없음"}</div>
                  <div className="text-xs text-muted-foreground">{event.ticker ?? "-"}</div>
                </td>
                <td className="px-4 py-3">
                  <div>{event.eventType}</div>
                  {event.isRestatement ? <span className="text-xs text-rose-500">정정</span> : null}
                </td>
                <td className="px-4 py-3 font-semibold">{formatPercent(event.caar)}</td>
                <td className="px-4 py-3">{formatPercent(event.salience)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        {!selectedReceipt ? (
          <p className="text-sm text-muted-foreground">왼쪽 테이블에서 이벤트를 선택하면 상세 정보가 표시됩니다.</p>
        ) : isDetailLoading || !detail ? (
          <div className="flex items-center text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            상세 정보를 불러오는 중입니다...
          </div>
        ) : (
          <DetailPanel detail={detail} planTier={planTier} />
        )}
      </div>
    </section>
  );
}

function DetailPanel({ detail, planTier }: { detail: EventStudyEventDetailResponse; planTier: PlanTier }) {
  const chartOption = useMemo(() => {
    if (!detail.series.length) {
      return null;
    }
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 24, right: 12, top: 16, bottom: 24 },
      xAxis: { type: "category", data: detail.series.map((point) => point.t) },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (value: number) => `${(value * 100).toFixed(1)}%`,
        },
      },
      series: [
        {
          name: "CAR",
          type: "line",
          smooth: true,
          data: detail.series.map((point) => Number((point.car ?? 0).toFixed(6))),
        },
      ],
    };
  }, [detail.series]);
  const evidenceItems = useMemo<EvidenceItem[]>(() => {
    if (!detail.evidence.length) {
      return [];
    }
    return detail.evidence.map((entry, index) => ({
      urnId: entry.urnId ?? `${detail.receiptNo}-evidence-${index}`,
      quote: entry.quote ?? undefined,
      section: entry.section ?? undefined,
      pageNumber: entry.pageNumber ?? undefined,
      viewerUrl: entry.viewerUrl ?? entry.documentUrl ?? detail.viewerUrl ?? undefined,
      documentTitle: entry.documentTitle ?? undefined,
      documentUrl: entry.documentUrl ?? entry.viewerUrl ?? detail.viewerUrl ?? undefined,
      documentMeta: {
        title: entry.documentTitle ?? detail.corpName ?? detail.ticker ?? undefined,
        corpName: detail.corpName ?? undefined,
        ticker: detail.ticker ?? undefined,
        receiptNo: detail.receiptNo,
        viewerUrl: entry.viewerUrl ?? detail.viewerUrl ?? undefined,
        publishedAt: detail.eventDate ?? undefined,
      },
    }));
  }, [detail]);
  const evidenceStatus: EvidencePanelStatus = evidenceItems.length ? "ready" : "empty";

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs uppercase text-muted-foreground">{detail.eventType}</p>
        <p className="text-lg font-semibold">{detail.corpName ?? detail.ticker}</p>
        <p className="text-xs text-muted-foreground">윈도우 {detail.window}</p>
      </div>
      {chartOption ? <ReactECharts option={chartOption} style={{ height: 200 }} /> : null}
      <div className="rounded-xl bg-muted/40 p-3 text-sm">
        <div className="flex justify-between">
          <span>CAAR</span>
          <span className="font-semibold">{formatPercent(detail.series.at(-1)?.car ?? null)}</span>
        </div>
        <div className="flex justify-between text-muted-foreground">
          <span>Salience</span>
          <span>{formatPercent(detail.salience)}</span>
        </div>
      </div>
      <div className="space-y-2">
        <p className="text-xs font-semibold text-muted-foreground">근거/문서</p>
        {detail.documents.length ? (
          detail.documents.map((doc) => (
            <a
              key={`${doc.viewerUrl ?? doc.title ?? ""}`}
              href={doc.viewerUrl ?? "#"}
              target="_blank"
              className="block rounded-xl border border-border px-3 py-2 text-sm hover:border-primary"
              rel="noreferrer"
            >
              <p className="font-medium">{doc.title ?? "공시 원문"}</p>
              <p className="text-xs text-muted-foreground">{doc.publishedAt ?? "—"}</p>
            </a>
          ))
        ) : (
          <p className="text-xs text-muted-foreground">연결된 문서가 없습니다.</p>
        )}
      </div>
      <EvidencePanel
        planTier={planTier}
        status={evidenceStatus}
        items={evidenceItems}
        inlinePdfEnabled={false}
        pdfUrl={detail.viewerUrl}
      />
    </div>
  );
}
