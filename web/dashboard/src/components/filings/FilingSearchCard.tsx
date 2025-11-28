import React from "react";
import { FileText, Calendar, Building2, CheckCircle2, ArrowUpRight } from "lucide-react";
import { REPORT_TYPE_LABELS } from "@/constants/filings";

export interface FilingSearchParams {
    companies: string[];
    years: number[];
    start_date?: string;
    end_date?: string;
    report_types: string[];
}

export interface FilingSearchResult {
    id: string;
    title?: string | null;
    company?: string | null;
    ticker?: string | null;
    corp_code?: string | null;
    filed_at?: string | null;
    category?: string | null;
    sentiment?: string | null;
    viewer_url?: string | null;
    download_url?: string | null;
}

export interface FilingSearchCardProps {
    parsed_params: FilingSearchParams;
    results?: FilingSearchResult[];
    searchUrl?: string;
    onExecute?: (searchUrl?: string) => void;
    onEdit?: () => void;
    onOpenResult?: (result: FilingSearchResult) => void;
}

export function FilingSearchCard({ parsed_params, results, searchUrl, onExecute, onEdit, onOpenResult }: FilingSearchCardProps) {
    const { companies, years, start_date, end_date, report_types } = parsed_params;
    const hasResults = Array.isArray(results) && results.length > 0;

    return (
        <div className="rounded-2xl border border-white/20 bg-gradient-to-br from-blue-500/10 to-purple-500/10 p-5 shadow-xl backdrop-blur-sm">
            <div className="flex items-center gap-2 mb-4">
                <FileText className="h-5 w-5 text-blue-400" />
                <h3 className="text-lg font-semibold text-white">공시 검색 요청</h3>
            </div>

            <div className="space-y-3 mb-5">
                {companies && companies.length > 0 && (
                    <div className="flex items-start gap-3">
                        <Building2 className="h-4 w-4 text-emerald-400 mt-0.5" />
                        <div>
                            <p className="text-xs text-slate-400 mb-1">기업</p>
                            <div className="flex flex-wrap gap-2">
                                {companies.map((company, idx) => (
                                    <span
                                        key={idx}
                                        className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-sm font-medium text-emerald-200"
                                    >
                                        {company}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {(years.length > 0 || start_date) && (
                    <div className="flex items-start gap-3">
                        <Calendar className="h-4 w-4 text-blue-400 mt-0.5" />
                        <div>
                            <p className="text-xs text-slate-400 mb-1">기간</p>
                            {years.length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                    {years.map((year) => (
                                        <span
                                            key={year}
                                            className="rounded-full border border-blue-400/30 bg-blue-500/10 px-3 py-1 text-sm font-medium text-blue-200"
                                        >
                                            {year}년
                                        </span>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-white">
                                    {start_date} ~ {end_date}
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {report_types && report_types.length > 0 && (
                    <div className="flex items-start gap-3">
                        <CheckCircle2 className="h-4 w-4 text-purple-400 mt-0.5" />
                        <div>
                            <p className="text-xs text-slate-400 mb-1">보고서 유형</p>
                            <div className="flex flex-wrap gap-2">
                                {report_types.map((type) => (
                                    <span
                                        key={type}
                                        className="rounded-full border border-purple-400/30 bg-purple-500/10 px-3 py-1 text-sm font-medium text-purple-200"
                                    >
                                        {REPORT_TYPE_LABELS[type] || type}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">검색 결과 미리보기</p>
                    {searchUrl ? <span className="text-[11px] text-slate-400">#{results?.length ?? 0}</span> : null}
                </div>
                {hasResults ? (
                    <ul className="divide-y divide-white/10 rounded-xl border border-white/15 bg-black/20">
                        {results!.map((item) => (
                            <li key={item.id} className="px-4 py-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0 space-y-1">
                                        <p className="truncate text-sm font-semibold text-white">{item.title || "제목 없음"}</p>
                                        <p className="text-xs text-slate-300">
                                            {item.company || item.ticker || "기업 미상"} ·{" "}
                                            {item.filed_at ? new Date(item.filed_at).toLocaleDateString("ko-KR") : "날짜 없음"}
                                        </p>
                                        {item.category ? (
                                            <p className="text-[11px] text-slate-400">{item.category}</p>
                                        ) : null}
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => onOpenResult?.(item)}
                                        className="inline-flex items-center gap-1 rounded-lg border border-white/30 px-3 py-1.5 text-xs font-semibold text-white transition hover:border-white/60 hover:bg-white/10"
                                    >
                                        열기
                                        <ArrowUpRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <div className="rounded-xl border border-dashed border-white/20 bg-white/5 px-4 py-3 text-sm text-slate-300">
                        조건에 맞는 공시 미리보기가 없습니다. 필요하면 필터를 수정해 주세요.
                    </div>
                )}
            </div>

            <div className="flex items-center gap-3 pt-3 border-t border-white/10">
                <button
                    onClick={() => onExecute?.(searchUrl)}
                    className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:shadow-xl hover:scale-105"
                >
                    검색 실행
                </button>
                <button
                    onClick={() => onEdit?.()}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:bg-white/10"
                >
                    필터 수정
                </button>
            </div>

            <p className="mt-3 text-xs text-slate-400 text-center">
                검색을 실행하면 Insights Hub 페이지로 이동합니다
            </p>
        </div>
    );
}
