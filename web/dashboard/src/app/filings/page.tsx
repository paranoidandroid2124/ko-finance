"use client";

import { AppShell } from "@/components/layout/AppShell";
import { FilingsTable } from "@/components/filings/FilingsTable";
import { FilingDetailPanel } from "@/components/filings/FilingDetailPanel";
import { useState } from "react";

const MOCK_FILINGS = [
  {
    id: "F-001",
    company: "삼성전자",
    title: "사업보고서 (2025.3분기)",
    type: "사업보고서",
    filedAt: "2025-10-19 09:31",
    sentiment: "neutral" as const,
    summary: "삼성전자가 2025년 3분기 실적을 발표했습니다. 반도체 부문의 재고 조정으로 영업이익은 감소했지만 시스템 LSI와 파운드리는 개선 흐름.",
    facts: [
      { label: "매출", value: "67조 원", anchor: "p.12" },
      { label: "영업이익", value: "2.8조 원", anchor: "p.15" }
    ],
    pdfUrl: "#"
  },
  {
    id: "F-002",
    company: "LG화학",
    title: "반기보고서 (2025.상반기)",
    type: "반기보고서",
    filedAt: "2025-10-18 16:45",
    sentiment: "positive" as const,
    summary: "전지 사업부문이 북미 전기차 수요 회복으로 호실적을 기록. 양극재 CAPEX 확대 계획 신규 공시.",
    facts: [
      { label: "배터리 매출", value: "18조 원", anchor: "p.23" },
      { label: "CAPEX", value: "4.2조 원", anchor: "p.27" }
    ],
    pdfUrl: "#"
  },
  {
    id: "F-003",
    company: "카카오",
    title: "분기보고서 (2025.3분기)",
    type: "분기보고서",
    filedAt: "2025-10-18 10:12",
    sentiment: "negative" as const,
    summary: "광고 매출 둔화 및 콘텐츠 투자 확대 영향으로 영업이익이 전년 대비 감소. 플랫폼 리스크 관련 self-check 경고 1건.",
    facts: [
      { label: "영업이익", value: "1,450억 원", anchor: "p.8" },
      { label: "MAU", value: "4,700만 명", anchor: "p.10" }
    ],
    pdfUrl: "#"
  }
];

export default function FilingsPage() {
  const [selectedId, setSelectedId] = useState<string>(MOCK_FILINGS[0].id);
  const selected = MOCK_FILINGS.find((filing) => filing.id === selectedId) ?? MOCK_FILINGS[0];

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <FilingsTable filings={MOCK_FILINGS} selectedId={selectedId} onSelect={setSelectedId} />
        <FilingDetailPanel filing={selected} />
      </div>
    </AppShell>
  );
}

