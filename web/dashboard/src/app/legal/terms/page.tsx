import type { Metadata } from "next";

import { LegalDocumentPage, type LegalSection } from "@/app/legal/_components/LegalDocumentPage";
import { LEGAL_COMPANY, buildCompanyContactSection } from "@/app/legal/constants";

const { name: companyName, address: companyAddress, contact: companyContact, updatedAt } = LEGAL_COMPANY;

export const metadata: Metadata = {
  title: "서비스 이용약관 | Nuvien",
  description: "Nuvien AI Copilot 서비스 이용 조건과 사용자 책임 범위를 안내합니다.",
};

const sections: LegalSection[] = [
  {
    id: "scope",
    title: "1. 서비스 개요 및 약관 적용",
    contents: [
      {
        type: "paragraph",
        text: `${companyName}가 운영하는 Nuvien Copilot, Event Board, Alert, Digest, Workspace(이하 “서비스”)는 한국 공시·뉴스·시장 데이터를 분석하고 AI 기반 검색·요약·협업 기능을 제공하는 SaaS입니다.`,
      },
      {
        type: "paragraph",
        text: "본 약관은 서비스를 이용하는 모든 사용자(개인 회원, 조직 계정 포함)에 적용되며 Enterprise 고객처럼 별도 계약을 체결한 경우에는 개별 계약서가 우선합니다.",
      },
    ],
  },
  {
    id: "account",
    title: "2. 계정 생성, 권한 및 이용자 책임",
    contents: [
      {
        type: "list",
        title: "이용자는 다음 사항을 지켜 주세요.",
        items: [
          "회원·조직 정보를 최신 상태로 유지하고 계정·API 토큰·워크스페이스 접근 권한을 조직 정책에 맞게 관리합니다.",
          "서비스에서 내려받은 공시·뉴스·데이터는 출처 표기와 라이선스 조건을 지킨 범위에서만 공유하거나 2차 가공합니다.",
          "Guardrail·Admin 정책으로 차단된 요청을 우회하지 않으며 외부 반출 시에도 조직 보안 정책을 함께 준수합니다.",
          "RBAC(역할 기반 권한)이나 PlanLock 제한을 임의로 수정하거나 위조하지 않습니다.",
        ],
      },
    ],
  },
  {
    id: "plans",
    title: "3. 유료 플랜, 과금 및 갱신",
    contents: [
      {
        type: "paragraph",
        text: "Starter·Pro·Enterprise 플랜 기능과 한도는 플랜 카탈로그, PlanLock 안내, 견적서·계약서에 명시된 내용을 따릅니다.",
      },
      {
        type: "list",
        title: "과금 원칙",
        items: [
          "Seat 또는 Org 단위 선결제로 이용하며 이미 제공된 기간·리소스에 대해서는 환불이 제한될 수 있습니다.",
          "Alert·Digest·Evidence Export 등 고비용 기능은 entitlement·quota·cooldown 정책으로 보호되며 초과 시 자동으로 중단될 수 있습니다.",
          "PG·Stripe 등 카드 결제 시 국내 전자상거래법상 청약철회 기간과 예외(데이터가 이미 제공된 경우 등)를 명확히 고지합니다.",
        ],
      },
    ],
  },
  {
    id: "data-use",
    title: "4. 데이터 이용 및 지식재산권",
    contents: [
      {
        type: "paragraph",
        text: "OpenDART, KRX 시세·벤치마크, KISVALUE, Nuvien이 자체 구축한 이벤트·요약 등 모든 데이터는 각 출처 또는 Nuvien의 저작권과 라이선스 정책을 따릅니다.",
      },
      {
        type: "paragraph",
        text: "서비스 화면·API·Evidence Export 등으로 제공된 자료를 무단 복제하거나 제3자 서비스에 재판매할 수 없으며, 조직 내부 보고서·연구 목적 사용 시에도 출처 표시는 필수입니다.",
      },
    ],
  },
  {
    id: "prohibited",
    title: "5. 금지 행위",
    contents: [
      {
        type: "list",
        items: [
          "자동화 스크래핑, 역분석, 비인가 API 호출 등으로 서비스·인프라에 과도한 부하를 주는 행위",
          "금융투자상품 매수·매도·추천·수익률 보장을 암시하는 콘텐츠를 만들어 배포하는 행위",
          "타인의 개인정보·민감정보·영업비밀을 동의 없이 업로드하거나 Guardrail이 금지한 내용을 입력하는 행위",
          "Admin 콘솔·Ops API 등 제한된 리소스에 무단으로 접근하는 행위",
        ],
      },
    ],
  },
  {
    id: "liability",
    title: "6. 면책과 책임 범위",
    contents: [
      {
        type: "paragraph",
        text: "서비스는 공시·뉴스 등 검증된 데이터를 기반으로 하지만 최신성·정확성·완결성을 완벽하게 보장할 수 없습니다. AI/RAG 답변은 참고용이며 최종 투자·법률 판단은 이용자 책임입니다.",
      },
      {
        type: "paragraph",
        text: "천재지변, 통신 장애, 외부 데이터 공급 중단 등 불가항력으로 인한 손해는 책임을 지지 않으며, 유료 고객의 경우 SLA 범위 내에서 크레딧·환불 등 보상 절차를 안내합니다.",
      },
    ],
  },
  {
    id: "termination",
    title: "7. 이용 제한 및 계약 종료",
    contents: [
      {
        type: "paragraph",
        text: "조직 관리자는 RBAC·PlanLock을 통해 구성원 접근을 조정할 수 있으며, 약관 위반이 확인되면 사전 통지 후 일시 정지 또는 해지될 수 있습니다.",
      },
      {
        type: "paragraph",
        text: "계약이 종료되더라도 관련 법령상 보관이 필요한 회계·결제·감사 로그는 정해진 기간 동안만 보존한 뒤 안전하게 폐기합니다.",
      },
    ],
  },
  {
    id: "law",
    title: "8. 준거법 및 분쟁 해결",
    contents: [
      {
        type: "paragraph",
        text: "본 약관은 대한민국 법령을 준거법으로 하며, 분쟁 발생 시 서울중앙지방법원을 1심 전속 관할로 합니다. 별도 계약이 있는 경우 계약서에 정한 분쟁 해결 절차를 우선합니다.",
      },
    ],
  },
  buildCompanyContactSection({
    note: "법무·데이터 정책, 개인 데이터 열람·삭제 요청은 Settings → Legal & Data 또는 위 연락처(hello@nuvien.com)로 알려 주세요.",
    title: "9. 문의처",
  }),
];

export default function TermsPage() {
  return (
    <LegalDocumentPage
      title="서비스 이용약관"
      subtitle="Nuvien Copilot을 안전하게 이용하기 위한 권리와 의무, 제한 사항을 안내합니다."
      updatedAtLabel={updatedAt}
      sections={sections}
    />
  );
}
