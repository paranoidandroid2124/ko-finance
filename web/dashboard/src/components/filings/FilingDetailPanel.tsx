"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import type { FilingDetail } from "@/hooks/useFilings";
import { useChatStore } from "@/store/chatStore";
import { FilingPdfDownloadNotice, FilingKoglBadge } from "@/components/legal/FilingLegal";

const sentimentText: Record<FilingDetail["sentiment"], { label: string; description: string }> = {
  positive: { label: "긍정적", description: "긍정적인 신호가 감지되었습니다." },
  neutral: { label: "중립적", description: "뚜렷한 감정 변화가 관측되지 않았습니다." },
  negative: { label: "부정적", description: "부정적인 징후가 나타났습니다." }
};

export function FilingDetailPanel({ filing }: { filing: FilingDetail }) {
  const sentiment = sentimentText[filing.sentiment];
  const router = useRouter();
  const startFilingConversation = useChatStore((state) => state.startFilingConversation);

  const handleAskClick = useCallback(async () => {
    if (!filing.summary?.trim()) {
      window.alert("요약 정보가 없어 질문을 시작할 수 없습니다.");
      return;
    }

    try {
      const sessionId = await startFilingConversation({
        filingId: filing.id,
        company: filing.company,
        title: filing.title,
        summary: filing.summary,
        viewerUrl: filing.pdfViewerUrl,
        downloadUrl: filing.pdfDownloadUrl
      });

      router.push(`/chat?session=${sessionId}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : '세션을 생성하지 못했습니다.';
      window.alert(message);
    }
  }, [filing, router, startFilingConversation]);
  const handleOpenPdf = useCallback(() => {
    if (!filing.pdfViewerUrl && !filing.pdfDownloadUrl) {
      window.alert("열 수 있는 PDF가 없습니다.");
      return;
    }
    const targetUrl = filing.pdfViewerUrl ?? filing.pdfDownloadUrl;
    if (targetUrl) {
      window.open(targetUrl, "_blank", "noopener,noreferrer");
    }
  }, [filing.pdfViewerUrl, filing.pdfDownloadUrl]);

  return (
    <aside className="flex h-full max-h-[calc(100vh-160px)] flex-col overflow-hidden rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header>
        <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">기본 정보</p>
        <h2 className="mt-2 text-lg font-semibold">{filing.company}</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{filing.title}</p>
        <div className="mt-3 flex items-center gap-2 text-xs">
          <span className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark">{filing.type}</span>
          <span className="text-text-secondaryLight dark:text-text-secondaryDark">{filing.filedAt}</span>
        </div>
        <div className="mt-4 rounded-lg border border-border-light bg-white/70 p-3 text-xs dark:border-border-dark dark:bg-white/5">
          <p className="font-semibold">{sentiment.label}</p>
          <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">
            {filing.sentimentReason || sentiment.description}
          </p>
        </div>
      </header>

      <section className="mt-5 flex-1 overflow-y-auto pr-1 text-sm">
        <div className="space-y-4 pb-4">
          <div>
            <h3 className="text-sm font-semibold">요약</h3>
            <p className="mt-2 text-text-secondaryLight dark:text-text-secondaryDark">
              {filing.summary || "요약이 제공되지 않았습니다."}
            </p>
          </div>

          <div>
            <h3 className="text-sm font-semibold">핵심 사실</h3>
            {filing.facts.length > 0 ? (
              <ul className="mt-2 space-y-2 text-sm">
                {filing.facts.map((fact) => (
                  <li key={`${fact.label}-${fact.value}`} className="rounded-lg border border-border-light px-3 py-2 text-xs dark:border-border-dark">
                    <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{fact.label}</p>
                    <p className="text-text-secondaryLight dark:text-text-secondaryDark">
                      {fact.value}
                      {fact.anchor && <span className="ml-2 text-[11px] text-primary">({fact.anchor})</span>}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">핵심 사실이 없습니다.</p>
            )}
          </div>
        </div>
      </section>

      <footer className="mt-auto">
        <div className="rounded-lg border border-dashed border-border-light p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          <FilingPdfDownloadNotice />
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleOpenPdf}
            disabled={!filing.pdfViewerUrl && !filing.pdfDownloadUrl}
            className="flex-1 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow transition-opacity hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            PDF 열기
          </button>
          <button
            onClick={handleAskClick}
            className="flex-1 rounded-lg border border-border-light px-3 py-2 text-sm font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover-border-primary.dark dark:hover:text-primary.dark"
          >
            질문하기
          </button>
        </div>
        <FilingKoglBadge className="mt-3 text-[11px] text-text-tertiaryLight dark:text-text-ter티aryDark" />
      </footer>
    </aside>
  );
}
