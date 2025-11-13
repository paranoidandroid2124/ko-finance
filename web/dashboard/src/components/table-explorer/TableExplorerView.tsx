"use client";

import clsx from "clsx";
import { Download, FileText, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PlanLock } from "@/components/ui/PlanLock";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import {
  useTableExplorerList,
  useTableExplorerDetail,
  type TableListFilters,
} from "@/hooks/useTableExplorer";
import { buildTableExportUrl, type TableSummary } from "@/lib/tableExplorerApi";
import { isTierAtLeast, usePlanStore, usePlanTier } from "@/store/planStore";

const TABLE_TYPE_LABEL: Record<string, string> = {
  dividend: "배당",
  treasury: "자사주/자금",
  cb_bw: "CB/BW",
  financials: "핵심 재무",
};

const TABLE_TYPE_OPTIONS = [
  { value: "", label: "전체 유형" },
  { value: "dividend", label: TABLE_TYPE_LABEL.dividend },
  { value: "treasury", label: TABLE_TYPE_LABEL.treasury },
  { value: "cb_bw", label: TABLE_TYPE_LABEL.cb_bw },
  { value: "financials", label: TABLE_TYPE_LABEL.financials },
];

const formatPercent = (value?: number | null) =>
  typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "—";

const formatDateTime = (value?: string | null) =>
  value ? new Date(value).toLocaleString("ko-KR") : "—";

type FilterFormState = {
  tableType: string;
  receiptNo: string;
  ticker: string;
  corpCode: string;
};

const DEFAULT_FILTERS: TableListFilters = { limit: 20, offset: 0 };

