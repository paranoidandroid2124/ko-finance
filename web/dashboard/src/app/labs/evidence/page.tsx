"use client";

import { notFound } from "next/navigation";
import { useMemo } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { EvidenceWorkspace } from "@/components/evidence/EvidenceWorkspace";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { ErrorState } from "@/components/ui/ErrorState";
import { useCompanyTimeline } from "@/hooks/useCompanyTimeline";
import type { EvidencePanelItem } from "@/components/evidence";
import type { TimelineSparklinePoint } from "@/components/company/TimelineSparkline";

const SAMPLE_PDF =
  "data:application/pdf;base64,JVBERi0xLjMKJcTl8uXrp/Og0MTGCjEgMCBvYmoKPDwvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlIC9QYWdlcyAvQ291bnQgMSAvS2lkcyBbMyAwIFJdPj4KZW5kb2JqCjMgMCBvYmoKPDwvVHlwZSAvUGFnZSAvUGFyZW50IDIgMCBSIC9NZWRpYUJveCBbMCAwIDU5NSA4NDJdIC9Db250ZW50cyA0IDAgUiAvUmVzb3VyY2VzIDw8Pj4+PgplbmRvYmoKNCAwIG9iago8PC9MZW5ndGggNTY+PgpzdHJlYW0KQlQKL0YxIDI0IFRmCjEwMCA3NjAgVGQKKChIZWxsbyBQREYpIFRqCkVUCmVuZHN0cmVhbQplbmRvYmoKeHJlZgowIDUKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDExIDAwMDAwIG4gCjAwMDAwMDAwNzMgMDAwMDAgbiAKMDAwMDAwMDE1MyAwMDAwMCBuIAowMDAwMDAwMjE3IDAwMDAwIG4gCnRyYWlsZXIKPDwvUm9vdCAxIDAgUiAvU2l6ZSA1Pj4Kc3RhcnR4cmVmCjI0MAolJUVPRgo=";

const SAMPLE_EVIDENCE: EvidencePanelItem[] = [
  {
    urnId: "urn:chunk:sample-1",
    section: "중요 사실",
    quote:
      "3분기 매출은 전년 동기 대비 18% 증가했고, 해외 시장 점유율이 5%p 확대되었습니다.",
    pageNumber: 12,
    anchor: {
      paragraphId: "para-1",
      pdfRect: { page: 12, x: 120, y: 420, width: 360, height: 64 },
      similarity: 0.82,
    },
    selfCheck: { verdict: "pass", score: 0.84 },
    sourceReliability: "high",
    createdAt: "2025-11-20T04:12:45Z",
    chunkId: "chunk-120",
  },
  {
    urnId: "urn:chunk:sample-2",
    section: "리스크 요인",
    quote:
      "원자재 가격 상승으로 인해 4분기 영업이익률이 1.3%p 하락할 것으로 예상됩니다.",
    pageNumber: 19,
    anchor: {
      paragraphId: "para-2",
      pdfRect: { page: 19, x: 96, y: 380, width: 340, height: 58 },
      similarity: 0.76,
    },
    selfCheck: { verdict: "warn", score: 0.56, explanation: "비용 증가 추정치가 보수적으로 계산됨" },
    sourceReliability: "medium",
    createdAt: "2025-11-20T04:12:45Z",
    chunkId: "chunk-233",
  },
  {
    urnId: "urn:chunk:sample-locked",
    section: "PDF 주석",
    quote: "Pro 이상 요금제에서만 확인할 수 있는 하이라이트입니다.",
    pageNumber: 27,
    locked: true,
    sourceReliability: "high",
    chunkId: "chunk-310",
  },
];

const TIMELINE_DEFAULT_POINTS = [
  {
    date: "2025-11-10",
    sentimentZ: 0.42,
    priceClose: 71200,
    volume: 320000,
    eventType: "실적 발표",
    evidenceUrnIds: ["urn:chunk:sample-1"],
  },
  {
    date: "2025-11-15",
    sentimentZ: 0.21,
    priceClose: 70650,
    volume: 298000,
    eventType: "시장 브리핑",
    evidenceUrnIds: ["urn:chunk:sample-2"],
  },
  {
    date: "2025-11-20",
    sentimentZ: -0.12,
    priceClose: 69900,
    volume: 410000,
    eventType: "리스크 업데이트",
  },
] satisfies TimelineSparklinePoint[];

export default function EvidenceLabPage() {
  if (process.env.NEXT_PUBLIC_ENABLE_LABS !== "true") {
    notFound();
  }

  const ticker = "005930";
  const { data, isLoading, isError } = useCompanyTimeline(ticker, 180);

  const timelinePoints = useMemo(() => {
    if (data?.points && data.points.length > 0) {
      return data.points;
    }
    return TIMELINE_DEFAULT_POINTS;
  }, [data?.points]);

  return (
    <AppShell>
      <div className="space-y-6">
        <header className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
            Evidence Workspace Prototype
          </h1>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            EvidencePanel v2와 TimelineSparkline 연동을 확인하는 실험용 화면입니다. 샘플 데이터와 삼성전자({ticker}) 타임라인 API를 조합합니다.
          </p>
        </header>

        {isLoading ? (
          <SkeletonBlock lines={8} />
        ) : isError ? (
          <ErrorState
            title="타임라인 데이터를 불러오지 못했습니다"
            description="네트워크 상태를 확인하고 다시 시도해 주세요."
          />
        ) : (
          <EvidenceWorkspace
            planTier="pro"
            evidence={SAMPLE_EVIDENCE}
            timeline={timelinePoints}
            pdfUrl={SAMPLE_PDF}
            pdfDownloadUrl={SAMPLE_PDF}
          />
        )}
      </div>
    </AppShell>
  );
}
