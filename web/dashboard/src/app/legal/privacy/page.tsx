import type { Metadata } from "next";

import { LegalDocumentPage, type LegalSection } from "@/app/legal/_components/LegalDocumentPage";
import { LEGAL_COMPANY, buildDpoContactSection } from "@/app/legal/constants";

const { updatedAt, name: companyName, contact: companyContact } = LEGAL_COMPANY;

export const metadata: Metadata = {
  title: "개인정보 처리방침 | K-Finance",
  description: "수집 항목, 이용 목적, 보관 기간, 권리 행사 방법을 안내합니다.",
};

const sections: LegalSection[] = [
  {
    id: "collection",
    title: "1. 수집하는 개인정보",
    contents: [
      {
        type: "list",
        title: "필수 항목",
        items: [
          "계정 정보: 이메일, 이름, 조직명, 직함, OAuth 토큰 또는 비밀번호 해시",
          "이용 기록: 로그인·로그아웃 시각, IP 해시, 브라우저 User-Agent, RBAC 상태",
          "과금 정보: 결제 수단 식별값(토스·Stripe 토큰), 사업자 정보, 세금계산서 수령 정보",
        ],
      },
      {
        type: "list",
        title: "선택·생성 정보",
        items: [
          "Chat·Notebook·Alert 등 사용자가 직접 입력한 분석 메모, 질문, 태그",
          "LightMem·Digest 개인화 설정, Watchlist 구성",
          "Admin/Workspace 운영자가 남긴 노트, 감사 코멘트, RBAC 관리 이력",
        ],
      },
    ],
  },
  {
    id: "purpose",
    title: "2. 이용 목적",
    contents: [
      {
        type: "list",
        items: [
          "서비스 제공: 공시·뉴스 탐색, AI 챗, Event Study, Alert, Digest 생성 및 전달",
          "고객 지원: 문의 응대, 장애 대응, Audit Log 기반 이상 탐지",
          "과금·플랜 관리: PlanLock, Entitlement, 결제 정산",
          "법령 준수: 전자상거래법, 전자금융거래법, 개인정보보호법에서 요구하는 기록 보관",
        ],
      },
    ],
  },
  {
    id: "retention",
    title: "3. 보관 및 파기",
    contents: [
      {
        type: "paragraph",
        text: "법령상 보존 의무가 있는 항목은 해당 기간을 준수하며, 그 외 데이터는 아래 기간이 지나면 안전하게 삭제하거나 익명화합니다.",
      },
      {
        type: "list",
        title: "기본 보유 기간",
        items: [
          "감사 로그(audit_logs): 2년",
          "Chat 세션·메시지: 이용자가 직접 삭제하거나 마지막 활동 후 180일 경과 시 순차 삭제",
          "Chat Archive·Chat Audit: 365일",
          "Digest Snapshot·Daily Digest Log: 180일",
          "Alert Delivery Log·Evidence Snapshot: 365일",
          "Notebook 공유 토큰: 만료 또는 해지 후 90일",
          "결제·거래 내역: 전자상거래법에 따라 5년",
        ],
      },
      {
        type: "note",
        text: "보관 기간은 Admin Console 및 내부 설정에서 조정할 수 있으며, DSAR 처리나 기업 고객 계약에 따라 단축될 수 있습니다.",
      },
    ],
  },
  {
    id: "third-party",
    title: "4. 제3자 제공 및 국외 이전",
    contents: [
      {
        type: "paragraph",
        text: "이용자의 동의 없이 개인정보를 제3자에게 판매하지 않으며, 결제·클라우드·메일 발송 등 서비스 운영에 필요한 최소 범위에서만 위탁합니다. 수탁사와는 비밀유지 및 보안 의무를 계약으로 명시합니다.",
      },
      {
        type: "paragraph",
        text: "데이터는 기본적으로 GCP 서울 리전(asia-northeast3)에 저장되며, 백업·로그 분석 목적의 암호화 자료가 다른 리전에 일시 저장될 수 있습니다. Enterprise 고객은 전용 리전이나 데이터 국지화 옵션을 요청할 수 있습니다.",
      },
    ],
  },
  {
    id: "rights",
    title: "5. 정보주체 권리",
    contents: [
      {
        type: "list",
        items: [
          "열람·정정·삭제·처리정지: Settings → Legal & Data → “내 데이터 내보내기/삭제 요청”에서 DSAR을 제출하거나 이메일로 요청할 수 있습니다.",
          "동의 철회: 마케팅 안내, LightMem 사용 등 선택 동의는 언제든지 Settings에서 변경할 수 있습니다.",
          "대리인 신청: 위임장을 제출하면 서면 또는 이메일로 처리합니다.",
        ],
      },
      {
        type: "note",
        text: "요청이 접수되면 영업일 기준 7일 이내에 처리 현황을 안내하며, 법적 보존 의무가 있는 정보는 삭제가 제한될 수 있습니다.",
      },
    ],
  },
  {
    id: "cookie",
    title: "6. 쿠키 및 로그",
    contents: [
      {
        type: "paragraph",
        text: "세션 유지, 테마 설정, PlanLock 경고 등 필수 기능을 위해 쿠키와 LocalStorage를 사용합니다. 광고·추적 목적 쿠키는 기본적으로 사용하지 않으며 필요 시 별도 동의를 구합니다.",
      },
    ],
  },
  {
    id: "security",
    title: "7. 안전성 확보 조치",
    contents: [
      {
        type: "list",
        items: [
          "전송 구간 TLS 암호화 및 저장 시 민감정보 암호화",
          "RBAC·PlanLock·Audit Log를 활용한 접근 통제",
          "운영 환경 다중 인증, Bastion 접근 제어, 접근 로그 모니터링",
          "정기적인 백업·복구 점검과 침해사고 대응 훈련",
        ],
      },
    ],
  },
  buildDpoContactSection({
    title: "8. 개인정보 보호책임자 및 문의",
    note: `${companyName}는 문의를 처리하기 위한 최소 범위에서만 개인정보에 접근하며, 처리 결과를 이메일로 안내합니다.`,
  }),
];

export default function PrivacyPage() {
  return (
    <LegalDocumentPage
      title="개인정보 처리방침"
      subtitle="K-Finance Copilot이 수집·이용하는 개인정보와 이용자 권리를 투명하게 안내합니다."
      updatedAtLabel={updatedAt}
      sections={sections}
    />
  );
}
