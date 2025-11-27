"use client";

import { useMemo, useState, useEffect } from "react";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Sparkles, ArrowRight, Activity, MessageCircle, Search, Plus } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { AppShell } from "@/components/layout/AppShell";

import { ProactiveBriefingsWidget, type FeedItem } from "@/components/feed/ProactiveBriefingsWidget";
import { useFilings, useFilingDetail } from "@/hooks/useFilings";
import { FilingsTable } from "@/components/filings/FilingsTable";
import { FilingDetailPanel } from "@/components/filings/FilingDetailPanel";
import { formatDateTime } from "@/lib/date";
import { useCompanySearch } from "@/hooks/useCompanySearch";
import { resolveApiBase } from "@/lib/apiBase";
import { fetchWithAuth } from "@/lib/fetchWithAuth";

type FilingCardProps = {
  id: string;
  company: string;
  title: string;
  type: string;
  filedAt: string;
  sentiment: "positive" | "neutral" | "negative";
};

function sentimentTone(sentiment: FilingCardProps["sentiment"]) {
  if (sentiment === "positive") return "text-emerald-300 bg-emerald-500/10 border-emerald-400/20";
  if (sentiment === "negative") return "text-rose-300 bg-rose-500/10 border-rose-400/20";
  return "text-slate-300 bg-white/5 border-white/10";
}

function FilingCard({ filing, onChat }: { filing: FilingCardProps; onChat: () => void }) {
  const formattedDate = useMemo(() => formatDateTime(filing.filedAt, { fallback: "-" }), [filing.filedAt]);
  return (
    <Card variant="glass" padding="md" className="rounded-2xl transition hover:border-white/20 hover:-translate-y-0.5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-white">{filing.company}</p>
          <p className="text-xs text-slate-400">{filing.type}</p>
        </div>
        <span className="rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-300 border-white/10 bg-white/5">
          {formattedDate}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-200 line-clamp-2">{filing.title}</p>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${sentimentTone(filing.sentiment)}`}>
          {filing.sentiment === "positive" ? "긍정" : filing.sentiment === "negative" ? "부정" : "중립"}
        </span>
        <button
          type="button"
          onClick={onChat}
          className="inline-flex items-center gap-1.5 rounded-full border border-blue-400/40 px-3 py-1.5 text-xs font-semibold text-blue-100 transition hover:border-blue-300 hover:text-white"
        >
          이 내용으로 질문하기 <MessageCircle className="h-4 w-4" />
        </button>
      </div>
    </Card>
  );
}

function InsightHubContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [quickQuestion, setQuickQuestion] = useState("");
  const [miniMessages, setMiniMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [contextIds, setContextIds] = useState<Record<string, string>>({});
  const [miniLoading, setMiniLoading] = useState(false);
  const [selectedFilingId, setSelectedFilingId] = useState<string | undefined>(undefined);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [companyQuery, setCompanyQuery] = useState("");

  // Auto-fill from URL params (from chat commands)
  useEffect(() => {
    const company = searchParams?.get('company');
    const start = searchParams?.get('startDate');
    const end = searchParams?.get('endDate');

    if (company) setCompanyQuery(company);
    if (start) setStartDate(start);
    if (end) setEndDate(end);
  }, [searchParams]);

  const { data, isLoading } = useFilings({
    limit: 50,
    ticker: companyQuery || undefined,
    startDate: startDate || undefined,
    endDate: endDate || undefined,
    days: (!startDate && !endDate) ? 3 : undefined
  });
  const { data: selectedFilingDetail } = useFilingDetail(selectedFilingId);
  const { data: searchResults } = useCompanySearch(query, 6);

  const filings = useMemo<FilingCardProps[]>(() => {
    const items = data ?? [];
    return items.map((item) => ({
      id: item.id,
      company: item.company,
      title: item.title,
      type: item.type,
      filedAt: item.filedAt,
      sentiment: item.sentiment,
    }));
  }, [data]);

  const handleSearch = () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    router.push(`/dashboard?query=${encodeURIComponent(trimmed)}`);
    setShowSuggestions(false);
  };

  const handleQuickAsk = (prompt: string, context?: string, turns?: Array<{ role: "user" | "assistant"; content: string }>) => {
    if (!prompt.trim()) return;
    const payload = {
      prompt: prompt.trim(),
      context: context ?? (query.trim() || null),
      turns,
      contextIds,
    };
    sessionStorage.setItem("miniChatImport", JSON.stringify(payload));
    router.push("/dashboard?importMini=1");
  };

  const handleSelectFiling = (filing: FilingCardProps) => {
    const label = filing.company || "";
    setQuery(label);
    const nextContext: Record<string, string> = { filing_id: filing.id };
    if (label) {
      nextContext.company_id = label;
    }
    setContextIds(nextContext);
    setShowSuggestions(false);
    router.push(`/dashboard?filingId=${filing.id}`);
  };

  const handleSelectEvent = (id: string, item?: FeedItem) => {
    const label = item?.ticker || query.trim();
    const nextContext: Record<string, string> = { ...contextIds, event_id: id };
    if (label) {
      nextContext.company_id = label;
      setQuery(label);
    }
    setContextIds(nextContext);
    setShowSuggestions(false);
    if (item?.title && !quickQuestion.trim()) {
      setQuickQuestion(item.title);
    }
  };

  const handleMiniSend = async () => {
    const trimmed = quickQuestion.trim();
    if (!trimmed) return;
    const contextLabel = query.trim();
    const ctxIds: Record<string, string> = { ...contextIds };
    if (contextLabel && !ctxIds.company_id) {
      ctxIds.company_id = contextLabel;
    }
    setContextIds(ctxIds);
    setMiniLoading(true);
    const userTurn = { role: "user" as const, content: trimmed };
    let assistantTurn: { role: "assistant"; content: string } = {
      role: "assistant",
      content: "답변을 준비하고 있어요...",
    };
    setMiniMessages((prev) => [...prev, userTurn, assistantTurn]);

    const updateAssistant = (content: string) => {
      assistantTurn = { role: "assistant", content };
      setMiniMessages((prev) => {
        const withoutLast = prev.slice(0, -1);
        return [...withoutLast, assistantTurn];
      });
    };

    try {
      const baseUrl = resolveApiBase();
      const body: Record<string, unknown> = {
        question: trimmed,
        top_k: 4,
        max_filings: 3,
        run_self_check: false,
        meta: { context_ids: ctxIds },
      };
      if (ctxIds.company_id) {
        body.filters = { ticker: ctxIds.company_id };
      }
      if (ctxIds.filing_id) {
        body.filing_id = ctxIds.filing_id;
      }
      const res = await fetchWithAuth(`${baseUrl}/api/v1/rag/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(`RAG ${res.status}`);
      }
      const reader = res.body?.getReader();
      if (!reader) {
        throw new Error("no_stream");
      }
      const decoder = new TextDecoder();
      let buffer = "";
      let answer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          const trimmedLine = line.trim();
          if (!trimmedLine) continue;
          try {
            const event = JSON.parse(trimmedLine);
            if (event.event === "chunk" && typeof event.delta === "string") {
              answer += event.delta;
              updateAssistant(answer || "답변을 준비하고 있어요...");
            } else if (event.event === "done") {
              const payload = event.payload;
              if (payload && typeof payload.answer === "string" && payload.answer.trim()) {
                answer = payload.answer.trim();
              }
            } else if (event.event === "error") {
              throw new Error(event.message || "stream_error");
            }
          } catch {
            // ignore malformed chunk
          }
        }
      }
      const finalAnswer =
        answer.trim() ||
        (contextLabel
          ? `"${contextLabel}" 컨텍스트로 메인 채팅에서 이어가며 더 자세히 답변해 드릴게요.`
          : "메인 채팅에서 이어가며 더 자세히 답변해 드릴게요.");
      assistantTurn = { role: "assistant", content: finalAnswer };
    } catch (error) {
      console.warn("Mini chat LLM call failed:", error);
      assistantTurn = {
        role: "assistant",
        content:
          contextLabel.length > 0
            ? `지금은 간단히 안내만 드립니다. "${contextLabel}" 컨텍스트로 메인 채팅에서 이어가며 답변해 드릴게요.`
            : "지금은 간단히 안내만 드립니다. 메인 채팅에서 이어서 질문해 주세요.",
      };
    } finally {
      setMiniMessages((prev) => {
        const withoutLast = prev.slice(0, -1);
        return [...withoutLast, assistantTurn];
      });
      // store for import
      handleQuickAsk(trimmed, contextLabel || undefined, [userTurn, assistantTurn]);
      setQuickQuestion("");
      setMiniLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="min-h-screen bg-canvas text-text-primary">
        <div className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-12">
          <header className="space-y-6 text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-blue-200">
              <Sparkles className="h-4 w-4" /> Insight Hub
            </div>
            <div className="space-y-3">
              <h1 className="text-3xl font-bold md:text-4xl">오늘 시장의 핵심 흐름을 한눈에</h1>
              <p className="text-slate-300 text-sm md:text-base">
                최신 공시, 이벤트, 맞춤 브리핑을 확인하고 바로 질문하세요.
              </p>
            </div>
            <div className="relative mx-auto flex max-w-3xl flex-col gap-3">
              <div className="flex flex-col gap-2 rounded-2xl border border-white/10 bg-white/5 p-3 text-left text-slate-200 shadow-lg md:flex-row md:items-center md:gap-3">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleSearch();
                    }
                  }}
                  onFocus={() => setShowSuggestions(true)}
                  onBlur={() => {
                    setTimeout(() => setShowSuggestions(false), 120);
                  }}
                  placeholder="기업명 또는 티커를 입력하세요 (예: 삼성전자, 005930)"
                  className="flex-1 rounded-xl bg-black/30 px-4 py-3 text-sm outline-none placeholder:text-slate-500"
                />
                <button
                  type="button"
                  onClick={handleSearch}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-400"
                >
                  질문 시작 <ArrowRight className="h-4 w-4" />
                </button>
              </div>
              {showSuggestions && query.trim().length >= 1 ? (
                <div className="absolute top-full z-20 mt-1 w-full overflow-hidden rounded-2xl border border-border-subtle bg-surface-1 shadow-2xl">
                  {searchResults?.length ? (
                    <ul className="divide-y divide-white/5">
                      {searchResults.map((item, idx) => (
                        <li key={`${item.ticker}-${idx}`}>
                          <button
                            type="button"
                            className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-slate-200 hover:bg-white/5"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => {
                              const label = item.ticker || item.corpName || "";
                              setQuery(label);
                              router.push(`/dashboard?query=${encodeURIComponent(label)}`);
                              setShowSuggestions(false);
                            }}
                          >
                            <Search className="h-4 w-4 text-slate-400" />
                            <div className="min-w-0">
                              <p className="truncate font-semibold text-white">
                                {item.corpName ?? "이름 없음"}
                              </p>
                              <p className="text-xs text-slate-400">
                                {item.ticker ? `티커 ${item.ticker}` : "티커 정보 없음"}
                                {item.latestReportName ? ` · ${item.latestReportName}` : ""}
                              </p>
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="px-4 py-3 text-sm text-slate-400">검색 결과가 없습니다.</div>
                  )}
                </div>
              ) : null}
              <p className="text-xs text-slate-500">검색하면 해당 기업 컨텍스트로 채팅이 열립니다.</p>
              <div className="flex flex-col gap-2 rounded-2xl border border-dashed border-white/10 bg-white/5 p-3 text-left text-slate-200 shadow-lg">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-white">짧은 질문 바로 보내기</p>
                    <p className="text-xs text-slate-400">현재 입력한 기업명을 컨텍스트로 메인 채팅에서 답변을 받습니다.</p>
                  </div>
                  <button
                    type="button"
                    onClick={handleMiniSend}
                    className="inline-flex items-center gap-2 rounded-full bg-blue-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-400"
                  >
                    메인 채팅으로 보내기 <Plus className="h-4 w-4" />
                  </button>
                </div>
                <textarea
                  value={quickQuestion}
                  onChange={(e) => setQuickQuestion(e.target.value)}
                  rows={2}
                  placeholder="예: 이번 공시에서 희석이 얼마나 될까?"
                  className="w-full rounded-xl bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-slate-500"
                />
                <div className="max-h-60 space-y-2 overflow-y-auto">
                  {miniMessages.map((msg, idx) => (
                    <div
                      key={`${msg.role}-${idx}`}
                      className={`rounded-2xl border px-3 py-2 text-sm ${msg.role === "user"
                        ? "border-blue-400/30 bg-blue-500/10 text-blue-50"
                        : "border-white/10 bg-white/5 text-slate-200"
                        }`}
                    >
                      {msg.content}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </header>

          <div className="grid gap-8 lg:grid-cols-[1.6fr_1fr]">
            <div className="space-y-6">
              <Card variant="glass" padding="md" className="rounded-3xl shadow-xl">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-400">오늘의 AI 브리핑</p>
                    <h2 className="text-lg font-semibold text-white">맞춤 인사이트</h2>
                  </div>
                </div>
                <div className="mt-4">
                  <ProactiveBriefingsWidget onSelectItem={handleSelectEvent} />
                </div>
              </Card>
              <Card variant="glass" padding="md" className="rounded-3xl shadow-xl">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Activity className="h-5 w-5 text-emerald-300" />
                    <div>
                      <p className="text-xs uppercase tracking-[0.3em] text-slate-400">핵심 공시</p>
                      <h2 className="text-lg font-semibold text-white">최근 주목할 만한 공시</h2>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={companyQuery}
                      onChange={(e) => setCompanyQuery(e.target.value)}
                      className="rounded-lg border border-white/10 bg-black/30 px-3 py-1 text-xs text-white outline-none focus:border-blue-400 w-32"
                      placeholder="기업명/티커"
                    />
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-xs text-white outline-none focus:border-blue-400"
                      placeholder="시작일"
                    />
                    <span className="text-xs text-slate-400">~</span>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-xs text-white outline-none focus:border-blue-400"
                      placeholder="종료일"
                    />
                    {(startDate || endDate || companyQuery) && (
                      <button
                        onClick={() => { setStartDate(""); setEndDate(""); setCompanyQuery(""); }}
                        className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-300 hover:bg-white/10"
                      >
                        초기화
                      </button>
                    )}
                  </div>
                </div>
                <div className="mt-4">
                  {isLoading ? (
                    <div className="space-y-3">
                      {Array.from({ length: 3 }).map((_, idx) => (
                        <div key={idx} className="h-24 rounded-2xl bg-white/5 animate-pulse" />
                      ))}
                    </div>
                  ) : data && data.length > 0 ? (
                    <>
                      <FilingsTable filings={data} selectedId={selectedFilingId} onSelect={setSelectedFilingId} />
                      {selectedFilingId && selectedFilingDetail && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setSelectedFilingId(undefined)}>
                          <div className="w-full max-w-2xl mx-4" onClick={(e) => e.stopPropagation()}>
                            <FilingDetailPanel filing={selectedFilingDetail} />
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-sm text-slate-300">표시할 공시가 없습니다.</p>
                  )}
                </div>
              </Card>
            </div>
            <div className="space-y-6">
              <Card variant="glass" padding="md" className="rounded-3xl shadow-xl">
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-[0.3em] text-slate-400">추천 액션</p>
                  <h2 className="text-lg font-semibold text-white">지금 바로 질문해 보세요</h2>
                  <p className="text-sm text-slate-300">
                    브리핑이나 공시를 선택해 채팅을 시작하면, 선택한 컨텍스트로 바로 이어집니다.
                  </p>
                  <div className="flex flex-wrap gap-2 text-xs text-slate-300">
                    <span className="rounded-full bg-white/5 px-3 py-1">#오늘의이슈</span>
                    <span className="rounded-full bg-white/5 px-3 py-1">#주목공시</span>
                    <span className="rounded-full bg-white/5 px-3 py-1">#이벤트임팩트</span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export default function InsightHubPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-canvas" />}>
      <InsightHubContent />
    </Suspense>
  );
}
