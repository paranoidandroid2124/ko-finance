// Single source of truth for every legal/compliance copy snippet that must be
// reused across the dashboard. Keeping everything in one map lets Legal/PD
// request text updates without spelunking through UI components.
const legalCopy = {
  chat: {
    inputDisclaimer:
      "이 서비스는 공시·공공데이터 기반 정보 정리 도구이며, 투자 권유나 자문을 제공하지 않습니다.\n투자 결정 및 책임은 전적으로 이용자에게 있습니다. 이름, 주민등록번호, 계좌번호 등 민감한 개인정보는 입력하지 마세요.",
    answerBadge:
      "AI가 자동 생성한 요약으로, 오류가 포함될 수 있습니다.\n중요한 판단 전에는 반드시 원문 공시와 자료를 확인하세요.",
    evidencePanel:
      "아래 자료는 이 답변이 참고한 공시·문서 목록입니다.\n법적 효력과 책임은 각 발행기관과 원문에 있으며, 원문 내용이 항상 우선합니다."
  },
  filing: {
    header:
      "공시 원문 출처: 금융감독원 전자공시시스템(OpenDART).\n본 문서는 발행회사 및 공시기관이 작성한 자료이며, 내용에 대한 권리와 책임은 해당 기관에 있습니다.",
    pdfDownload:
      "PDF는 발행기관에서 제공한 원문을 변형 없이 전달한 것입니다.\n법적 효력과 공식 해석은 항상 발행기관의 공시·원문이 우선합니다.",
    koglType1: "이 자료는 공공누리 제1유형(출처표시, 상업적 이용 및 변경 가능) 조건에 따라 제공됩니다."
  },
  news: {
    cardFooter:
      "기사 제목과 일부 인용은 해당 언론사의 저작물이며, 전문은 원문 링크에서 확인하실 수 있습니다.\nko-finance는 기사 전문을 저장·재배포하지 않고, 요약·감성 분석·섹터 태깅만 제공합니다.",
    pageHeader:
      "뉴스 데이터는 저작권·라이선스 정책에 따라 제목·링크·요약·메타데이터 중심으로 제공됩니다.\n기사 전문은 언론사 사이트에서 확인해 주세요.",
    alertFooter:
      "이 요약 및 태깅은 참고용 정보이며, 기사 내용과 차이가 있을 수 있습니다.\n뉴스 저작권은 각 언론사에 있으며, 자세한 내용은 원문 기사를 확인해 주세요."
  },
  eventStudy: {
    boardHeader:
      "표시되는 AR·CAAR 및 통계값은 과거 데이터를 기반으로 계산된 통계 지표일 뿐이며,\n향후 수익을 보장하지 않습니다. 데이터 오류·지연·누락으로 실제 시장과 차이가 발생할 수 있습니다.\n금융투자상품에 대한 최종 투자 판단과 책임은 이용자에게 있습니다.",
    radarFooter:
      "정정 공시 영향도 및 히트맵은 통계적 요약 결과이며,\n개별 종목의 실제 투자 수익률이나 향후 성과를 보장하지 않습니다."
  },
  alerts: {
    ruleBuilderFooter:
      "본 알림은 특정 공시·뉴스·지표의 발생 사실을 알려드리기 위한 것으로,\n금융투자상품의 매수·매도 또는 보유를 권유하는 투자자문 서비스가 아닙니다.\n가격·수익률 조건 알림은 참고용으로만 사용하시고, 투자 결정은 별도의 검토를 거쳐 주세요.",
    notificationFooter:
      "이 알림은 투자 권유가 아니며, 과거·현재 데이터에 기반한 정보 제공용입니다.\n투자 결정과 그 결과에 따른 책임은 전적으로 이용자에게 있습니다."
  },
  digest: {
    pdfFooter:
      "본 리포트는 공시·공공데이터 및 라이선스된 데이터를 기반으로 자동 생성된 요약·분석 자료입니다.\n금융투자상품의 매수·매도 또는 보유를 권유하는 것이 아니며, 과거 분석 결과는 향후 수익을 보장하지 않습니다.\n데이터의 정확성과 완결성은 보장되지 않으므로, 중요한 판단 전에는 반드시 원문 공시와 관련 자료를 확인하세요.",
    exportHelper:
      "내보낸 데이터는 참고용 분석 자료입니다.\n법적·회계적 증빙이나 공식 보고에 사용하기 전에 반드시 원 출처 데이터와 대조해 주세요."
  },
  board: {
    header:
      "이 보드는 설정된 기준에 따라 자동/반자동으로 구성된 리스트입니다.\n구성 기준은 언제든 변경될 수 있으며, 최종적인 투자 의사결정 기록은 별도의 사내 절차와 시스템을 따르셔야 합니다.",
    shareModal:
      "조직 외부로 공유하는 경우, 포함된 공시·뉴스·차트에 대한 저작권 및 이용약관 준수 책임은 공유자에게 있습니다."
  },
  auth: {
    signupHelper:
      "가입 시 공시·뉴스 조회 이력, 알림 설정 등 서비스 이용 기록이 저장될 수 있습니다.\n보존 기간과 삭제 방법은 개인정보 처리방침에서 확인하실 수 있습니다.",
    termsCheckbox: "(필수) 서비스 이용약관에 동의합니다.",
    privacyCheckbox: "(필수) 개인정보 수집·이용에 동의합니다.",
    marketingCheckbox: "(선택) 이벤트·업데이트 등 마케팅 정보 수신에 동의합니다."
  },
  settings: {
    accountRetention: "계정·결제 정보: 서비스 이용 기간 + 해지 후 5년 보존",
    logRetention: "접속·감사 로그: 최대 2년 보존",
    contentRetention: "Chat·보드 내용: 탈퇴 후 6개월 이내 삭제",
    llmToggle: "외부 LLM 전송: 기본값 OFF (설정에서 변경 가능)"
  },
  admin: {
    consoleHeader:
      "이 화면에는 고객·조직 정보를 포함한 민감한 데이터가 표시될 수 있습니다.\n권한이 부여된 담당자만 접근해야 하며, 다른 목적으로 복사·전송해서는 안 됩니다.",
    auditDetail:
      "이 정보는 보안·감사 목적으로만 활용해야 하며,\n통계·마케팅 등 다른 용도로 2차 사용하려면 별도의 내부 승인과 법적 검토가 필요합니다."
  }
} as const;

export type LegalCopyMap = typeof legalCopy;
export type LegalSection = keyof LegalCopyMap;
export type LegalSectionKey<S extends LegalSection> = keyof LegalCopyMap[S];

export const LEGAL_COPY: LegalCopyMap = legalCopy;