export function TableExplorerView() {
  const [filters, setFilters] = useState<TableListFilters>(DEFAULT_FILTERS);
  const [formState, setFormState] = useState<FilterFormState>({
    tableType: "",
    receiptNo: "",
    ticker: "",
    corpCode: "",
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const {
    data: tableList,
    isLoading: listLoading,
    isError: listError,
    refetch: refetchList,
  } = useTableExplorerList(filters);

  useEffect(() => {
    if (!tableList?.items?.length) {
      setSelectedId(null);
      return;
    }
    if (selectedId && tableList.items.some((item) => item.id === selectedId)) {
      return;
    }
    setSelectedId(tableList.items[0]?.id ?? null);
  }, [tableList?.items, selectedId]);

  const { initialized: planInitialized, loading: planLoading } = usePlanStore((state) => ({
    initialized: state.initialized,
    loading: state.loading,
  }));
  const planTier = usePlanTier();
  const planReady = planInitialized && !planLoading;
  const canViewDetail = planReady && isTierAtLeast(planTier, "pro");

  const {
    data: tableDetail,
    isLoading: detailLoading,
    isError: detailError,
  } = useTableExplorerDetail(selectedId, canViewDetail);

  const selectedSummary: TableSummary | undefined = useMemo(
    () => tableList?.items?.find((item) => item.id === selectedId),
    [selectedId, tableList?.items],
  );

  const handleFilterSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFilters({
      limit: 20,
      offset: 0,
      tableType: formState.tableType || undefined,
      receiptNo: formState.receiptNo.trim() || undefined,
      ticker: formState.ticker.trim() || undefined,
      corpCode: formState.corpCode.trim() || undefined,
    });
  };

  const handleResetFilters = () => {
    setFormState({ tableType: "", receiptNo: "", ticker: "", corpCode: "" });
    setFilters(DEFAULT_FILTERS);
  };

  const handleDownload = (format: "csv" | "json") => {
    if (!selectedId) {
      return;
    }
    const url = buildTableExportUrl(selectedId, format);
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const renderQualityPill = (label: string, value?: number | null) => (
    <div
      key={label}
      className="rounded-lg border border-border-light/70 bg-background-cardLight px-3 py-2 text-xs dark:border-border-dark/70 dark:bg-background-cardDark"
    >
      <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">{label}</p>
      <p className="mt-1 font-semibold text-text-primaryLight dark:text-text-primaryDark">{formatPercent(value)}</p>
    </div>
  );

  return (
    <AppShell>
      <div className="space-y-6">
        <header className="flex flex-col gap-2">
          <h1 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
            Table Explorer (Prototype)
          </h1>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            공시 PDF에서 추출된 표를 확인하고 CSV/JSON으로 내려받는 실험용 화면입니다. Pro 이상 요금제에서 세부 내용을 열람할 수
            있습니다.
          </p>
        </header>

        <form
          onSubmit={handleFilterSubmit}
          className="rounded-xl border border-border-light/70 bg-background-cardLight/60 p-4 shadow-card dark:border-border-dark/70 dark:bg-background-cardDark/60"
        >
          <div className="grid gap-3 md:grid-cols-5">
            <label className="flex flex-col text-xs font-medium text-text-tertiaryLight dark:text-text-tertiaryDark">
              표 유형
              <select
                className="mt-1 rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight focus:outline-none focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
                value={formState.tableType}
                onChange={(event) => setFormState((prev) => ({ ...prev, tableType: event.target.value }))}
              >
                {TABLE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col text-xs font-medium text-text-tertiaryLight dark:text-text-tertiaryDark">
              접수번호
              <input
                type="text"
                placeholder="2025..."
                value={formState.receiptNo}
                onChange={(event) => setFormState((prev) => ({ ...prev, receiptNo: event.target.value }))}
                className="mt-1 rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight focus:outline-none focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
              />
            </label>
            <label className="flex flex-col text-xs font-medium text-text-tertiaryLight dark:text-text-tertiaryDark">
              티커
              <input
                type="text"
                placeholder="005930"
                value={formState.ticker}
                onChange={(event) => setFormState((prev) => ({ ...prev, ticker: event.target.value }))}
                className="mt-1 rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight focus:outline-none focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
              />
            </label>
            <label className="flex flex-col text-xs font-medium text-text-tertiaryLight dark:text-text-tertiaryDark">
              법인코드
              <input
                type="text"
                placeholder="00123456"
                value={formState.corpCode}
                onChange={(event) => setFormState((prev) => ({ ...prev, corpCode: event.target.value }))}
                className="mt-1 rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight focus:outline-none focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
              />
            </label>
            <div className="flex items-end gap-2">
              <button
                type="submit"
                className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                <Search className="h-4 w-4" />
                검색
              </button>
              <button
                type="button"
                onClick={handleResetFilters}
                className="inline-flex items-center justify-center rounded-lg border border-border-light px-3 py-2 text-sm font-medium text-text-secondaryLight transition hover:bg-border-light/30 dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/30"
              >
                초기화
              </button>
            </div>
          </div>
        </form>

        <div className="flex flex-col gap-4 lg:flex-row">
          <section className="lg:w-5/12">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-text-secondaryLight dark:text-text-secondaryDark">추출된 표</h2>
              <button
                type="button"
                onClick={() => refetchList()}
                className="inline-flex items-center gap-1 rounded-lg border border-border-light px-2 py-1 text-xs font-medium text-text-secondaryLight transition hover:bg-border-light/30 dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/30"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                새로고침
              </button>
            </div>

            <div className="rounded-2xl border border-border-light/80 bg-background-cardLight shadow-card dark:border-border-dark/70 dark:bg-background-cardDark">
              {listLoading ? (
                <SkeletonBlock lines={6} />
              ) : listError ? (
                <ErrorState
                  title="표 목록을 불러오지 못했어요"
                  description="네트워크 상태를 확인하고 다시 시도해 주세요."
                  className="p-6"
                />
              ) : !tableList?.items?.length ? (
                <EmptyState
                  title="표 데이터가 없습니다"
                  description="필터를 조정하거나 다른 접수번호를 입력해 보세요."
                  className="p-6"
                />
              ) : (
                <ul className="divide-y divide-border-light/70 dark:divide-border-dark/70">
                  {tableList.items.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(item.id)}
                        className={clsx(
                          "w-full p-4 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                          selectedId === item.id
                            ? "bg-primary/5 dark:bg-primary/15"
                            : "hover:bg-border-light/40 dark:hover:bg-border-dark/30",
                        )}
                      >
                        <div className="flex items-center justify-between text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                          <span>{item.tableType in TABLE_TYPE_LABEL ? TABLE_TYPE_LABEL[item.tableType] : item.tableType}</span>
                          <span>{formatDateTime(item.createdAt)}</span>
                        </div>
                        <p className="mt-1 text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                          {item.tableTitle || "제목 없음"}
                        </p>
                        <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                          {item.corpName || "법인 미지정"} · {item.ticker || "티커 미지정"}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                          <span>접수번호 {item.receiptNo || "—"}</span>
                          <span>
                            페이지 {item.pageNumber ?? "?"} · 행 {item.rowCount} × 열 {item.columnCount}
                          </span>
                          <span>Confidence {formatPercent(item.confidence)}</span>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="flex-1 rounded-2xl border border-border-light/80 bg-background-cardLight p-4 shadow-card dark:border-border-dark/70 dark:bg-background-cardDark">
            <header className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                  상세 보기
                </p>
                <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  Pro 이상 플랜에서 표의 세부 셀과 CSV/JSON을 확인할 수 있습니다.
                </p>
              </div>
              {canViewDetail && selectedId ? (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleDownload("csv")}
                    className="inline-flex items-center gap-1 rounded-lg border border-border-light px-3 py-1.5 text-xs font-medium text-text-secondaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/30"
                  >
                    <Download className="h-3.5 w-3.5" />
                    CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownload("json")}
                    className="inline-flex items-center gap-1 rounded-lg border border-border-light px-3 py-1.5 text-xs font-medium text-text-secondaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/30"
                  >
                    <FileText className="h-3.5 w-3.5" />
                    JSON
                  </button>
                </div>
              ) : null}
            </header>

            {!planReady ? (
              <SkeletonBlock lines={8} />
            ) : !canViewDetail ? (
              <PlanLock
                requiredTier="pro"
                title="Pro 이상 요금제에서만 이용할 수 있어요"
                description="정규화된 표, CSV·JSON 다운로드, 셀 미리보기 기능은 Pro · Enterprise 고객에게 제공됩니다."
              />
            ) : detailLoading ? (
              <SkeletonBlock lines={10} />
            ) : detailError ? (
              <ErrorState
                title="세부 정보를 불러오지 못했어요"
                description="선택한 표를 다시 시도하거나 다른 표를 선택해 주세요."
              />
            ) : !tableDetail || !selectedSummary ? (
              <EmptyState
                title="표를 선택해 주세요"
                description="왼쪽 목록에서 확인할 표를 클릭하면 세부 정보가 표시됩니다."
              />
            ) : (
              <div className="space-y-4">
                <div className="grid gap-3 text-sm md:grid-cols-2">
                  <div>
                    <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">법인명</p>
                    <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {selectedSummary.corpName || "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">티커 / 법인코드</p>
                    <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {selectedSummary.ticker || "—"} · {selectedSummary.corpCode || "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">접수번호</p>
                    <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {selectedSummary.receiptNo || "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">추출 시각</p>
                    <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {formatDateTime(selectedSummary.updatedAt)}
                    </p>
                  </div>
                </div>

                <div className="grid gap-3 text-xs md:grid-cols-4">
                  {renderQualityPill("헤더 커버리지", tableDetail.quality?.headerCoverage)}
                  {renderQualityPill("빈 셀 비율", tableDetail.quality?.nonEmptyRatio)}
                  {renderQualityPill("숫자 비율", tableDetail.quality?.numericRatio)}
                  {renderQualityPill("정확도 점수", tableDetail.quality?.accuracyScore)}
                </div>

                <div className="overflow-auto rounded-xl border border-border-light/80 dark:border-border-dark/80">
                  <table className="min-w-full border-collapse text-sm">
                    <thead className="bg-border-light/40 dark:bg-border-dark/40">
                      {(tableDetail.tableJson?.headerRows ?? []).map((row, rowIndex) => (
                        <tr key={`header-${rowIndex}`}>
                          {row.map((cell, cellIndex) => (
                            <th
                              key={`header-${rowIndex}-${cellIndex}`}
                              className="border border-border-light px-3 py-1 text-left text-xs font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
                            >
                              {cell || "—"}
                            </th>
                          ))}
                        </tr>
                      ))}
                      {tableDetail.tableJson?.headerRows?.length
                        ? null
                        : tableDetail.columnHeaders?.length
                          ? (
                              <tr>
                                {tableDetail.columnHeaders.map((col, idx) => (
                                  <th
                                    key={`column-${idx}`}
                                    className="border border-border-light px-3 py-1 text-left text-xs font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
                                  >
                                    {col.filter(Boolean).join(" / ") || `열 ${idx + 1}`}
                                  </th>
                                ))}
                              </tr>
                            )
                          : null}
                    </thead>
                    <tbody>
                      {(tableDetail.tableJson?.bodyRows ?? []).slice(0, 40).map((row, rowIndex) => (
                        <tr key={`body-${rowIndex}`} className="odd:bg-white even:bg-border-light/20 dark:odd:bg-background-dark">
                          {row.map((cell, cellIndex) => (
                            <td
                              key={`cell-${rowIndex}-${cellIndex}`}
                              className="border border-border-light px-3 py-1 text-xs text-text-primaryLight dark:border-border-dark dark:text-text-primaryDark"
                            >
                              {cell || "—"}
                            </td>
                          ))}
                        </tr>
                      ))}
                      {!tableDetail.tableJson?.bodyRows?.length ? (
                        <tr>
                          <td
                            colSpan={tableDetail.columnHeaders?.length || 1}
                            className="px-4 py-6 text-center text-sm text-text-secondaryLight dark:text-text-secondaryDark"
                          >
                            본문 행이 감지되지 않았습니다.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  );
}

export default TableExplorerView;
