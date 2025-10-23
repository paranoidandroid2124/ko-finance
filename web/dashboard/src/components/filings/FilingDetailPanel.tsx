"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import type { FilingDetail } from "@/hooks/useFilings";
import { useChatStore } from "@/store/chatStore";

const sentimentText: Record<FilingDetail["sentiment"], { label: string; description: string }> = {
  positive: { label: "ê¸ì •ì ", description: "ê¸ì •ì ì¸ ì‹ í˜¸ê°€ ê°ì§€ë˜ì—ˆìŠµë‹ˆë‹¤." },
  neutral: { label: "ì¤‘ë¦½ì ", description: "ëšœë ·í•œ ê°ì • ë³€í™”ê°€ ê´€ì¸¡ë˜ì§€ ì•Šì•˜ìŠµë‹ˆë‹¤." },
  negative: { label: "ë¶€ì •ì ", description: "ë¶€ì •ì ì¸ ì§•í›„ê°€ ë‚˜íƒ€ë‚¬ìŠµë‹ˆë‹¤." }
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
      window.alert("ì—´ ìˆ˜ ìžˆëŠ” PDFê°€ ì—†ìŠµë‹ˆë‹¤.");
      return;
    }
    const targetUrl = filing.pdfViewerUrl ?? filing.pdfDownloadUrl;
    if (targetUrl) {
      window.open(targetUrl, "_blank", "noopener,noreferrer");
    }
  }, [filing.pdfViewerUrl, filing.pdfDownloadUrl]);

  const handleDownloadPdf = useCallback(() => {
    const targetUrl = filing.pdfDownloadUrl ?? filing.pdfViewerUrl;
    if (!targetUrl) {
      window.alert("ë‹¤ìš´ë¡œë“œ ê°€ëŠ¥í•œ PDFê°€ ì—†ìŠµë‹ˆë‹¤.");
      return;
    }
    window.open(targetUrl, "_blank", "noopener,noreferrer");
  }, [filing.pdfDownloadUrl, filing.pdfViewerUrl]);

  return (
    <aside className="flex h-full flex-col rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header>
        <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">ê¸°ë³¸ ì •ë³´</p>
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

      <section className="mt-5 space-y-4 text-sm">
        <div>
          <h3 className="text-sm font-semibold">ìš”ì•½</h3>
          <p className="mt-2 text-text-secondaryLight dark:text-text-secondaryDark">
            {filing.summary || "ìš”ì•½ì´ ì œê³µë˜ì§€ ì•Šì•˜ìŠµë‹ˆë‹¤."}
          </p>
        </div>

        <div>
          <h3 className="text-sm font-semibold">í•µì‹¬ ì‚¬ì‹¤</h3>
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
            <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">í•µì‹¬ ì‚¬ì‹¤ì´ ì—†ìŠµë‹ˆë‹¤.</p>
          )}
        </div>
      </section>

      <footer className="mt-auto">
        <div className="rounded-lg border border-dashed border-border-light p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          <p>PDF ë§í¬ë¥¼ í†µí•´ ë¬¸ì„œë¥¼ í™•ì¸í•  ìˆ˜ ìžˆìŠµë‹ˆë‹¤.</p>
          {filing.pdfDownloadUrl && (
            <p className="mt-2">
              <button onClick={handleDownloadPdf} className="text-primary underline-offset-2 hover:underline">
                PDF ë‹¤ìš´ë¡œë“œ
              </button>
            </p>
          )}
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleOpenPdf}
            disabled={!filing.pdfViewerUrl && !filing.pdfDownloadUrl}
            className="flex-1 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow transition-opacity hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            PDF ì—´ê¸°
          </button>
          <button
            onClick={handleAskClick}
            className="flex-1 rounded-lg border border-border-light px-3 py-2 text-sm font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            ì§ˆë¬¸í•˜ê¸°
          </button>
        </div>
      </footer>
    </aside>
  );
}
