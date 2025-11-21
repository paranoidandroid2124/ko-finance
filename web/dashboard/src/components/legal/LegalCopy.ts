"use client";

export type LegalSection = "chat" | "filing" | "settings";

export type LegalSectionKey<S extends LegalSection> = keyof (typeof LEGAL_COPY)[S];

export const LEGAL_COPY = {
  chat: {
    inputDisclaimer:
      "이 서비스는 일반 정보 제공용입니다. 투자 판단은 이용자 책임이며, 민감 정보 입력을 피해주세요.",
    evidenceNotice: "출처는 제공된 문서 기준이며, 최신성/정확성을 추가로 확인하세요.",
  },
  filing: {
    headerNotice: "공시·보고서는 참고용으로 제공되며, 원문을 반드시 확인하세요.",
    pdfDownloadNotice: "원문 PDF는 외부 링크로 이동합니다. 최신 버전을 확인해주세요.",
    koglBadge: "본 문서는 공공저작물 저작권 정책에 따라 제공될 수 있습니다.",
  },
  settings: {
    dataRetentionList:
      "데이터 보관 기간은 정책에 따라 제한됩니다. 민감 정보 입력 시 즉시 삭제를 권장합니다.",
  },
} as const;

export type LegalCopy = typeof LEGAL_COPY;
