"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { FilingHeaderNotice } from "@/components/legal/FilingLegal";
import { ChatInputDisclaimer } from "@/components/legal/ChatLegal";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type PublicFiling = {
  id: string;
  corpName?: string | null;
  reportName?: string | null;
  category?: string | null;
  market?: string | null;
  filedAt?: string | null;
  highlight?: string | null;
  targetUrl?: string | null;
};

type PublicChatSource = {
  id: string;
  title: string;
  summary?: string | null;
  filedAt?: string | null;
  targetUrl?: string | null;
};

type PublicChatResponse = {
  answer: string;
  sources: PublicChatSource[];
  disclaimer: string;
};

export default function PublicPreviewPage() {
  const [filings, setFilings] = useState<PublicFiling[]>([]);
  const [filingError, setFilingError] = useState<string | null>(null);
  const [loadingFilings, setLoadingFilings] = useState(true);

  const [question, setQuestion] = useState("");
  const [chatResponse, setChatResponse] = useState<PublicChatResponse | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    const fetchFilings = async () => {
      setLoadingFilings(true);
      setFilingError(null);
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/public/filings?limit=6`, {
          cache: "no-store",
        });
        if (!res.ok) {
          throw new Error("공시 목록을 불러오지 못했습니다.");
        }
        const data = (await res.json()) as { filings: PublicFiling[] };
        setFilings(data.filings ?? []);
      } catch (error) {
        setFilingError(error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.");
      } finally {
        setLoadingFilings(false);
      }
    };

    void fetchFilings();
  }, []);

  const formattedAnswer = useMemo(() => {
    if (!chatResponse?.answer) return null;
    return chatResponse.answer.split("\n").map((line, index) => (
      <p key={index} className="text-sm text-slate-200">
        {line}
      </p>
    ));
  }, [chatResponse]);

  const handleChatSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      setChatError("질문을 입력해 주세요.");
      return;
    }
    setChatLoading(true);
    setChatError(null);
    setChatResponse(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/public/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      const data = await res.json();
      if (!res.ok) {
        setChatError(data?.detail?.message ?? "미리보기 대화를 처리할 수 없습니다.");
        return;
      }
      setChatResponse(data as PublicChatResponse);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "연결 중 오류가 발생했습니다.");
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 bg-slate-950/70 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-blue-300">K-Finance Preview</p>
            <h1 className="text-2xl font-semibold">즉시 체험 가능한 공시 미리보기</h1>
          </div>
          <div className="flex gap-3">
            <Link
              href="/auth/login"
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 hover:border-slate-500"
            >
              로그인
            </Link>
            <Link
              href="/auth/register"
              className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-400"
            >
              가입하기
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-10 lg:flex-row">
        <section className="flex-1 space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-black/20">
            <h2 className="text-lg font-semibold">최신 공시 스냅샷</h2>
            <p className="mt-1 text-sm text-slate-400">
              로그인 없이도 최근 공시 흐름을 살짝 확인해 보세요.
            </p>
            <FilingHeaderNotice className="mt-2 text-xs text-slate-500" />
            {loadingFilings && <p className="mt-6 text-sm text-slate-400">공시를 불러오는 중...</p>}
            {filingError && (
              <p className="mt-6 rounded-lg border border-red-500/60 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                {filingError}
              </p>
            )}
            {!loadingFilings && !filingError && (
              <ul className="mt-6 space-y-3">
                {filings.map((filing) => (
                  <li
                    key={filing.id}
                    className="rounded-xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-200"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-white">{filing.corpName ?? "공시"}</p>
                        <p className="text-slate-400">{filing.reportName ?? filing.highlight ?? "세부 정보 없음"}</p>
                      </div>
                      <span className="text-xs text-slate-500">
                        {filing.filedAt ? new Date(filing.filedAt).toLocaleDateString("ko-KR") : "날짜 정보 없음"}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
                      {filing.category ? <span className="rounded-full bg-slate-800 px-2 py-0.5">{filing.category}</span> : null}
                      {filing.market ? <span className="rounded-full bg-slate-800 px-2 py-0.5">{filing.market}</span> : null}
                      {filing.targetUrl ? (
                        <a
                          href={filing.targetUrl}
                          className="text-blue-300 hover:text-blue-200"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          대시보드에서 보기 →
                        </a>
                      ) : null}
                    </div>
                  </li>
                ))}
                {filings.length === 0 && (
                  <li className="rounded-xl border border-slate-800 bg-slate-900 px-4 py-5 text-center text-sm text-slate-400">
                    표시할 공시가 없습니다. 로그인 후 전체 데이터를 확인해 보세요.
                  </li>
                )}
              </ul>
            )}
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-800 p-6 shadow-lg shadow-black/20">
            <h3 className="text-lg font-semibold">미리보기에서 확인할 수 있는 것</h3>
            <ul className="mt-4 space-y-2 text-sm text-slate-200">
              <li>• 공시 본문이 어떻게 정리되어 보여지는지 직접 확인</li>
              <li>• 기업/업종별 질문을 던져보고 답변 흐름 체험</li>
              <li>• 맞춤 다이제스트, 워치리스트, 뉴스 시그널 등 로그인 후 제공되는 기능 안내</li>
            </ul>
            <p className="mt-4 text-xs text-slate-400">
              미리보기에서는 세션이 저장되지 않으며 데이터 범위가 제한됩니다. 가입 후에는 히스토리, 경고 알림, 워치리스트, 다이제스트 등
              모든 기능을 이용할 수 있어요.
            </p>
          </div>
        </section>

        <section className="flex-1 space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-black/20">
            <h2 className="text-lg font-semibold">공시 기반 챗 미리보기</h2>
            <p className="mt-1 text-sm text-slate-400">
              질문을 입력하면 최신 공시를 기반으로 요약 답변을 보여 드립니다. 기록은 남지 않아요.
            </p>
            <form className="mt-4 space-y-3" onSubmit={handleChatSubmit}>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="예: 최근 에너지 업종 사업보고 주요 이슈 알려줘"
                className="h-28 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
              />
              <ChatInputDisclaimer className="text-xs text-slate-500" />
              {chatError ? <p className="text-sm text-red-300">{chatError}</p> : null}
              <button
                type="submit"
                disabled={chatLoading}
                className="w-full rounded-xl bg-blue-500 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {chatLoading ? "요약 생성 중..." : "미리보기 답변 받기"}
              </button>
            </form>
            {chatResponse ? (
              <div className="mt-6 space-y-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                <div className="space-y-2">{formattedAnswer}</div>
                {chatResponse.sources.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">참고 공시</p>
                    <ul className="space-y-2">
                      {chatResponse.sources.map((source) => (
                        <li key={source.id} className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200">
                          <p className="font-semibold text-white">{source.title}</p>
                          {source.summary ? <p className="text-slate-400">{source.summary}</p> : null}
                          <div className="mt-1 flex items-center justify-between text-xs text-slate-500">
                            <span>{source.filedAt ? new Date(source.filedAt).toLocaleString("ko-KR") : "날짜 정보 없음"}</span>
                            {source.targetUrl ? (
                              <a
                                href={source.targetUrl}
                                className="text-blue-300 hover:text-blue-200"
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                이동 →
                              </a>
                            ) : null}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <p className="text-xs text-slate-500">{chatResponse.disclaimer}</p>
              </div>
            ) : null}
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 to-blue-900/40 p-6 shadow-lg shadow-black/30">
            <h3 className="text-lg font-semibold">깊이 있는 분석이 필요하신가요?</h3>
            <p className="mt-2 text-sm text-slate-200">
              로그인하면 RAG 기반 대화형 분석, 뉴스/워치리스트, 맞춤형 다이제스트까지 모두 이용할 수 있습니다.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link href="/auth/register" className="rounded-lg bg-white/90 px-4 py-2 text-sm font-semibold text-blue-900 hover:bg-white">
                무료로 시작하기
              </Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
