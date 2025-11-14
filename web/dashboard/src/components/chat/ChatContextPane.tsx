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
    <aside className="hidden w-80 flex-none space-y-4 rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark lg:block">
      <section>
        <h3 className="text-sm font-semibold">컨텍스트 하이라이트</h3>
        {contextSummary ? (
          <div className="mt-3 space-y-2 rounded-lg border border-border-light px-3 py-3 text-xs dark:border-border-dark">
            <p className="text-[11px] font-semibold uppercase text-primary">{contextLabel}</p>
            {referenceId && (
              <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">참조 ID: {referenceId}</p>
            )}
            <p className="leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">{contextSummary}</p>
          </div>
        ) : (
          <p className="mt-3 rounded-lg border border-dashed border-border-light px-3 py-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            이 세션에는 아직 연결된 컨텍스트가 없습니다. 공시 상세 화면에서 “질문하기” 버튼을 사용해 새 대화를 열어보세요.
          </p>
        )}
      </section>
      <section>
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
      <section>
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
        <section>
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
