import type { Metadata } from "next";

import { LegalDocumentPage, type LegalSection } from "@/app/legal/_components/LegalDocumentPage";
import { LEGAL_COMPANY, buildCompanyContactSection } from "@/app/legal/constants";

const { contact: companyContact, updatedAt } = LEGAL_COMPANY;

export const metadata: Metadata = {
  title: "데이터 & 라이선스 정책 | Nuvien",
  description: "데이터 소스, Evidence 정책, 보존 주기, 데이터 열람·삭제 절차를 안내합니다.",
};

const sections: LegalSection[] = [
  {
    id: "sources",
    title: "1. 데이터 소스와 라이선스",
    contents: [
      {
        type: "paragraph",
        text: "서비스는 OpenDART, KRX 시세·벤치마크, KISVALUE, Nuvien이 축적한 이벤트/섹터 데이터, 언론사와 협약한 뉴스 피드를 조합해 제공합니다.",
      },
      {
        type: "list",
        title: "공급자별 기본 원칙",
        items: [
          "OpenDART·공공데이터: 출처를 명시하고 원문이 항상 우선",
          "라이선스 뉴스: 제목·링크·요약 중심으로 노출하며 전문을 저장하거나 재배포하지 않음",
          "사용자 업로드 자료(Evidence Bundle, Report 첨부 등): 업로더가 저작권·제3자 권리를 보유하고 있음을 전제로 기록",
        ],
      },
    ],
  },
  {
    id: "evidence",
    title: "2. Evidence와 Guardrail 운영",
    contents: [
      {
        type: "paragraph",
        text: "모든 RAG 답변에는 Evidence Panel, 하이라이트, guardrail 텔레메트리가 함께 기록되며 Admin Console에서 금지어·금지 토픽을 수정하면 즉시 Guardrail 평가에 반영됩니다.",
      },
      {
        type: "note",
        text: "투자 권유·목표가·매수/매도 지시 문구는 기본적으로 차단되며, 허용 예외는 Team(구 Enterprise) 계약서에 명시된 범위에서만 적용합니다.",
      },
    ],
  },
  {
    id: "retention",
    title: "3. 데이터 보존 주기",
    contents: [
      {
        type: "paragraph",
        text: "아래 기간은 기본 보존/삭제 스케줄입니다. Admin·Ops 담당자는 환경 변수를 통해 기관별 요구사항에 맞게 기간을 조정할 수 있습니다.",
      },
      {
        type: "list",
        items: [
          "감사 로그(audit_logs): 730일",
          "Chat 세션/메시지: 180일",
          "Chat Archive·Chat Audit: 365일",
          "Alert Delivery·Evidence Snapshot: 365일",
          "Report Export Log: 180일",
          "Report Share Token: 90일",
          "LightMem 설정 파일: 이용자 삭제 또는 계정 삭제 시 즉시 폐기",
        ],
      },
      {
        type: "note",
        text: "보존 정책은 스케줄러에서 하루 1회 실행되고, 삭제 결과는 audit_logs.source='compliance.retention' 이벤트로 기록됩니다.",
      },
    ],
  },
  {
    id: "dsar",
    title: "4. 데이터 열람·삭제(권리 요청) 절차",
    contents: [
      {
        type: "list",
        items: [
          "Settings → Legal & Data에서 내보내기 또는 삭제 요청을 남기면 처리 큐에 등록되어 순차적으로 처리됩니다.",
          "요청은 최대 24시간마다 실행되는 Celery 작업에서 처리되며, 진행 상태와 다운로드 링크는 화면과 API로 안내됩니다.",
          "삭제 요청 시 Chat·LightMem·Report 등의 개인 데이터를 우선 제거하고, 법적으로 보존해야 하는 데이터는 비식별화합니다.",
        ],
      },
      {
        type: "note",
        text: `이메일(${companyContact})로도 요청할 수 있으며, 본인 확인을 위해 로그인 상태 또는 추가 서류가 필요할 수 있습니다.`,
      },
    ],
  },
  {
    id: "storage",
    title: "5. 보안과 저장 위치",
    contents: [
      {
        type: "paragraph",
        text: "모든 사용자 데이터는 GCP Cloud SQL(PostgreSQL)과 GCS(evidence bundle, 내보내기 파일)에 저장되며, 저장 시 AES256 서버 측 암호화를 적용합니다. 운영자 접근은 Bastion+MFA를 거쳐야 하고, 접근 기록은 admin_audit_logs에 남습니다.",
      },
    ],
  },
  buildCompanyContactSection({
    id: "contact",
    title: "6. 문의",
    note: `데이터 사용, 라이선스, 데이터 열람·삭제(권리 요청) 처리 관련 문의는 ${companyContact} 로 연락해 주세요.`,
  }),
];

export default function DataPolicyPage() {
  return (
    <LegalDocumentPage
      title="데이터 & 라이선스 정책"
      subtitle="데이터 소스, Guardrail, 보존/삭제 원칙, 권리 요청 흐름을 한눈에 제공합니다."
      updatedAtLabel={updatedAt}
      sections={sections}
    />
  );
}
