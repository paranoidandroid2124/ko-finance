import Link from "next/link";
import type { Route } from "next";

import { LEGAL_COMPANY } from "@/app/legal/constants";

const LEGAL_LINKS = [
  { href: "/legal/terms", label: "이용약관" },
  { href: "/legal/privacy", label: "개인정보 처리방침" },
  { href: "/legal/data", label: "데이터 & 라이선스 정책" },
] as const;

const companyProfile = {
  name: LEGAL_COMPANY.name,
  representative: process.env.NEXT_PUBLIC_COMPANY_REPRESENTATIVE ?? "미등록",
  registrationNumber: process.env.NEXT_PUBLIC_COMPANY_REGISTRATION ?? "미등록",
  address: LEGAL_COMPANY.address,
  contact: LEGAL_COMPANY.contact
};

export function AppFooter() {
  return (
    <footer className="border-t border-border-light/60 bg-background-cardLight/40 px-4 py-6 text-xs text-text-secondaryLight dark:border-border-dark/60 dark:bg-background-cardDark/30 dark:text-text-secondaryDark">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {LEGAL_LINKS.map((link) => (
            <Link key={link.href} href={link.href as Route} className="hover:text-primary hover:underline">
              {link.label}
            </Link>
          ))}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          <span>상호: {companyProfile.name}</span>
          <span>대표: {companyProfile.representative}</span>
          <span>사업자등록번호: {companyProfile.registrationNumber}</span>
          <span>주소: {companyProfile.address}</span>
          <span>연락처: {companyProfile.contact}</span>
        </div>
      </div>
    </footer>
  );
}
