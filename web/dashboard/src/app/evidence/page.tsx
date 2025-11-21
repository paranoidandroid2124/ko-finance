"use client";
export const dynamic = "force-dynamic";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { EvidenceWorkspace } from "@/components/evidence";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { ErrorState } from "@/components/ui/ErrorState";
import { useEvidenceWorkspace } from "@/hooks/useEvidenceWorkspace";
import { usePlanTier } from "@/store/planStore";
import { usePlanUpgrade } from "@/hooks/usePlanUpgrade";

export default function EvidenceWorkspacePage() {
  return (
    <Suspense fallback={<SkeletonBlock lines={8} />}>
      <EvidenceWorkspaceContent />
    </Suspense>
  );
}

function EvidenceWorkspaceContent() {
  const searchParams = useSearchParams();
  const traceId = searchParams?.get("traceId");
  const filingId = searchParams?.get("filingId");
  const urnId = searchParams?.get("urnId");
  const planTier = usePlanTier();
  const { requestUpgrade } = usePlanUpgrade();
  const { data, isLoading, isError, error } = useEvidenceWorkspace(traceId, urnId, filingId);

  const status: "loading" | "ready" | "empty" | "anchor-mismatch" =
    isLoading ? "loading" : data && data.evidence.length === 0 ? "empty" : "ready";

  return (
    <AppShell>
      <div className="space-y-6">
        <header className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary/70">Evidence Workspace</p>
          <h1 className="text-2xl font-bold text-text-primaryLight dark:text-text-primaryDark">증거 스냅샷 뷰어</h1>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            RAG 답변에 사용된 증거를 PDF·표 기반으로 재검증하는 화면입니다. traceId 또는 filingId 파라미터로 원하는
            세션을 열 수 있어요.
          </p>
        </header>

        {isLoading ? (
          <SkeletonBlock lines={8} />
        ) : isError ? (
          <ErrorState title="Evidence를 불러오지 못했습니다" description={error?.message ?? "잠시 후 다시 시도해 주세요."} />
        ) : data ? (
          <EvidenceWorkspace
            planTier={planTier}
            evidence={data.evidence}
            pdfUrl={data.pdfUrl}
            pdfDownloadUrl={data.pdfDownloadUrl}
            evidenceStatus={status}
            diffEnabled={data.diffEnabled}
            diffRemoved={data.removed}
            onRequestUpgrade={requestUpgrade}
            selectedUrnId={data.selectedUrnId ?? urnId ?? undefined}
          />
        ) : (
          <ErrorState
            title="traceId 또는 filingId가 필요합니다"
            description="주소창에 traceId나 filingId 파라미터를 추가해 주세요."
          />
        )}
      </div>
    </AppShell>
  );
}
