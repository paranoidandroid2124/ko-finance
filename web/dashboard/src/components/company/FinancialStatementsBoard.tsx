"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import clsx from "clsx";
import { ExternalLink, Loader2, Plus, Sparkles, X } from "lucide-react";

import {
  fetchCompanySnapshot,
  type CompanySnapshot,
  type FinancialStatementBlock,
  type FinancialStatementRow,
  type FinancialValue,
} from "@/hooks/useCompanySnapshot";
import { useCompanySearch, type CompanySearchResult } from "@/hooks/useCompanySearch";
import { useToastStore } from "@/store/toastStore";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

type PeriodFilter = "annual" | "quarter";

type FinancialStatementsBoardProps = {
  statements: FinancialStatementBlock[];
  corpName?: string | null;
  identifier?: string | null;
};

type PeerEntry = {
  identifier: string;
  label: string;
  statements: FinancialStatementBlock[];
};

const PERIOD_FILTERS: { label: string; value: PeriodFilter }[] = [
  { label: "연간", value: "annual" },
  { label: "분기", value: "quarter" },
];

const MAX_COLUMNS = 6;
const MAX_PEERS = 3;

const numberFormatter = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 1,
  notation: "compact",
});

const formatValue = (value?: number | null, unit?: string | null) => {
  if (value == null) {
    return "—";
  }
  const formatted = numberFormatter.format(value);
  return unit ? `${formatted} ${unit}` : formatted;
};

const dartViewerUrl = (referenceNo: string) =>
  `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${encodeURIComponent(referenceNo)}`;

const buildPeriodKey = (value: FinancialValue) => {
  const year = value.fiscalYear ?? "na";
  const period = value.fiscalPeriod ?? value.periodType ?? "na";
  const endDate = value.periodEndDate ?? "";
  return `${year}-${period}-${endDate}`;
};

const sortValuesDescending = (a: FinancialValue, b: FinancialValue) => {
  const dateA = a.periodEndDate ? Date.parse(a.periodEndDate) : null;
  const dateB = b.periodEndDate ? Date.parse(b.periodEndDate) : null;
  if (dateA && dateB) {
    return dateB - dateA;
  }
  const yearDiff = (b.fiscalYear ?? 0) - (a.fiscalYear ?? 0);
  if (yearDiff !== 0) {
    return yearDiff;
  }
  return (b.fiscalPeriod ?? "").localeCompare(a.fiscalPeriod ?? "");
};

const findRowByMetric = (blocks: FinancialStatementBlock[], metricCode: string) => {
  for (const block of blocks) {
    for (const row of block.rows) {
      if (row.metricCode === metricCode) {
        return row;
      }
    }
  }
  return null;
};

const pickLatestValue = (row: FinancialStatementRow | null, periodType: PeriodFilter) => {
  if (!row) return null;
  const filtered = row.values.filter((value) => value.periodType === periodType);
  if (!filtered.length) {
    return null;
  }
  const sorted = [...filtered].sort(sortValuesDescending);
  return sorted[0];
};

