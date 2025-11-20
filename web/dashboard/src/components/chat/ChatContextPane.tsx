"use client";

import { useCallback, useMemo } from "react";
import { RagEvidencePanel } from "@/components/chat/RenderRagEvidence";
import { FilingXmlViewer } from "@/components/chat/FilingXmlViewer";
import { PdfHighlightMock } from "@/components/chat/PdfHighlightMock";
import { selectActiveSession, selectContextPanelData, selectHighlightDisplay, useChatStore } from "@/store/chatStore";

export function ChatContextPane() {
  const activeSession = useChatStore(selectActiveSession);
  const { evidence, guardrail, metrics } = useChatStore(selectContextPanelData);
  const highlight = useChatStore(selectHighlightDisplay);
  const focusEvidence = useChatStore((state) => state.focus_evidence_item);
  const sessionContext = activeSession?.context;

  const contextLabel = useMemo(() => {
    const type = sessionContext?.type;
    if (type === "filing") return "공시 컨텍스트";
    if (type === "news") return "뉴스 컨텍스트";
    if (type === "custom") return "사용자 컨텍스트";
    return "연결된 컨텍스트 없음";
  }, [sessionContext?.type]);

  const contextSummary = sessionContext?.summary ?? null;
  const referenceId =
    sessionContext && sessionContext.type !== "custom" ? sessionContext.referenceId ?? undefined : undefined;
  const evidenceErrorMessage =
    evidence.status === "error" && "errorMessage" in evidence ? evidence.errorMessage : undefined;

  const handleEvidenceSelect = useCallback(
    (evidenceId: string) => {
      focusEvidence(evidenceId);
    },
    [focusEvidence]
  );

  const handleOpenSource = useCallback(
    (evidenceId: string) => {
      focusEvidence(evidenceId);
      const target = evidence.items.find((item) => item.id === evidenceId);
      if (target?.sourceUrl) {
        window.open(target.sourceUrl, "_blank", "noopener,noreferrer");
      }
    },
    [evidence.items, focusEvidence]
  );

  return (
    <aside className="hidden w-[320px] flex-none flex-col gap-4 rounded-3xl border border-white/5 bg-black/20 p-4 text-sm text-slate-200 shadow-[0_25px_120px_rgba(3,7,18,0.55)] backdrop-blur-xl lg:flex">
      <section className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.3em] text-slate-500">Context</p>
            <h3 className="text-base font-semibold text-white">컨텍스트 하이라이트</h3>
          </div>
          {referenceId ? (
            <span className="rounded-full border border-white/15 px-3 py-1 text-[11px] text-slate-400">ID: {referenceId}</span>
          ) : null}
        </div>
        {contextSummary ? (
          <p className="mt-3 text-sm text-slate-300">{contextSummary}</p>
        ) : (
          <p className="mt-3 rounded-2xl border border-dashed border-white/10 px-3 py-3 text-xs text-slate-500">
            이 세션에는 아직 연결된 컨텍스트가 없습니다. 공시 상세 화면에서 “질문하기” 버튼으로 새 대화를 열어보세요.
          </p>
        )}
        <p className="mt-2 text-[11px] uppercase tracking-[0.2em] text-blue-300">{contextLabel}</p>
      </section>
      <section className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3">
        <RagEvidencePanel
          status={evidence.status}
          items={evidence.items}
          activeId={evidence.activeId}
          confidence={evidence.confidence}
          errorMessage={evidenceErrorMessage}
          guardrail={guardrail}
          metrics={metrics}
          onSelectItem={handleEvidenceSelect}
          onOpenSource={handleOpenSource}
        />
      </section>
      <section className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3">
        <PdfHighlightMock
          documentTitle={highlight.documentTitle}
          pdfUrl={highlight.documentUrl}
          highlightRanges={highlight.ranges}
          activeRangeId={highlight.activeRangeId}
          status={highlight.status}
          onFocusHighlight={focusEvidence}
        />
      </section>
      {activeSession?.context?.type === "filing" ? (
        <section className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3">
          <FilingXmlViewer
            filingId={referenceId ?? undefined}
            evidenceItems={evidence.items}
            activeEvidenceId={evidence.activeId ?? undefined}
          />
        </section>
      ) : null}
    </aside>
  );
}
