"use client";

import Link from "next/link";

export function AppFooter() {
  return (
    <footer className="mt-auto flex flex-col gap-3 border-t border-white/10 pt-4 text-xs text-slate-400 md:flex-row md:items-center md:justify-between">
      <div>© 2025 Nuvien. All rights reserved.</div>
      <div className="flex flex-wrap items-center gap-4">
        <Link href="/legal/terms" className="hover:text-white">
          서비스 이용약관
        </Link>
        <Link href="/legal/privacy" className="hover:text-white">
          개인정보 처리방침
        </Link>
        <Link href="mailto:hello@nuvien.com" className="hover:text-white">
          지원·문의 (hello@nuvien.com)
        </Link>
      </div>
    </footer>
  );
}

export default AppFooter;