export function FinancialStatementsBoard({
  statements,
  corpName,
  identifier,
}: FinancialStatementsBoardProps) {
  const toast = useToastStore((state) => state.show);

  const initialStatement = statements[0]?.statementCode ?? "";
  const initialRow = statements[0]?.rows[0]?.metricCode ?? "";

  const hasQuarterData = statements.some((statement) =>
    statement.rows.some((row) => row.values.some((value) => value.periodType === "quarter")),
  );
  const defaultFilter: PeriodFilter = hasQuarterData ? "quarter" : "annual";

  const [periodFilter, setPeriodFilter] = useState<PeriodFilter>(defaultFilter);
  const [activeStatement, setActiveStatement] = useState(initialStatement);
  const [activeMetric, setActiveMetric] = useState(initialRow);
  const [peerInput, setPeerInput] = useState("");
  const [isAddingPeer, setIsAddingPeer] = useState(false);
  const [peers, setPeers] = useState<PeerEntry[]>([]);

  const statementOptions = useMemo(() => statements.map((entry) => entry.statementCode), [statements]);

  const currentStatement = useMemo(
    () => statements.find((entry) => entry.statementCode === activeStatement) ?? statements[0],
    [activeStatement, statements],
  );

  const rows = currentStatement?.rows ?? [];
  const currentRow =
    rows.find((row) => row.metricCode === activeMetric) ?? rows[0] ?? null;

  const availableFilters = useMemo(() => {
    const rowHasPeriod = (value: PeriodFilter) =>
      statements.some((statement) =>
        statement.rows.some((row) => row.values.some((entry) => entry.periodType === value)),
      );
    return PERIOD_FILTERS.map((option) => ({
      ...option,
      disabled: !rowHasPeriod(option.value),
    }));
  }, [statements]);

  const periodColumns = useMemo(() => {
    if (!rows.length) {
      return [];
    }
    const values = rows.flatMap((row) => row.values).filter((value) => value.periodType === periodFilter);
    const sorted = [...values].sort(sortValuesDescending);
    const unique: FinancialValue[] = [];
    const seen = new Set<string>();
    for (const value of sorted) {
      const key = buildPeriodKey(value);
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(value);
      if (unique.length >= MAX_COLUMNS) break;
    }
    return unique;
  }, [rows, periodFilter]);

  const chartSeries = useMemo(() => {
    if (!currentRow) return [];
    const values = currentRow.values
      .filter((value) => value.periodType === periodFilter && value.value != null)
      .sort(sortValuesDescending)
      .reverse();
    return values.map((value) => ({
      label: buildFriendlyPeriodLabel(value),
      value: value.value ?? 0,
    }));
  }, [currentRow, periodFilter]);

  const chartOption = useMemo(() => {
    if (!chartSeries.length) {
      return {
        textStyle: { fontFamily: "var(--font-sans, Inter)" },
      };
    }
    return {
      textStyle: { fontFamily: "var(--font-sans, Inter)" },
      grid: { left: 42, right: 12, top: 24, bottom: 28 },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value: number) => numberFormatter.format(value),
      },
      xAxis: {
        type: "category",
        data: chartSeries.map((entry) => entry.label),
        boundaryGap: false,
        axisLine: { lineStyle: { color: "var(--border-color, #e2e8f0)" } },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (value: number) => numberFormatter.format(value),
        },
        splitLine: {
          lineStyle: { color: "var(--border-color, #e2e8f0)", type: "dashed" },
        },
      },
      series: [
        {
          type: "line",
          smooth: true,
          symbolSize: 8,
          showSymbol: true,
          data: chartSeries.map((entry) => entry.value),
          itemStyle: { color: "var(--primary-color, #2563eb)" },
          lineStyle: { width: 3 },
          areaStyle: {
            color: "var(--primary-color, #2563eb)",
            opacity: 0.08,
          },
        },
      ],
    };
  }, [chartSeries]);

  const {
    data: peerSearchResults = [],
    isFetching: isSearchingPeers,
  } = useCompanySearch(peerInput, 5);
  const trimmedPeerInput = peerInput.trim();
  const showPeerSuggestions = trimmedPeerInput.length >= 1 && (isSearchingPeers || peerSearchResults.length > 0);

  const handleStatementChange = (code: string) => {
    setActiveStatement(code);
    const nextStatement = statements.find((entry) => entry.statementCode === code);
    if (nextStatement?.rows.length) {
      setActiveMetric(nextStatement.rows[0].metricCode);
    }
  };

  const addPeerByIdentifier = async (rawIdentifier: string) => {
    const normalized = rawIdentifier.trim().toUpperCase();
    if (!normalized) {
      toast({ message: "추가할 티커 또는 법인코드를 입력해 주세요.", intent: "warning" });
      return;
    }
    if (identifier && normalized === identifier.toUpperCase()) {
      toast({ message: "현재 보고 있는 기업과 동일합니다.", intent: "warning" });
      return;
    }
    if (peers.some((peer) => peer.identifier === normalized)) {
      toast({ message: "이미 추가된 기업입니다.", intent: "info" });
      return;
    }
    if (peers.length >= MAX_PEERS) {
      toast({ message: `피어는 최대 ${MAX_PEERS}개까지 비교할 수 있습니다.`, intent: "warning" });
      return;
    }
    setIsAddingPeer(true);
    try {
      const snapshot: CompanySnapshot = await fetchCompanySnapshot(normalized);
      if (!snapshot.financialStatements.length) {
        toast({ message: "선택한 기업의 재무제표를 찾을 수 없습니다.", intent: "error" });
        return;
      }
      setPeers((prev) => [
        ...prev,
        {
          identifier: normalized,
          label: snapshot.corpName ?? snapshot.ticker ?? normalized,
          statements: snapshot.financialStatements,
        },
      ]);
      setPeerInput("");
      toast({ message: "피어를 추가했습니다.", intent: "success", duration: 2500 });
    } catch (error) {
      toast({
        message:
          error instanceof Error ? error.message : "피어 데이터를 불러오지 못했습니다.",
        intent: "error",
      });
    } finally {
      setIsAddingPeer(false);
    }
  };
  const handleAddPeer = async (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    await addPeerByIdentifier(peerInput);
  };

  const handlePeerSuggestionSelect = async (candidate: CompanySearchResult) => {
    const identifierValue = candidate.corpCode ?? candidate.ticker;
    if (!identifierValue) {
      toast({ message: "선택한 기업의 티커/법인코드를 확인할 수 없습니다.", intent: "warning" });
      return;
    }
    await addPeerByIdentifier(identifierValue);
  };

  const removePeer = (identifierToRemove: string) => {
    setPeers((prev) => prev.filter((peer) => peer.identifier !== identifierToRemove));
  };

  const baseLatestValue = pickLatestValue(currentRow, periodFilter);
  const peerComparisons = peers.map((peer) => {
    const row = findRowByMetric(peer.statements, activeMetric);
    const latest = pickLatestValue(row, periodFilter);
    return {
      identifier: peer.identifier,
      label: peer.label,
      latest,
    };
  });

  if (!statements.length) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card transition dark:border-border-dark dark:bg-background-cardDark">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            재무제표 스택
          </p>
          <h2 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
            {corpName ?? "선택한 기업"} 재무 하이라이트
          </h2>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-border-light bg-background-base/80 px-2 py-1 text-xs dark:border-border-dark dark:bg-background-dark/60">
          <Sparkles className="h-4 w-4 text-primary" />
          <span>값을 클릭하면 차트·피어 비교가 갱신됩니다</span>
        </div>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-full border border-border-light bg-background-base p-0.5 dark:border-border-dark dark:bg-background-dark">
          {availableFilters.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={option.disabled}
              onClick={() => setPeriodFilter(option.value)}
              className={clsx(
                "rounded-full px-3 py-1 text-xs font-semibold transition",
                periodFilter === option.value
                  ? "bg-primary text-white shadow"
                  : "text-text-secondaryLight hover:text-text-primaryLight dark:text-text-secondaryDark dark:hover:text-text-primaryDark",
                option.disabled ? "cursor-not-allowed opacity-40" : "cursor-pointer",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="inline-flex rounded-full border border-border-light bg-background-base p-0.5 text-xs dark:border-border-dark dark:bg-background-dark">
          {statementOptions.map((code) => {
            const statement = statements.find((entry) => entry.statementCode === code);
            return (
              <button
                key={code}
                type="button"
                onClick={() => handleStatementChange(code)}
                className={clsx(
                  "rounded-full px-3 py-1 font-semibold transition",
                  activeStatement === code
                    ? "bg-text-primaryLight text-background-cardLight dark:bg-text-primaryDark dark:text-background-cardDark"
                    : "text-text-secondaryLight hover:text-text-primaryLight dark:text-text-secondaryDark dark:hover:text-text-primaryDark",
                )}
              >
                {statement?.label ?? code}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="overflow-hidden rounded-2xl border border-border-light dark:border-border-dark">
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr className="bg-background-base/80 text-xs uppercase tracking-wide text-text-secondaryLight dark:bg-background-dark/60 dark:text-text-secondaryDark">
                  <th className="px-4 py-3 text-left font-semibold">지표</th>
                  {periodColumns.map((period) => (
                    <th key={buildPeriodKey(period)} className="px-4 py-3 text-right font-semibold">
                      {buildFriendlyPeriodLabel(period)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.metricCode}
                    className={clsx(
                      "border-t border-border-light/70 text-text-primaryLight transition hover:bg-primary/5 dark:border-border-dark/60 dark:text-text-primaryDark",
                      row.metricCode === activeMetric ? "bg-primary/10 dark:bg-primary/15" : "",
                    )}
                    onClick={() => setActiveMetric(row.metricCode)}
                  >
                    <th className="min-w-[160px] px-4 py-3 text-left text-sm font-semibold">
                      {row.label}
                    </th>
                    {periodColumns.map((period) => {
                      const current = row.values.find(
                        (value) =>
                          value.periodType === periodFilter &&
                          buildPeriodKey(value) === buildPeriodKey(period),
                      );
                      return (
                        <td key={`${row.metricCode}-${buildPeriodKey(period)}`} className="px-4 py-3 text-right text-sm">
                          <div className="inline-flex items-center gap-2">
                            <span>{formatValue(current?.value, current?.unit)}</span>
                            {current?.referenceNo ? (
                              <a
                                href={dartViewerUrl(current.referenceNo)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="rounded-full border border-border-light/80 p-1 text-xs text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark/60 dark:text-text-secondaryDark"
                                title="DART 원문 보기"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                              </a>
                            ) : null}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex flex-col gap-4 rounded-2xl border border-border-light bg-background-base/70 p-4 dark:border-border-dark dark:bg-background-dark/40">
          <div>
            <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              차트
            </p>
            <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {currentRow?.label ?? "지표 선택"}
            </h3>
          </div>
          <div className="min-h-[220px] rounded-xl border border-border-light/70 bg-background-cardLight/80 p-2 dark:border-border-dark/60 dark:bg-background-cardDark/60">
            {chartSeries.length ? (
              <ReactECharts option={chartOption} style={{ height: 220 }} />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                선택한 기간에 데이터가 없습니다.
              </div>
            )}
          </div>

          <div className="space-y-3 rounded-xl border border-dashed border-border-light/70 p-4 dark:border-border-dark/60">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                  피어 비교
                </p>
                <h4 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  최근 {periodFilter === "annual" ? "연간" : "분기"} 값 비교
                </h4>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                최대 {MAX_PEERS}개
              </span>
            </div>
            <div className="space-y-2">
              <form onSubmit={handleAddPeer} className="flex items-center gap-2">
                <input
                  type="text"
                  value={peerInput}
                  onChange={(event) => setPeerInput(event.target.value)}
                  placeholder="티커 또는 법인코드"
                  className="flex-1 rounded-lg border border-border-light bg-background-cardLight px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
                />
                <button
                  type="submit"
                  disabled={isAddingPeer}
                  className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white transition hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isAddingPeer ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  추가
                </button>
              </form>
              {showPeerSuggestions ? (
                <div className="max-h-56 overflow-y-auto rounded-xl border border-border-light/80 bg-background-cardLight dark:border-border-dark/70 dark:bg-background-cardDark">
                  {isSearchingPeers ? (
                    <div className="px-3 py-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">검색 중...</div>
                  ) : peerSearchResults.length ? (
                    <ul className="divide-y divide-border-light/60 text-sm dark:divide-border-dark/60">
                      {peerSearchResults.map((result) => {
                        const suggestionKey = `${result.corpCode ?? ""}-${result.ticker ?? ""}-${result.corpName ?? ""}`;
                        return (
                          <li key={suggestionKey}>
                          <button
                            type="button"
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => handlePeerSuggestionSelect(result)}
                            className="flex w-full flex-col gap-1 px-3 py-2 text-left hover:bg-primary/10"
                          >
                            <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                              {result.corpName ?? result.ticker ?? "기업"}
                            </span>
                            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                              {result.ticker ? `티커 ${result.ticker}` : null}
                              {result.ticker && result.corpCode ? " · " : null}
                              {result.corpCode ? `법인코드 ${result.corpCode}` : null}
                            </span>
                            {result.latestReportName ? (
                              <span className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                                {result.latestReportName}
                              </span>
                            ) : null}
                          </button>
                        </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <div className="px-3 py-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">검색 결과가 없습니다.</div>
                  )}
                </div>
              ) : null}
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                <span>{corpName ?? "기준"}</span>
                <span>{formatValue(baseLatestValue?.value, baseLatestValue?.unit)}</span>
              </div>
              {peerComparisons.length ? (
                <ul className="space-y-2">
                  {peerComparisons.map((peer) => (
                    <li
                      key={peer.identifier}
                      className="flex items-center justify-between rounded-lg border border-border-light/70 px-3 py-2 text-sm dark:border-border-dark/60"
                    >
                      <div className="flex flex-col">
                        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                          {peer.label}
                        </span>
                        {peer.latest ? (
                          <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                            {buildFriendlyPeriodLabel(peer.latest)}
                          </span>
                        ) : (
                          <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                            데이터 없음
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                          {peer.latest ? formatValue(peer.latest.value, peer.latest.unit) : "—"}
                        </span>
                        <button
                          type="button"
                          onClick={() => removePeer(peer.identifier)}
                          className="rounded-full border border-border-light/60 p-1 text-text-secondaryLight transition hover:bg-border-light/40 dark:border-border-dark/60 dark:hover:bg-border-dark/40"
                          aria-label={`${peer.label} 제거`}
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                  비교할 기업을 추가하면 최근 값이 여기에 표시됩니다.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

const buildFriendlyPeriodLabel = (value: FinancialValue) => {
  const year = value.fiscalYear ? `${value.fiscalYear}` : "";
  if (value.periodType === "annual") {
    if (value.periodEndDate) {
      const date = new Date(value.periodEndDate);
      if (!Number.isNaN(date.getTime())) {
        return `${date.getFullYear()}년 ${date.getMonth() + 1}월`;
      }
    }
    return year ? `${year} FY` : "연도 미상";
  }
  if (value.periodType === "quarter") {
    return `${year} ${value.fiscalPeriod ?? "분기"}`;
  }
  return value.fiscalPeriod ?? "기타";
};
