import { LayoutDashboard, FileText, Newspaper, MessageSquare, Settings } from "lucide-react";
import Link from "next/link";

const NAV_ITEMS = [
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/filings", label: "공시", icon: FileText },
  { href: "/news", label: "뉴스 인사이트", icon: Newspaper },
  { href: "/chat", label: "대화형 분석", icon: MessageSquare },
  { href: "/settings", label: "설정", icon: Settings }
];

export function SideNav() {
  return (
    <aside className="hidden min-h-screen w-64 flex-col border-r border-border-light bg-background-cardLight px-4 py-6 dark:border-border-dark dark:bg-background-cardDark lg:flex">
      <div className="px-3 py-2 text-lg font-semibold tracking-tight">
        K-Finance Copilot
        <p className="mt-1 text-xs font-medium text-text-secondaryLight dark:text-text-secondaryDark">
          연구원의 데이터 허브
        </p>
      </div>
      <nav className="mt-6 flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-primary/10 hover:text-primary dark:hover:bg-primary.dark/15"
          >
            <Icon className="h-5 w-5" />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
      <div className="rounded-lg border border-dashed border-border-light p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">실시간 상태</p>
        <p className="mt-1">큐 지연, Langfuse, Qdrant 상태를 곧 여기에 표시합니다.</p>
      </div>
    </aside>
  );
}

