import type { LegalSection } from "@/app/legal/_components/LegalDocumentPage";

const DEFAULT_UPDATED_AT = "2025-11-18";

export const LEGAL_COMPANY = {
  updatedAt: process.env.NEXT_PUBLIC_LEGAL_UPDATED_AT ?? DEFAULT_UPDATED_AT,
  name: process.env.NEXT_PUBLIC_COMPANY_NAME ?? "ko-finance 주식회사",
  address: process.env.NEXT_PUBLIC_COMPANY_ADDRESS ?? "서울특별시 (업데이트 예정)",
  contact: process.env.NEXT_PUBLIC_COMPANY_CONTACT ?? "support@ko.finance",
  dpoName: process.env.NEXT_PUBLIC_DPO_NAME ?? "개인정보 보호책임자",
} as const;

type ContactSectionOptions = {
  note?: string;
  id?: string;
  title?: string;
};

export function buildCompanyContactSection(options?: ContactSectionOptions): LegalSection {
  const contents: LegalSection["contents"] = [
    {
      type: "paragraph",
      text: `회사명: ${LEGAL_COMPANY.name}`,
    },
    {
      type: "paragraph",
      text: `주소: ${LEGAL_COMPANY.address}`,
    },
    {
      type: "paragraph",
      text: `연락처: ${LEGAL_COMPANY.contact}`,
    },
  ];
  if (options?.note) {
    contents.push({
      type: "note",
      text: options.note,
    });
  }
  return {
    id: options?.id ?? "contact",
    title: options?.title ?? "문의처",
    contents,
  };
}

export function buildDpoContactSection(options?: ContactSectionOptions): LegalSection {
  const contents: LegalSection["contents"] = [
    {
      type: "paragraph",
      text: `개인정보 보호책임자: ${LEGAL_COMPANY.dpoName}`,
    },
    {
      type: "paragraph",
      text: `연락처: ${LEGAL_COMPANY.contact}`,
    },
  ];
  if (options?.note) {
    contents.push({
      type: "note",
      text: options.note,
    });
  }
  return {
    id: options?.id ?? "dpo",
    title: options?.title ?? "개인정보 보호책임자 및 문의",
    contents,
  };
}
